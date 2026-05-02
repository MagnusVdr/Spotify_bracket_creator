import requests
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QFrame, QSizePolicy,  QPushButton
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap


class ImageLoader(QObject):
    loaded = Signal(QLabel, bytes)

    def __init__(self, label: QLabel, url: str):
        super().__init__()
        self.label = label
        self.url = url

    def run(self):
        try:
            data = requests.get(self.url, timeout=5).content
            self.loaded.emit(self.label, data)
        except Exception:
            pass


class RoundStartInput(QWidget):
    """A label + text input for one round's starting point."""
    def __init__(self, round_index: int, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel(f"R{round_index + 1}:")
        lbl.setFixedWidth(32)
        lbl.setStyleSheet("font-size: 12px; color: #aaa; font-weight: bold;")
        layout.addWidget(lbl)

        self.input = QLineEdit("0:00")
        self.input.setFixedWidth(72)
        self.input.setFixedHeight(28)
        self.input.setStyleSheet("font-size: 12px; padding: 2px 4px;")
        self.input.setToolTip(f"Starting point for Round {round_index + 1} (format: m:ss)")
        layout.addWidget(self.input)

    def get_ms(self) -> int:
        try:
            parts = self.input.text().strip().split(":")
            if len(parts) == 2:
                return (int(parts[0]) * 60 + int(parts[1])) * 1000
            return int(parts[0]) * 1000
        except ValueError:
            return 0


class TrackRow(QFrame):
    remove_requested = Signal(object)  # emits self

    def __init__(self, track: dict, num_rounds: int, parent=None):
        super().__init__(parent)
        self.track = track
        self.setFrameShape(QFrame.StyledPanel)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── Top row: art + name/artist + remove btn ──
        top = QHBoxLayout()
        top.setSpacing(12)

        self.art_label = QLabel()
        self.art_label.setFixedSize(64, 64)
        self.art_label.setAlignment(Qt.AlignCenter)
        self.art_label.setStyleSheet("background: #222; border-radius: 6px;")
        top.addWidget(self.art_label)

        info = QVBoxLayout()
        info.setSpacing(4)
        name_label = QLabel(track["name"])
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name_label.setWordWrap(True)
        artist_label = QLabel(track["artists"])
        artist_label.setStyleSheet("color: #aaa; font-size: 12px;")
        info.addWidget(name_label)
        info.addWidget(artist_label)
        top.addLayout(info, stretch=1)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setToolTip("Remove track")
        remove_btn.setStyleSheet("""
            QPushButton { background: #5a1a1a; border-radius: 14px;
                          font-size: 13px; color: #ff6b6b; font-weight: bold; }
            QPushButton:hover { background: #7a2020; }
        """)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        top.addWidget(remove_btn, alignment=Qt.AlignTop)

        outer.addLayout(top)

        # ── Bottom row: start time inputs (initially hidden) ──
        self._inputs_row = QHBoxLayout()
        self._inputs_row.setSpacing(10)
        self._inputs_row.setContentsMargins(0, 0, 0, 0)

        self._round_inputs: list[RoundStartInput] = []
        for r in range(num_rounds):
            inp = RoundStartInput(r)
            inp.setVisible(False)
            self._round_inputs.append(inp)
            self._inputs_row.addWidget(inp)

        self._inputs_row.addStretch()
        outer.addLayout(self._inputs_row)

        # Adjust height dynamically
        self._update_height()

        if track.get("image_url"):
            self._load_image(track["image_url"])

    def set_round_visible(self, round_index: int, visible: bool):
        if round_index < len(self._round_inputs):
            self._round_inputs[round_index].setVisible(visible)
        self._update_height()

    def _update_height(self):
        any_visible = any(inp.isVisible() for inp in self._round_inputs)
        self.setFixedHeight(110 if any_visible else 80)

    def _load_image(self, url: str):
        self._thread = QThread()
        self._loader = ImageLoader(self.art_label, url)
        self._loader.moveToThread(self._thread)
        self._loader.loaded.connect(self._set_image)
        self._thread.started.connect(self._loader.run)
        self._thread.start()

    def _set_image(self, label: QLabel, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        label.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._thread.quit()

    def get_start_times_ms(self) -> list[int]:
        return [inp.get_ms() for inp in self._round_inputs]


class TrackListWidget(QWidget):
    track_removed = Signal(dict)  # emits the removed track dict

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Tracks")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px;")
        layout.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._inner = QVBoxLayout(self._container)
        self._inner.setSpacing(6)
        self._inner.setContentsMargins(4, 4, 4, 4)
        self._inner.addStretch()
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        self._rows: list[TrackRow] = []
        self._num_rounds = 0

    def load_tracks(self, tracks: list[dict], num_rounds: int):
        for row in self._rows:
            row.deleteLater()
        self._rows.clear()
        self._num_rounds = num_rounds

        self._inner.takeAt(self._inner.count() - 1)

        for track in tracks:
            row = TrackRow(track, num_rounds)
            row.remove_requested.connect(self._on_remove)
            self._rows.append(row)
            self._inner.addWidget(row)

        self._inner.addStretch()

    def set_round_input_visible(self, round_index: int, visible: bool):
        """Called by settings widget when a round's mode changes."""
        for row in self._rows:
            row.set_round_visible(round_index, visible)

    def _on_remove(self, row: object):
        track = row.track
        self._rows.remove(row)
        row.deleteLater()
        self.track_removed.emit(track)

    def get_all_start_times(self) -> dict[str, list[int]]:
        return {
            row.track["uri"]: row.get_start_times_ms()
            for row in self._rows
        }