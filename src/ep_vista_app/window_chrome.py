# SPDX-FileCopyrightText: 2026 Ritz
# SPDX-License-Identifier: LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS
# AGPL-3.0-or-later with the narrow permission in ADDITIONAL_PERMISSION.md
# at the project root. No third-party model rights are granted.

"""Qt Widgets glass title bar with system move/resize and a local fallback.

Only the outer shell/title region is translucent. Data widgets remain opaque;
this is not an OS desktop-blur effect and does not change system settings.
"""

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QSizePolicy,
    QStyle, QToolButton, QVBoxLayout, QWidget,
)


class GlassShell(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        radius = 0 if self.window().isMaximized() else 18
        path.addRoundedRect(rect, radius, radius)
        # Keep alpha uniform across each row, including the entire title bar.
        backdrop = QLinearGradient(0, 0, 0, self.height())
        backdrop.setColorAt(0, QColor(230, 239, 255, 228))
        backdrop.setColorAt(0.12, QColor(239, 243, 252, 255))
        backdrop.setColorAt(1, QColor(235, 230, 251, 255))
        painter.fillPath(path, backdrop)
        painter.setPen(QPen(QColor(255, 255, 255, 225), 1))
        painter.drawPath(path)


class GlassTitleBar(QFrame):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._drag_anchor = None
        self.setObjectName("glassTitleBar")
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QFrame#glassTitleBar { background:rgba(255,255,255,90);
                border:1px solid rgba(255,255,255,190); border-radius:11px; }
            QLabel { background:transparent; color:#44577C; font-size:9pt; }
            QToolButton { background:transparent; border:0; border-radius:7px; }
            QToolButton:hover { background:rgba(203,215,247,180); }
            QToolButton:pressed { background:rgba(176,193,237,210); }
            QToolButton:focus { border:1px solid #868AE3; }
            QToolButton#windowClose:hover { background:#E56371; }
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 2, 3, 2)
        row.setSpacing(4)
        self.title_label = QLabel(owner.windowTitle())
        self.title_label.setMinimumWidth(0)
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(self.title_label, 1)
        self.minimize_button = self._button("最小化", QStyle.SP_TitleBarMinButton, owner.showMinimized)
        self.maximize_button = self._button("最大化", QStyle.SP_TitleBarMaxButton, self.toggle_maximized)
        self.close_button = self._button("关闭", QStyle.SP_TitleBarCloseButton, owner.close)
        self.close_button.setObjectName("windowClose")
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            row.addWidget(button)
        owner.windowTitleChanged.connect(self._update_title)
        self.sync_state()

    def _button(self, text, icon, callback):
        button = QToolButton(self)
        button.setFixedSize(38, 30)
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.setIcon(self.style().standardIcon(icon))
        button.clicked.connect(callback)
        return button

    def _update_title(self, *_args):
        title = self.owner.windowTitle()
        self.title_label.setText(self.fontMetrics().elidedText(title, Qt.ElideRight, self.title_label.width()))
        self.title_label.setToolTip(title)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_title()

    def sync_state(self):
        maximized = self.owner.isMaximized()
        text = "还原" if maximized else "最大化"
        self.maximize_button.setToolTip(text)
        self.maximize_button.setAccessibleName(text)
        icon = QStyle.SP_TitleBarNormalButton if maximized else QStyle.SP_TitleBarMaxButton
        self.maximize_button.setIcon(self.style().standardIcon(icon))

    def toggle_maximized(self):
        self.owner.showNormal() if self.owner.isMaximized() else self.owner.showMaximized()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.owner.start_system_move():
                if self.owner.isMaximized():
                    ratio = event.globalPosition().x() - self.owner.x()
                    ratio /= max(self.owner.width(), 1)
                    self.owner.showNormal()
                    self.owner.move(event.globalPosition().toPoint() - QPoint(int(self.owner.width() * ratio), 20))
                self._drag_anchor = event.globalPosition().toPoint() - self.owner.pos()
                self.grabMouse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_anchor is not None and event.buttons() & Qt.LeftButton:
            self.owner.move(event.globalPosition().toPoint() - self._drag_anchor)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_anchor is not None:
            self._drag_anchor = None
            self.releaseMouse()
        super().mouseReleaseEvent(event)


class GlassMainWindow(QMainWindow):
    """Frameless chrome shared by settings/results; close policies stay in them."""

    EDGE_WIDTH = 7

    def __init__(self, parent=None, flags=Qt.Window):
        super().__init__(parent, flags | Qt.FramelessWindowHint)
        self.setObjectName("glassWindow")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._fallback_resize = None
        self._edge_cursor_widget = None
        self._edge_saved_cursor = None
        self.title_bar = None
        self._shell = None
        QApplication.instance().installEventFilter(self)

    def set_content_widget(self, widget):
        self._shell = GlassShell(self)
        layout = QVBoxLayout(self._shell)
        layout.setContentsMargins(7, 6, 7, 7)
        layout.setSpacing(3)
        self.title_bar = GlassTitleBar(self)
        layout.addWidget(self.title_bar)
        layout.addWidget(widget, 1)
        super().setCentralWidget(self._shell)
        # Mouse tracking is required for an edge cursor even without a click.
        self.setMouseTracking(True)
        self._shell.setMouseTracking(True)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and self.title_bar is not None:
            self.title_bar.sync_state()
            self._shell.update()
            self._restore_cursor()

    def start_system_move(self):
        handle = self.windowHandle()
        return bool(handle and handle.startSystemMove())

    def start_system_resize(self, edges):
        handle = self.windowHandle()
        return bool(handle and handle.startSystemResize(edges))

    def resize_edges(self, point):
        edges = Qt.Edges()
        if self.isMaximized() or self.isFullScreen() or not self.rect().contains(point):
            return edges
        margin = self.EDGE_WIDTH
        if self.minimumWidth() < self.maximumWidth():
            if point.x() < margin:
                edges |= Qt.LeftEdge
            elif point.x() >= self.width() - margin:
                edges |= Qt.RightEdge
        if self.minimumHeight() < self.maximumHeight():
            if point.y() < margin:
                edges |= Qt.TopEdge
            elif point.y() >= self.height() - margin:
                edges |= Qt.BottomEdge
        return edges

    def _restore_cursor(self):
        if self._edge_cursor_widget is not None:
            try:
                self._edge_cursor_widget.setCursor(self._edge_saved_cursor)
            except RuntimeError:
                pass  # The pointer may have left a widget deleted with a chart.
            self._edge_cursor_widget = None

    def _resize_fallback_to(self, global_position):
        edges, anchor, initial = self._fallback_resize
        delta = global_position - anchor
        rect = QRect(initial)
        if edges & Qt.LeftEdge:
            width = max(self.minimumWidth(), min(self.maximumWidth(), initial.width() - delta.x()))
            rect.setLeft(initial.right() - width + 1)
        elif edges & Qt.RightEdge:
            rect.setWidth(max(self.minimumWidth(), min(self.maximumWidth(), initial.width() + delta.x())))
        if edges & Qt.TopEdge:
            height = max(self.minimumHeight(), min(self.maximumHeight(), initial.height() - delta.y()))
            rect.setTop(initial.bottom() - height + 1)
        elif edges & Qt.BottomEdge:
            rect.setHeight(max(self.minimumHeight(), min(self.maximumHeight(), initial.height() + delta.y())))
        self.setGeometry(rect)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind not in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.Leave):
            return False
        if not isinstance(watched, QWidget) or watched.window() is not self:
            return False
        if kind == QEvent.Leave:
            if self._fallback_resize is None:
                self._restore_cursor()
            return False
        if self._fallback_resize is not None:
            if kind == QEvent.MouseMove:
                self._resize_fallback_to(event.globalPosition().toPoint())
                return True
            if kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._fallback_resize = None
                self.releaseMouse()
                return True
        edges = self.resize_edges(self.mapFromGlobal(event.globalPosition().toPoint()))
        if kind == QEvent.MouseMove:
            self._restore_cursor()
            if edges:
                diagonal_a = edges in (Qt.TopEdge | Qt.LeftEdge, Qt.BottomEdge | Qt.RightEdge)
                diagonal_b = edges in (Qt.TopEdge | Qt.RightEdge, Qt.BottomEdge | Qt.LeftEdge)
                cursor = (Qt.SizeFDiagCursor if diagonal_a else Qt.SizeBDiagCursor if diagonal_b
                          else Qt.SizeHorCursor if edges & (Qt.LeftEdge | Qt.RightEdge) else Qt.SizeVerCursor)
                self._edge_cursor_widget, self._edge_saved_cursor = watched, watched.cursor()
                watched.setCursor(cursor)
        elif kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton and edges:
            if not self.start_system_resize(edges):
                self._fallback_resize = (edges, event.globalPosition().toPoint(), self.geometry())
                self.grabMouse()
            return True
        return False
