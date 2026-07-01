import os
import html
import qtawesome as qta

from .styles import Catppuccin  # Macchiato 변수 사용을 위해 추가
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsRectItem, 
                             QListWidget, QAbstractItemView, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame)
from PyQt6.QtGui import QColor, QFont, QBrush, QPen, QPainter, QPaintEvent, QDrag, QPixmap, QIcon
from PyQt6.QtCore import pyqtSignal, Qt, QSizeF, QRectF, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QSize
from .styles import CurrentTheme as Theme
from BlurWindow.blurWindow import GlobalBlur
from src.utils.utils_font import get_current_font_family # [추가]

# 1. 통합 비디오 플레이어
class ProVideoView(QGraphicsView):
    click_ratio_signal = pyqtSignal(float)
    wheel_signal = pyqtSignal(int) # [추가] 휠 이벤트 신호 정의
    
    def set_progressbar_visible(self, visible):
        """영상 목록 유무에 따라 플레이바 숨김/표시"""
        if visible:
            self.progress_bg.show()
            self.progress_fill.show()
        else:
            self.progress_bg.hide()
            self.progress_fill.hide()
            
    def set_privacy_screen(self, enabled: bool):
        self.is_privacy_active = enabled 
        
        # [수정] self.scene() -> self.scene (괄호 삭제)
        from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
        for item in self.scene.items(): 
            if isinstance(item, QGraphicsVideoItem):
                item.setVisible(not enabled)
        
        self.set_progressbar_visible(not enabled)
        self.viewport().update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        
        is_privacy = getattr(self, 'is_privacy_active', False)
        from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
        has_visible_video = any(isinstance(item, QGraphicsVideoItem) and item.isVisible() for item in self.scene.items())

        if is_privacy or not has_visible_video:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.viewport().rect())

            # 배경을 다시 테마 색상으로 채우고 안내 문구를 그립니다.
            painter.fillRect(self.viewport().rect(), QBrush(QColor(Theme.BASE)))
            
            #icon_size = 80
            #icon = qta.icon('fa5s.file-video', color=Theme.OVERLAY)
            #icon_x = (rect.width() - icon_size) / 2
            #icon_y = (rect.height() - icon_size) / 2 - 20
            #icon.paint(painter, int(icon_x), int(icon_y), int(icon_size), int(icon_size))
            
            painter.setPen(QColor(Theme.TEXT_SUB))
            painter.setFont(QFont(get_current_font_family(), 13, QFont.Weight.Bold))
            msg = "" if is_privacy else "Drag & Drop Video or Folder"
            painter.drawText(rect.adjusted(0, 40, 0, 0), Qt.AlignmentFlag.AlignCenter, msg)

            painter.end()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus) 
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setLineWidth(0)
        self.setMidLineWidth(0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setViewportMargins(0, 0, 0, 0)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setStyleSheet("background: transparent; border: none;")
        self.viewport().setStyleSheet("background: transparent;")
        # [추가] 뷰포트 자체에 투명도와 안티앨리어싱 설정 유도
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 배경색 및 스크롤바 제거
        self.setStyleSheet(f"background-color: transparent; border: none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 렌더링 품질 설정
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing) # [추가] 텍스트 품질 향상 필수

        # [버그 수정] 좌표 정렬 (AlignLeft | AlignTop)
        # 기본값인 AlignCenter는 뷰와 씬의 크기가 다를 때 오프셋을 발생시켜 클릭 좌표가 틀어짐
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        
        # 씬(Scene) 생성
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # 안내 텍스트
        # 안내 텍스트 설정
        self.info_text = QGraphicsTextItem()
        # 중앙 정렬이 흐트러지지 않도록 텍스트 너비를 고정합니다.
        self.info_text.setTextWidth(650) 
        
        current_font = get_current_font_family()
        self.info_text.setHtml(
            f"""
            <div style='text-align: center; font-family: "{current_font}", sans-serif;'>
                <p style='color: {Theme.ACCENT_RED}; font-size: 20px; font-weight: bold; margin: 0px; padding-bottom: 5px;'>
                    ESC : 긴급 종료
                </p>
                <p style='color: {Theme.TEXT_SUB}; font-size: 14px;'>
                    사고 예방을 위해 사용자의 왼손은 항상 ESC 키 근처에 위치하십시오.
                </p>
                
                <br>
                <hr style='background-color: {Theme.OVERLAY}; border: none; height: 1px;'>
                <br>

                <table align='center' border='0' cellspacing='10' cellpadding='0'>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_GREEN}; font-weight: bold; font-size: 16px;'>Space</td>
                        <td width='30'></td> 
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>재생 / 일시정지</td>
                    </tr>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_YELLOW}; font-weight: bold; font-size: 16px;'>1</td>
                        <td></td>
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>
                            A급 태그 <span style='color: {Theme.TEXT_SUB}; font-size: 12px;'>(A급 메뉴에서 재입력 시 삭제)</span>
                        </td>
                    </tr>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_BLUE}; font-weight: bold; font-size: 16px;'>2</td>
                        <td></td>
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>
                            B급 태그 <span style='color: {Theme.TEXT_SUB}; font-size: 12px;'>(B급 메뉴에서 재입력 시 삭제)</span>
                        </td>
                    </tr>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_PURPLE}; font-weight: bold; font-size: 16px;'>3</td>
                        <td></td>
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>
                            하이라이트 저장 <span style='color: {Theme.TEXT_SUB}; font-size: 12px;'>(메뉴에서 재입력 시 삭제)</span>
                        </td>
                    </tr>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_BLUE}; font-weight: bold; font-size: 16px;'>[ ]</td>
                        <td></td>
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>
                            배속 조절 <span style='color: {Theme.TEXT_SUB}; font-size: 12px;'>(Backspace: 초기화)</span>
                        </td>
                    </tr>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_ORANGE}; font-weight: bold; font-size: 16px;'>Enter</td>
                        <td></td>
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>
                            # 마킹 <span style='color: {Theme.TEXT_SUB}; font-size: 12px;'>(파일명 맨 앞 "#" 추가)</span>
                        </td>
                    </tr>
                    <tr>
                        <td align='right' style='color: {Theme.ACCENT_RED}; font-weight: bold; font-size: 16px;'>Del</td>
                        <td></td>
                        <td align='left' style='color: {Theme.TEXT_MAIN}; font-size: 15px;'>
                            휴지통 이동 <span style='color: {Theme.TEXT_SUB}; font-size: 12px;'>(최종 삭제는 휴지통 메뉴에서)</span>
                        </td>
                    </tr>
                </table>
            </div>
            """
        )
        self.scene.addItem(self.info_text)
        self.info_text.setZValue(10)
        
        # 임시 상태 메시지
        self.status_text = QGraphicsTextItem()
        self.scene.addItem(self.status_text)
        self.status_text.setZValue(15)
        self.status_text.hide()
        
        self.msg_timer = QTimer(self)
        self.msg_timer.setSingleShot(True)
        self.msg_timer.timeout.connect(self.status_text.hide)

        # 프로그레스 바
        self.progress_bg = QGraphicsRectItem()
        self.progress_bg.setBrush(QBrush(QColor(Catppuccin.OVERLAY + "70")))
        self.progress_bg.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(self.progress_bg)
        self.progress_bg.setZValue(90)
        self.progress_bg.hide()  # [추가] 초기 실행 시 숨김
        
        self.progress_fill = QGraphicsRectItem()
        self.progress_fill.setBrush(QBrush(QColor(Catppuccin.YELLOW + "D0")))
        self.progress_fill.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(self.progress_fill)
        self.progress_fill.setZValue(91)
        self.progress_fill.hide() # [추가] 초기 실행 시 숨김
        
        self.duration = 0
        self.position = 0
        self.info_visible = True
        
        # 초기 레이아웃 업데이트
        self.update_layout_items()

    def set_info_visible(self, visible):
        self.info_visible = visible
        self.info_text.setVisible(visible)
   
    def show_temp_message(self, text, duration=1000):
        # HTML 인젝션 방지: 입력받은 텍스트를 이스케이프 처리
        safe_text = html.escape(text)
        
        # 스타일 적용 (중앙 정렬, 폰트 등)
        formatted_html = (
            f"<div style='text-align: center; color: {Theme.TEXT_MAIN}; "
            f"font-family: \"{get_current_font_family()}\"; font-size: 20px; font-weight: bold;'>"
            f"{safe_text}</div>"
        )
        
        self.status_text.setHtml(formatted_html)
        self.update_layout_items() 
        self.status_text.show()
        self.msg_timer.start(duration)


    def set_duration(self, duration):
        self.duration = duration
        self.update_progress_bar()

    def set_position(self, position):
        self.position = position
        self.update_progress_bar()

    def update_progress_bar(self):
        # [수정] 뷰 자체의 크기를 기준으로 바를 그립니다.
        width = self.viewport().width()
        height = self.viewport().height()
        
        bar_h = 7.0
        bottom_inset = 6.0
        bar_y = max(0.0, height - bar_h - bottom_inset)
        
        self.progress_bg.setRect(0, bar_y, width, bar_h)
        
        if self.duration > 0:
            ratio = max(0.0, min(1.0, self.position / self.duration))
            fill_width = width * ratio
            self.progress_fill.setRect(0, bar_y, fill_width, bar_h)
        else:
            self.progress_fill.setRect(0, bar_y, 0, bar_h)

    def update_layout_items(self):
        # [핵심 수정] 뷰의 크기에 맞춰 씬(Scene)의 크기를 1:1로 맞춥니다.
        w = self.viewport().width()
        h = self.viewport().height()
        
        self.scene.setSceneRect(0, 0, w, h)
             
        # 텍스트 위치 중앙 정렬
        text_rect = self.info_text.boundingRect()
        self.info_text.setPos((w - text_rect.width()) / 2, (h - text_rect.height()) / 2)
        
        status_rect = self.status_text.boundingRect()
        self.status_text.setPos((w - status_rect.width()) / 2, h * 0.2)
        
        self.update_progress_bar()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
        video_size = QSizeF(self.viewport().size())
        for item in self.scene.items():
            if isinstance(item, QGraphicsVideoItem):
                item.setPos(0, 0)
                item.setSize(video_size)
        self.update_layout_items()

    def _handle_seek(self, event):
        # [수정] 마우스 클릭 위치도 뷰 전체 너비 기준으로 계산
        # 정렬을 TopLeft로 바꾸었으므로 event.pos()가 (0,0) 기준이 됨
        click_x = event.pos().x()
        view_width = self.width()
        
        # 씬 정규화 (혹시 모를 오차 보정)
        # scene_width = self.scene.width()
        # if scene_width > 0:
        #    ratio = click_x / scene_width ...
        # 현재는 뷰 크기에 맞춰 씬을 계속 조정하므로 view_width 사용이 안전함

        if view_width > 0:
            ratio = click_x / view_width
            ratio = max(0.0, min(1.0, ratio))
            self.click_ratio_signal.emit(ratio)


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_seek(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._handle_seek(event)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
            # 휠 굴림 값 (일반적으로 위로 120, 아래로 -120)
            delta = event.angleDelta().y()
            if delta != 0:
                self.wheel_signal.emit(delta) # 메인으로 신호 발사!
            
            # 부모 클래스의 기본 동작(스크롤 등)은 막아서 화면이 흔들리지 않게 함
            event.accept()

# [ui_components.py] PlaceholderListWidget 클래스 (모바일 스타일 실시간 정렬)
class PlaceholderListWidget(QListWidget):
    reordered = pyqtSignal()
    folder_dropped = pyqtSignal(str) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAcceptDrops(True)
        self.setDragEnabled(True) # 드래그 켜기
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        # 1. 외부 탐색기에서 폴더를 드롭했을 때
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    self.folder_dropped.emit(path)
        
        # 2. 내부에서 순서 변경
        elif event.source() == self:
            super().dropEvent(event)
            self.reordered.emit()

    # [추가된 부분] 리스트가 비어있을 때 아이콘과 텍스트를 그리는 함수
    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event) # 기본 그리기 수행

        # 아이템이 없을 때만 워터마크 그리기
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.save()
            
            # 렌더링 품질 설정 (부드럽게)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            rect = self.viewport().rect()
            center_x = rect.center().x()
            center_y = rect.center().y()
            
            # ---------------------------------------------------------
            # 1.벡터 아이콘 그리기 (qtawesome)
            # ---------------------------------------------------------
            
            # 아이콘 크기 설정 (64x64 ~ 80x80 추천)
            icon_size = 100 
            
            # 아이콘 생성 (색상은 테마의 보조 텍스트 색상 사용)
            # 추천 아이콘: 'fa5s.folder-open' 또는 'fa5s.cloud-upload-alt'
            icon = qta.icon('mdi6.folder-plus-outline', color=Theme.OVERLAY)
            
            # 아이콘 위치 계산 (정중앙보다 살짝 위)
            icon_x = int(center_x - (icon_size / 2))
            icon_y = int(center_y - (icon_size / 2))
            
            # 캔버스에 아이콘 직접 그리기
            icon.paint(painter, icon_x, icon_y, icon_size, icon_size)
            
            painter.restore()


# 3. 파일 목록용 리스트
class WatermarkListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.watermark_text = ""
        self.watermark_color = QColor(Catppuccin.OVERLAY)
        
    def set_watermark(self, text, color_hex="#555555", alpha=100):
        self.watermark_text = text
        
        # 1. 먼저 색상 객체를 만듭니다.
        color = QColor(color_hex)
        
        # 2. [핵심] 받은 alpha 값을 색상에 적용합니다. (이 코드가 빠져있었습니다!)
        color.setAlpha(alpha) 
        
        # 3. 투명도가 적용된 색상을 저장합니다.
        self.watermark_color = color
        
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent):
        if self.watermark_text:
            painter = QPainter(self.viewport())
            painter.save()
            painter.setPen(self.watermark_color)
            font = painter.font()
            font.setPointSize(20)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, self.watermark_text)
            painter.restore()
            
        super().paintEvent(event)
        
