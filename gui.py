import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QSplitter, QLabel
)
from PySide6.QtCore import Qt

from spotify_logic import SpotifyClient
from state_manager import save_state, load_state, restore_bracket, restore_runner, delete_state, has_save
from playback_manager import PlaybackManager
from bracket_runner import BracketRunner
from clash_window import ClashWidget
from bracket import build_bracket
from bracket_widget import BracketView
from track_list_widget import TrackListWidget
from settings_widget import SettingsWidget


# ── Screen 1: Playlist Entry ──────────────────────────────────────────────────

class StartScreen(QWidget):
    def __init__(self, on_start_callback, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        title = QLabel("🎵 Spotify Bracket")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.playlist_input = QLineEdit()
        self.playlist_input.setPlaceholderText("Paste Spotify playlist link here...")
        self.playlist_input.setFixedWidth(400)
        self.playlist_input.returnPressed.connect(on_start_callback)
        layout.addWidget(self.playlist_input, alignment=Qt.AlignCenter)

        self.start_button = QPushButton("Start")
        self.start_button.setFixedWidth(200)
        self.start_button.clicked.connect(on_start_callback)
        layout.addWidget(self.start_button, alignment=Qt.AlignCenter)


# ── Screen 2: Bracket Setup ───────────────────────────────────────────────────

class BracketScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal)

        self.settings_widget    = SettingsWidget()
        self.track_list_widget  = TrackListWidget()
        self.bracket_view       = BracketView()

        self.splitter.addWidget(self.settings_widget)
        self.splitter.addWidget(self.track_list_widget)
        self.splitter.addWidget(self.bracket_view)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 1)

        layout.addWidget(self.splitter)

    def load(self, tracks: list[dict], bracket: dict):
        self.settings_widget.load_rounds(bracket["rounds"])
        self.track_list_widget.load_tracks(tracks, bracket["rounds"])
        self.bracket_view.load_bracket(bracket)
        self.settings_widget.round_mode_changed.connect(
            self.track_list_widget.set_round_input_visible
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        total = self.splitter.width()
        third = total // 3
        self.splitter.setSizes([third, third, total - 2 * third])


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spotify Bracket")
        self.showMaximized()

        self.spotify  = SpotifyClient()
        self.playback = PlaybackManager(self.spotify)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.start_screen   = StartScreen(on_start_callback=self.on_start)
        self.bracket_screen = BracketScreen()
        self.clash_widget   = ClashWidget(
            self.playback,
            self.bracket_screen.settings_widget
        )
        self.clash_widget.clash_resolved.connect(self._on_clash_resolved)
        # clash_resolved now emits {winner, loser}

        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.bracket_screen)
        self.stack.addWidget(self.clash_widget)
        self.stack.setCurrentWidget(self.start_screen)

        self._tracks  = []
        self._bracket = None
        self._runner  = None

        self.bracket_screen.settings_widget.youtube_track_added.connect(self.on_youtube_track_added)
        self.bracket_screen.settings_widget.start_bracket_btn.clicked.connect(self.on_start_bracket)
        self.bracket_screen.track_list_widget.track_removed.connect(self.on_track_removed)

        # Check for saved state on startup
        if has_save():
            self._try_restore_save()

    # ── Spotify load ──────────────────────────────────────────────────────────

    def on_start(self):
        link = self.start_screen.playlist_input.text().strip()
        if not link:
            QMessageBox.warning(self, "Error", "Please enter a playlist link.")
            return
        try:
            tracks = self.spotify.get_playlist_tracks(link)
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Link", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load playlist:\n{e}")
            return
        if len(tracks) < 2:
            QMessageBox.warning(self, "Too few tracks", "Playlist needs at least 2 tracks.")
            return
        self._tracks  = tracks
        self._bracket = build_bracket(tracks)
        self.bracket_screen.load(tracks, self._bracket)
        self.stack.setCurrentWidget(self.bracket_screen)

    # ── YouTube ───────────────────────────────────────────────────────────────

    def on_youtube_track_added(self, track: dict):
        self._tracks.append(track)
        self._bracket = build_bracket(self._tracks)
        self.bracket_screen.load(self._tracks, self._bracket)

    # ── Bracket start ─────────────────────────────────────────────────────────

    def on_track_removed(self, track: dict):
        uri = track.get("uri", "")
        self._tracks = [t for t in self._tracks if t.get("uri") != uri]
        if self._tracks:
            self._bracket = build_bracket(self._tracks)
            self.bracket_screen.load(self._tracks, self._bracket)
        else:
            self._bracket = None

    def on_start_bracket(self):
        if not self._bracket or not self._tracks:
            return
        settings    = self.bracket_screen.settings_widget.get_all_settings()
        start_times = self.bracket_screen.track_list_widget.get_all_start_times()
        for t in self._tracks:
            t["start_times_ms"] = start_times.get(t.get("uri", ""), [])
        self._runner = BracketRunner(self._bracket, self._tracks, settings)
        self._run_next_clash()

    def _run_next_clash(self):
        result = self._runner.find_next_clash()
        if result is None:
            winner = self._runner.get_winner()
            name   = winner["name"] if winner else "Unknown"
            self._bracket["assigned"] = [t for t in self._runner.slot_state if t is not None]
            self._bracket["losers"]   = self._runner.losers
            delete_state()  # clean up save on completion
            self.clash_widget.show_winner(name, self._bracket)
            return

        track_a, track_b, result_slot, round_idx = result
        round_settings = self._runner.get_round_settings(round_idx)
        self.clash_widget.load_clash(
            track_a, track_b, round_idx,
            self._bracket, round_settings
        )
        self.stack.setCurrentWidget(self.clash_widget)

    def _on_clash_resolved(self, result: dict):
        if self._runner.current_clash is None:
            return
        winner = result["winner"]
        loser  = result["loser"]
        _, _, result_slot, _ = self._runner.current_clash
        self._runner.record_winner(winner, loser, result_slot)

        self._bracket["assigned"] = [t for t in self._runner.slot_state if t is not None]
        self._bracket["losers"]   = self._runner.losers

        # Save state after every lock-in
        save_state(self._tracks, self._bracket, self._runner)

        self.clash_widget.update_bracket(self._bracket)
        self._run_next_clash()

    def _try_restore_save(self):
        state = load_state()
        if not state:
            return
        reply = QMessageBox.question(
            self, "Resume bracket?",
            "A saved bracket was found. Resume where you left off?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            delete_state()
            return
        try:
            self._tracks  = state["tracks"]
            self._bracket = restore_bracket(state["bracket"])
            settings      = list(state["runner"]["settings"].values())

            self.bracket_screen.load(self._tracks, self._bracket)
            self.stack.setCurrentWidget(self.bracket_screen)

            self._runner = BracketRunner(self._bracket, self._tracks, settings)
            restore_runner(self._runner, state["runner"])

            self._run_next_clash()
        except Exception as e:
            QMessageBox.warning(self, "Restore failed", f"Could not restore save:\n{e}")
            delete_state()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())