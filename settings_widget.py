from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QComboBox, QSpinBox,
    QLineEdit, QPushButton, QMessageBox
)

PLAY_MODES = [
    "Full song",
    "X seconds from set starting point",
    "X seconds from random point",
]


class RoundSettingRow(QFrame):
    def __init__(self, round_index: int, total_rounds: int, parent=None):
        super().__init__(parent)
        self.round_index = round_index
        self.setFrameShape(QFrame.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        label = QLabel(self._round_name(round_index, total_rounds))
        label.setFixedWidth(110)
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(label)

        self.mode_combo = QComboBox()
        for mode in PLAY_MODES:
            self.mode_combo.addItem(mode)
        self.mode_combo.setFixedWidth(240)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)

        self.seconds_label = QLabel("Seconds:")
        self.seconds_label.setStyleSheet("color: #aaa;")
        self.seconds_spin = QSpinBox()
        self.seconds_spin.setRange(5, 600)
        self.seconds_spin.setValue(30)
        self.seconds_spin.setSuffix(" s")
        self.seconds_spin.setFixedWidth(80)
        layout.addWidget(self.seconds_label)
        layout.addWidget(self.seconds_spin)
        layout.addStretch()

        self._on_mode_changed(0)

    def _on_mode_changed(self, index: int):
        needs_seconds = index in (1, 2)
        self.seconds_label.setVisible(needs_seconds)
        self.seconds_spin.setVisible(needs_seconds)

    def get_settings(self) -> dict:
        mode = self.mode_combo.currentIndex()
        return {
            "round":   self.round_index,
            "mode":    mode,
            "seconds": self.seconds_spin.value() if mode in (1, 2) else None,
        }

    @staticmethod
    def _round_name(r: int, total: int) -> str:
        rounds_left = total - r
        if rounds_left == 1:
            return "Final"
        if rounds_left == 2:
            return "Semi-Final"
        if rounds_left == 3:
            return "Quarter-Final"
        return f"Round {r + 1}"


class SettingsWidget(QWidget):
    round_mode_changed = Signal(int, bool)  # (round_index, show_start_input)
    youtube_track_added = Signal(dict)      # emits a full track dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[RoundSettingRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Round playback settings ──
        rounds_header = QLabel("Playback per round")
        rounds_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px 6px 4px 6px;")
        layout.addWidget(rounds_header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._inner = QVBoxLayout(self._container)
        self._inner.setSpacing(4)
        self._inner.setContentsMargins(4, 4, 4, 4)
        self._inner.addStretch()
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, stretch=1)

        # ── Add YouTube song ──
        yt_header = QLabel("Add YouTube Song")
        yt_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px 6px 4px 6px;")
        layout.addWidget(yt_header)

        yt_row = QHBoxLayout()
        yt_row.setContentsMargins(6, 0, 6, 8)
        yt_row.setSpacing(6)

        self._yt_input = QLineEdit()
        self._yt_input.setPlaceholderText("Paste YouTube URL...")
        self._yt_input.setFixedHeight(32)
        self._yt_input.returnPressed.connect(self._on_add_youtube)
        yt_row.addWidget(self._yt_input, stretch=1)

        self._yt_button = QPushButton("Add")
        self._yt_button.setFixedHeight(32)
        self._yt_button.setFixedWidth(60)
        self._yt_button.clicked.connect(self._on_add_youtube)
        yt_row.addWidget(self._yt_button)

        layout.addLayout(yt_row)

        # ── Start Bracket ──
        self.start_bracket_btn = QPushButton("🏆  Start Bracket")
        self.start_bracket_btn.setFixedHeight(44)
        self.start_bracket_btn.setStyleSheet(
            "QPushButton { background: #f0c040; border-radius: 8px; "
            "font-size: 15px; font-weight: bold; color: #1a1a2e; margin: 8px; } "
            "QPushButton:hover { background: #f5d060; }"
        )
        layout.addWidget(self.start_bracket_btn)

    def load_rounds(self, total_rounds: int):
        for row in self._rows:
            row.deleteLater()
        self._rows.clear()
        self._inner.takeAt(self._inner.count() - 1)

        for r in range(total_rounds):
            row = RoundSettingRow(r, total_rounds)
            def make_handler(round_idx):
                def handler(index):
                    self.round_mode_changed.emit(round_idx, index == 1)
                return handler
            row.mode_combo.currentIndexChanged.connect(make_handler(r))
            self._rows.append(row)
            self._inner.addWidget(row)

        self._inner.addStretch()

    def get_all_settings(self) -> list[dict]:
        return [row.get_settings() for row in self._rows]

    def _on_add_youtube(self):
        url = self._yt_input.text().strip()
        if not url:
            return

        self._yt_button.setEnabled(False)
        self._yt_button.setText("...")

        try:
            from youtube_client import fetch_youtube_track
            track = fetch_youtube_track(url)
            self._yt_input.clear()
            self.youtube_track_added.emit(track)
        except Exception as e:
            QMessageBox.critical(self, "YouTube Error", f"Could not load track:\n{e}")
        finally:
            self._yt_button.setEnabled(True)
            self._yt_button.setText("Add")