# [New] 모던하고 심플한 커스텀 메시지 박스
class ThemeMessageBox(QDialog):
    def __init__(self, parent=None, title="", text="", icon_name="mdi6.information-outline", icon_color=Theme.ACCENT_BLUE, buttons=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 레이아웃 설정 (여백 축소)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15) # 25 -> 15
        layout.setSpacing(10) # 20 -> 10
        
        # 1. 헤더 (아이콘 + 제목)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10) # 15 -> 10
        
        # 아이콘 (사이즈 축소)
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(24, 24)) # 32 -> 24
        icon_label.setFixedSize(24, 24)
        
        # 제목
        title_label = QLabel(title)
        title_label.setObjectName("TitleLabel") # styles.py 참조
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)
        
        # 2. 본문 내용 (간격 조정)
        body_label = QLabel(text)
        body_label.setObjectName("BodyLabel") # styles.py 참조
        body_label.setTextFormat(Qt.TextFormat.PlainText) # [보안] HTML 태그 해석 방지
        body_label.setWordWrap(True)

        # 텍스트가 너무 길어질 경우를 대비해 최소 폭 설정 (선택사항)
        # body_label.setMinimumWidth(300) 
        layout.addWidget(body_label)
        
        # 3. 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.setSpacing(8) # 10 -> 8
        
        self.result_btn = QMessageBox.StandardButton.NoButton
        
        # 버튼 생성 헬퍼
        def add_btn(text, role, accent_color=None):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if accent_color:
                # 강조 버튼 스타일 (약간의 테두리 색상)
                btn.setStyleSheet(f"border: 1px solid {accent_color}; color: {accent_color};")
            
            btn.clicked.connect(lambda: self.done_with_role(role))
            btn_layout.addWidget(btn)
            return btn

        # 버튼 구성 (기본값: 확인)
        if not buttons:
            add_btn("확인", QMessageBox.StandardButton.Ok, Theme.ACCENT_BLUE)
        else:
            # Yes/No
            if buttons & QMessageBox.StandardButton.Yes:
                add_btn("네", QMessageBox.StandardButton.Yes, Theme.ACCENT_BLUE)
            if buttons & QMessageBox.StandardButton.No:
                add_btn("아니요", QMessageBox.StandardButton.No)
            
            # Ok/Cancel
            if buttons & QMessageBox.StandardButton.Ok:
                add_btn("확인", QMessageBox.StandardButton.Ok, Theme.ACCENT_BLUE)
            if buttons & QMessageBox.StandardButton.Cancel:
                add_btn("취소", QMessageBox.StandardButton.Cancel)
                
            # Delete/Save (Custom)
            if buttons & QMessageBox.StandardButton.Save:
                add_btn("저장", QMessageBox.StandardButton.Save, Theme.ACCENT_BLUE)
            if buttons & QMessageBox.StandardButton.Discard:
                add_btn("버리기", QMessageBox.StandardButton.Discard, Theme.ACCENT_RED)
        
        btn_layout.addStretch(1) # [수정] 우측에도 여백을 주어 버튼을 가운데로 모음

        layout.addLayout(btn_layout)
        
        # 스타일 적용
        from .styles import POPUP_STYLE
        self.setStyleSheet(POPUP_STYLE)
        
        # 페이드 인 애니메이션 효과
        GlobalBlur(self.winId(), hexColor='#2E344099', Dark=True, Acrylic=True)
        self.setWindowOpacity(0.0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

    def done_with_role(self, role):
        self.result_btn = role
        self.accept()

    # 창 이동 구현 (Frameless라 직접 구현)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    # 정적 메서드들 (호환성 유지)
    @staticmethod
    def _show(parent, title, text, icon_name, icon_color, buttons):
        dlg = ThemeMessageBox(parent, title, text, icon_name, icon_color, buttons)
        dlg.exec()
        return dlg.result_btn

    @staticmethod
    def question(parent, title, text, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No):
        return ThemeMessageBox._show(parent, title, text, "mdi6.help-circle-outline", Theme.ACCENT_YELLOW, buttons)

    @staticmethod
    def information(parent, title, text, buttons=QMessageBox.StandardButton.Ok):
        return ThemeMessageBox._show(parent, title, text, "mdi6.information-outline", Theme.ACCENT_BLUE, buttons)

    @staticmethod
    def warning(parent, title, text, buttons=QMessageBox.StandardButton.Ok):
        return ThemeMessageBox._show(parent, title, text, "mdi6.alert-circle-outline", Theme.ACCENT_ORANGE, buttons)

    @staticmethod
    def critical(parent, title, text, buttons=QMessageBox.StandardButton.Ok):
        return ThemeMessageBox._show(parent, title, text, "mdi6.close-circle-outline", Theme.ACCENT_RED, buttons)
