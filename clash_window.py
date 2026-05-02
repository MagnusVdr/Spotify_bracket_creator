import requests
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QSplitter, QFrame,
    QDialog, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QObject
from PySide6.QtGui import QPixmap

from bracket_widget import BracketView
from settings_widget import SettingsWidget


class ImageLoader(QObject):
    loaded = Signal(bytes)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            data = requests.get(self.url, timeout=5).content
            self.loaded.emit(data)
        except Exception:
            self.loaded.emit(b"")


class TrackPanel(QFrame):
    def __init__(self, track: dict, parent=None):
        super().__init__(parent)
        self.track = track
        self.votes = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.name_lbl = QLabel(track.get("name", ""))
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.name_lbl.setWordWrap(True)
        layout.addWidget(self.name_lbl)

        self.art = QLabel()
        self.art.setAlignment(Qt.AlignCenter)
        self.art.setMinimumHeight(160)
        self.art.setStyleSheet("background: #1a1a2e; border-radius: 8px;")
        self.art.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.art.setScaledContents(False)
        layout.addWidget(self.art, stretch=1)

        self.vote_widget = QWidget()
        vote_layout = QHBoxLayout(self.vote_widget)
        vote_layout.setSpacing(12)

        self.minus_btn = QPushButton("−")
        self.minus_btn.setFixedSize(44, 44)
        self.minus_btn.setStyleSheet("font-size:22px; border-radius:22px; background:#5a1a1a; color:white;")
        self.minus_btn.clicked.connect(self._vote_down)

        self.counter = QLabel("0")
        self.counter.setAlignment(Qt.AlignCenter)
        self.counter.setStyleSheet("font-size:20px; font-weight:bold; min-width:40px;")

        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(44, 44)
        self.plus_btn.setStyleSheet("font-size:22px; border-radius:22px; background:#1a5a1a; color:white;")
        self.plus_btn.clicked.connect(self._vote_up)

        vote_layout.addStretch()
        vote_layout.addWidget(self.minus_btn)
        vote_layout.addWidget(self.counter)
        vote_layout.addWidget(self.plus_btn)
        vote_layout.addStretch()

        self.vote_widget.setVisible(False)
        layout.addWidget(self.vote_widget)

        if track.get("image_url"):
            self._load_image(track["image_url"])

    def update_track(self, track: dict):
        self.track = track
        self.name_lbl.setText(track.get("name", "Unknown Track"))
        self.art.setPixmap(QPixmap())
        self.reset()
        if track.get("image_url"):
            self._load_image(track["image_url"])

    def set_playing(self, playing: bool):
        if playing:
            self.setStyleSheet("TrackPanel { border: 3px solid #1db954; border-radius:10px; background: rgba(29,185,84,20); }")
        else:
            self.setStyleSheet("TrackPanel { border: 3px solid transparent; }")

    def show_votes(self):
        self.vote_widget.setVisible(True)

    def reset(self):
        self.votes = 0
        self.counter.setText("0")
        self.vote_widget.setVisible(False)
        self.set_playing(False)

    def _vote_up(self):
        self.votes += 1
        self.counter.setText(str(self.votes))

    def _vote_down(self):
        self.votes -= 1
        self.counter.setText(str(self.votes))

    def _load_image(self, url: str):
        self._thread = QThread()
        self._loader = ImageLoader(url)
        self._loader.moveToThread(self._thread)
        self._loader.loaded.connect(self._set_image)
        self._thread.started.connect(self._loader.run)
        self._thread.start()

    def _set_image(self, data: bytes):
        if data:
            self._original_pix = QPixmap()
            self._original_pix.loadFromData(data)
            self._rescale_image()
        self._thread.quit()

    def _rescale_image(self):
        if hasattr(self, "_original_pix") and not self._original_pix.isNull():
            w = self.art.width() or 300
            h = self.art.height() or 300
            self.art.setPixmap(
                self._original_pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_image()


class ClashWidget(QWidget):
    clash_resolved = Signal(dict)

    def __init__(self, playback_manager, settings_widget: SettingsWidget, parent=None):
        super().__init__(parent)
        self.pm              = playback_manager
        self.settings_widget = settings_widget
        self._listen_phase   = 0
        self._round_idx      = 0

        self._play_timer = QTimer()
        self._play_timer.setSingleShot(True)
        self._play_timer.timeout.connect(self._on_playback_done)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left side ──
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(0)

        self.panel_a = TrackPanel({"name": "", "artists": ""})
        left_layout.addWidget(self.panel_a, stretch=1)

        vs_container = QWidget()
        vs_container.setFixedHeight(80)
        vs_inner = QHBoxLayout(vs_container)
        vs_inner.setContentsMargins(0, 0, 0, 0)
        vs_lbl = QLabel("VS")
        vs_lbl.setAlignment(Qt.AlignCenter)
        vs_lbl.setStyleSheet("font-size:48px; font-weight:bold; color:#f0c040;")
        vs_inner.addWidget(vs_lbl)
        left_layout.addWidget(vs_container, stretch=0)

        self.panel_b = TrackPanel({"name": "", "artists": ""})
        left_layout.addWidget(self.panel_b, stretch=1)

        # ── Bottom bar ──
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        bottom_layout.setSpacing(12)

        self.status_lbl = QLabel("Press Listen to play Track 1")
        self.status_lbl.setStyleSheet("color:#aaa; font-size:12px;")
        bottom_layout.addWidget(self.status_lbl, stretch=1)

        self.listen_btn = QPushButton("▶  Listen")
        self.listen_btn.setFixedSize(130, 44)
        self.listen_btn.setStyleSheet("""
            QPushButton { background:#1db954; border-radius:22px;
                          font-size:14px; font-weight:bold; color:white; }
            QPushButton:hover { background:#1ed760; }
        """)
        self.listen_btn.clicked.connect(self._on_listen)
        bottom_layout.addWidget(self.listen_btn)

        self.lock_in_btn = QPushButton("🔒  Lock In")
        self.lock_in_btn.setFixedSize(130, 44)
        self.lock_in_btn.setVisible(False)
        self.lock_in_btn.setStyleSheet("""
            QPushButton { background:#e63946; border-radius:22px;
                          font-size:14px; font-weight:bold; color:white; }
            QPushButton:hover { background:#ff4d5a; }
        """)
        self.lock_in_btn.clicked.connect(self._on_lock_in)
        bottom_layout.addWidget(self.lock_in_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(44, 44)
        self.settings_btn.setStyleSheet("""
            QPushButton { background:#333; border-radius:22px;
                          font-size:18px; color:#ccc; }
            QPushButton:hover { background:#444; }
        """)
        self.settings_btn.clicked.connect(self._open_settings)
        bottom_layout.addWidget(self.settings_btn)

        self.save_btn = QPushButton("💾")
        self.save_btn.setFixedSize(44, 44)
        self.save_btn.setToolTip("Save bracket as SVG")
        self.save_btn.setStyleSheet("""
            QPushButton { background:#333; border-radius:22px;
                          font-size:18px; color:#ccc; }
            QPushButton:hover { background:#444; }
        """)
        self.save_btn.clicked.connect(lambda: self.bracket_view.save_svg())
        bottom_layout.addWidget(self.save_btn)

        left_layout.addWidget(bottom_bar)

        self.bracket_view = BracketView()

        splitter.addWidget(left_container)
        splitter.addWidget(self.bracket_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def load_clash(self, track_a, track_b, round_idx, bracket, round_settings):
        self._listen_phase = 0
        self._round_idx    = round_idx
        self._stop_playback()

        self.panel_a.update_track(track_a)
        self.panel_b.update_track(track_b)

        self.listen_btn.setVisible(True)
        self.listen_btn.setText("▶  Listen")
        self.lock_in_btn.setVisible(False)
        self.status_lbl.setText("Press Listen to play Track 1")

        self.bracket_view.load_bracket(bracket)

    def update_bracket(self, bracket):
        self.bracket_view.load_bracket(bracket)

    def _get_round_settings(self) -> dict:
        for s in self.settings_widget.get_all_settings():
            if s["round"] == self._round_idx:
                return s
        return {"mode": 0, "seconds": 30}

    def _on_listen(self):
        if self._listen_phase == 0:
            self._play_track(self.panel_a.track, self.panel_a, self.panel_b)
            self._listen_phase = 1
            self.status_lbl.setText("Playing Track 1...")
            self.listen_btn.setText("⏹  Stop")

        elif self._listen_phase == 1:
            self._stop_playback()
            self._listen_phase = 2
            self.status_lbl.setText("Press Listen to play Track 2")
            self.listen_btn.setText("▶  Listen")

        elif self._listen_phase == 2:
            self._play_track(self.panel_b.track, self.panel_b, self.panel_a)
            self._listen_phase = 3
            self.status_lbl.setText("Playing Track 2...")
            self.listen_btn.setText("⏹  Stop")

        elif self._listen_phase == 3:
            self._stop_playback()
            self._show_voting()

    def _play_track(self, track, active_panel, inactive_panel):
        active_panel.set_playing(True)
        inactive_panel.set_playing(False)
        s       = self._get_round_settings()
        mode    = s.get("mode", 0)
        seconds = s.get("seconds", 30)
        if mode == 0:
            self.pm.play(track, start_ms=0)
        elif mode == 1:
            self.pm.play(track, start_ms=self._get_start_ms(track))
            self._play_timer.start(seconds * 1000)
        elif mode == 2:
            self.pm.play_random_start(track, duration_ms=seconds * 1000)
            self._play_timer.start(seconds * 1000)

    def _stop_playback(self):
        self._play_timer.stop()
        self.pm.stop()
        self.panel_a.set_playing(False)
        self.panel_b.set_playing(False)

    def _on_playback_done(self):
        self._stop_playback()
        if self._listen_phase == 1:
            self._listen_phase = 2
            self.status_lbl.setText("Press Listen to play Track 2")
            self.listen_btn.setText("▶  Listen")
        elif self._listen_phase == 3:
            self._show_voting()

    def _show_voting(self):
        self._stop_playback()
        self._listen_phase = 4
        self.status_lbl.setText("Vote, then Lock In!")
        self.listen_btn.setVisible(False)
        self.panel_a.show_votes()
        self.panel_b.show_votes()
        self.lock_in_btn.setVisible(True)

    def _get_start_ms(self, track) -> int:
        times = track.get("start_times_ms", [])
        if self._round_idx < len(times):
            return times[self._round_idx]
        return 0

    def _on_lock_in(self):
        votes_a = self.panel_a.votes
        votes_b = self.panel_b.votes

        if votes_a >= votes_b:
            winner_panel, loser_panel = self.panel_a, self.panel_b
        else:
            winner_panel, loser_panel = self.panel_b, self.panel_a

        # Make copies with correct votes attached — originals stay clean
        winner = dict(winner_panel.track)
        loser  = dict(loser_panel.track)
        winner["votes"] = winner_panel.votes
        loser["votes"]  = loser_panel.votes

        # Strip votes from originals so winner doesn't show pts in next round
        winner_panel.track.pop("votes", None)
        loser_panel.track.pop("votes", None)

        self.clash_resolved.emit({"winner": winner, "loser": loser})

    def show_winner(self, name: str, bracket: dict):
        """Replace clash panels with a winner banner, keep bracket visible."""
        self.listen_btn.setVisible(False)
        self.lock_in_btn.setVisible(False)
        self.settings_btn.setVisible(False)
        self.status_lbl.setText(f"🏆 Winner: {name}")
        self.status_lbl.setStyleSheet("color:#f0c040; font-size:18px; font-weight:bold;")
        self.panel_a.setVisible(False)
        self.panel_b.setVisible(False)
        self.bracket_view.load_bracket(bracket)

    def _open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.resize(520, 450)
        layout = QVBoxLayout(dlg)
        layout.addWidget(self.settings_widget)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()
        self.settings_widget.setParent(None)