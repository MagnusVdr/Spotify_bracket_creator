import requests
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPixmapItem,
    QFileDialog
)
from PySide6.QtCore import Qt, QRectF, QSize, QThread, QObject, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QWheelEvent, QPixmap
from PySide6.QtSvg import QSvgGenerator

IMG_W      = 48
NODE_W     = 200
NODE_H     = IMG_W + 8   # node height matches image + padding
NODE_GAP   = 12
NODE_W_GAP = 70
SLOT_H     = NODE_H + NODE_GAP
TEXT_X     = IMG_W + 10  # text starts after image


def col_x(col: int) -> float:
    return col * (NODE_W + NODE_W_GAP)


def slot_cy(slot: int) -> float:
    return slot * SLOT_H + NODE_H / 2


def span_cy(first_slot: int, last_slot: int) -> float:
    return (slot_cy(first_slot) + slot_cy(last_slot)) / 2


# ── Async image loader ────────────────────────────────────────────────────────

class ImageFetcher(QObject):
    done = Signal(str, bytes)  # url, data

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            data = requests.get(self.url, timeout=5).content
        except Exception:
            data = b""
        self.done.emit(self.url, data)


class BracketView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#1a1a2e"))
        self._has_fitted  = False
        self._img_cache   = {}   # url -> QPixmap
        self._img_items   = {}   # url -> list of QGraphicsPixmapItem waiting for this image
        self._threads     = []

    def load_bracket(self, bracket: dict):
        self._scene.clear()
        self._has_fitted = False
        self._img_items  = {}

        total_rounds = bracket["rounds"]
        size         = bracket["size"]
        round_offset = bracket["round_offset"]

        slot_to_track = {}
        for t in bracket["assigned"]:
            slot_to_track[t["starter_slot"]] = t
        losers = bracket.get("losers", set())

        node_center = {}

        for r in range(total_rounds + 1):
            span    = 2 ** r
            matches = size // span
            for m in range(matches):
                first_slot = m * span
                last_slot  = first_slot + span - 1
                slot_idx   = round_offset[r] + m
                track      = slot_to_track.get(slot_idx)
                cy = span_cy(first_slot, last_slot)
                y  = cy - NODE_H / 2
                x  = col_x(r)
                is_loser = slot_idx in losers
                self._draw_node(x, y, track, slot_idx, r, m, is_loser=is_loser)
                node_center[(r, m)] = (col_x(r) + NODE_W / 2, cy)

        for r in range(total_rounds):
            span    = 2 ** r
            matches = size // span
            for m in range(0, matches, 2):
                top_c  = node_center.get((r, m))
                bot_c  = node_center.get((r, m + 1))
                next_x = col_x(r + 1)
                if top_c and bot_c:
                    self._draw_connectors(top_c, bot_c, next_x)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def fit_bracket(self):
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def _draw_node(self, x, y, track, slot_idx, r, m, is_loser=False):
        has_track = track is not None
        rect = QGraphicsRectItem(x, y, NODE_W, NODE_H)
        if is_loser:
            rect.setBrush(QColor("#5a1a1a"))
            rect.setPen(QPen(QColor("#e63946"), 1.5))
        elif has_track:
            rect.setBrush(QColor("#16533a"))
            rect.setPen(QPen(QColor("#1db954"), 1.5))
        else:
            rect.setBrush(QColor("#0d3b5e"))
            rect.setPen(QPen(QColor("#1a7abf"), 1.5))
        self._scene.addItem(rect)

        if has_track:
            # ── Image placeholder ──
            img_placeholder = QGraphicsRectItem(x + 4, y + 4, IMG_W, IMG_W)
            img_placeholder.setBrush(QColor("#111122"))
            img_placeholder.setPen(QPen(Qt.NoPen))
            self._scene.addItem(img_placeholder)

            url = track.get("image_url")
            if url:
                pix_item = QGraphicsPixmapItem()
                pix_item.setPos(x + 4, y + 4)
                self._scene.addItem(pix_item)

                if url in self._img_cache:
                    self._apply_pixmap(pix_item, self._img_cache[url])
                else:
                    self._img_items.setdefault(url, []).append(pix_item)
                    if len(self._img_items[url]) == 1:
                        self._fetch_image(url)

            # ── Text ──
            tx = x + TEXT_X
            name = QGraphicsTextItem(track["name"][:20])
            name.setDefaultTextColor(QColor("#ffffff"))
            name.setFont(QFont("Arial", 8, QFont.Bold))
            name.setPos(tx, y + 2)
            self._scene.addItem(name)

            artist = QGraphicsTextItem(track["artists"][:18])
            artist.setDefaultTextColor(QColor("#aaaaaa"))
            artist.setFont(QFont("Arial", 7))
            artist.setPos(tx, y + NODE_H // 2)
            self._scene.addItem(artist)

            if "votes" in track:
                v = QGraphicsTextItem(f"{track['votes']} pts")
                v.setDefaultTextColor(QColor("#f0c040"))
                v.setFont(QFont("Arial", 7, QFont.Bold))
                v.setPos(x + NODE_W - 44, y + NODE_H // 2)
                self._scene.addItem(v)
        else:
            label = QGraphicsTextItem(f"S{slot_idx} R{r} M{m}")
            label.setDefaultTextColor(QColor("#555577"))
            label.setFont(QFont("Arial", 7))
            label.setPos(x + 6, y + NODE_H / 2 - 8)
            self._scene.addItem(label)

    def _fetch_image(self, url: str):
        thread = QThread()
        fetcher = ImageFetcher(url)
        fetcher.moveToThread(thread)
        fetcher.done.connect(self._on_image_fetched)
        thread.started.connect(fetcher.run)
        thread.start()
        self._threads.append((thread, fetcher))

    def _on_image_fetched(self, url: str, data: bytes):
        if data:
            pix = QPixmap()
            pix.loadFromData(data)
            pix = pix.scaled(IMG_W, IMG_W, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_cache[url] = pix
            for item in self._img_items.get(url, []):
                self._apply_pixmap(item, pix)

    def _apply_pixmap(self, item: QGraphicsPixmapItem, pix: QPixmap):
        item.setPixmap(pix)

    def _draw_connectors(self, top_c, bot_c, next_x):
        pen   = QPen(QColor("#1a7abf"), 1.5)
        mid_x = next_x - NODE_W_GAP / 2
        cy    = (top_c[1] + bot_c[1]) / 2
        for x1, y1, x2, y2 in [
            (top_c[0] + NODE_W / 2 - 10, top_c[1], mid_x, top_c[1]),
            (bot_c[0] + NODE_W / 2 - 10, bot_c[1], mid_x, bot_c[1]),
            (mid_x, top_c[1], mid_x, bot_c[1]),
            (mid_x, cy, next_x, cy),
        ]:
            l = QGraphicsLineItem(x1, y1, x2, y2)
            l.setPen(pen)
            self._scene.addItem(l)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def save_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Bracket", "bracket.svg", "SVG Files (*.svg)")
        if not path:
            return
        rect = self._scene.sceneRect()
        generator = QSvgGenerator()
        generator.setFileName(path)
        generator.setSize(QSize(int(rect.width()), int(rect.height())))
        generator.setViewBox(QRectF(0, 0, rect.width(), rect.height()))
        generator.setTitle("Bracket")
        painter = QPainter(generator)
        painter.setRenderHint(QPainter.Antialiasing)
        self._scene.render(painter, source=rect)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._scene.items() and not self._has_fitted:
            self._has_fitted = True
            self.fit_bracket()