from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QSpinBox, QCheckBox, QComboBox, QAbstractSpinBox,
                             QPushButton, QLabel, QMessageBox, QSizePolicy)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from src.managers.settings_manager import SettingsManager
from BlurWindow.blurWindow import GlobalBlur
from . import styles
from .ui_components import ThemeMessageBox

class SettingsDialog(QDialog):
    def __init__(self, parent=None, file_manager=None):
        super().__init__(parent)
        self.file_manager = file_manager
        self.setWindowTitle("환경설정")
        self.resize(300, 420) # [수정] 320x430 -> 300x420 (미니멀 사이즈)
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)
        
        self.setWindowOpacity(0.0)
        
        self.settings = SettingsManager()
        self.setStyleSheet(styles.POPUP_STYLE)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20) # [수정] 여백 축소
        self.layout.setSpacing(10) # [수정] 위젯 간격 축소

        form_layout = QFormLayout()
        form_layout.setSpacing(8) # [수정] 폼 항목 간격 조밀하게
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # [수정된 헬퍼 함수]
        def add_row(label_text, widget):
            lbl = QLabel(label_text)
            # [수정] 13px -> 15px (사용자 요청: 가독성 개선)
            lbl.setStyleSheet(f"color: {styles.CurrentTheme.ACCENT_BLUE}; font-weight: bold; font-size: 15px;")
            form_layout.addRow(lbl, widget)

        # 1. 방향키 이동 시간
        self.spin_seek = QSpinBox()
        self.spin_seek.setRange(1, 600)
        self.spin_seek.setSuffix(" 초")
        self.spin_seek.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_seek.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_row("방향키 이동:", self.spin_seek)

        # 2. 휠 간격 
        self.spin_wheel = QSpinBox()
        self.spin_wheel.setRange(1, 600)
        self.spin_wheel.setSuffix(" 초")
        self.spin_wheel.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_wheel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_row("휠 간격:", self.spin_wheel)

        # 3. 기본 스킵 비율
        self.combo_default_skip = QComboBox()
        self.combo_default_skip.addItems(["5%", "10%", "15%", "20%", "30%"])
        add_row("자동 스킵:", self.combo_default_skip)
        
        # 4. 휠 동작
        self.combo_wheel = QComboBox()
        self.combo_wheel.addItems(["파일 목록 탐색", "재생 구간 탐색"])
        add_row("휠 동작:", self.combo_wheel)
        
        # 5. 자동 재생
        self.chk_autoplay = QCheckBox("파일 선택 시 자동 재생")
        # [수정] 체크박스 폰트 크기 14px로 명시적 지정
        self.chk_autoplay.setStyleSheet(f"color: {styles.CurrentTheme.TEXT_MAIN}; font-size: 14px;")
        add_row("재생 옵션:", self.chk_autoplay)
                
        # 6. 휠 반전
        self.chk_wheel_reverse = QCheckBox("휠 방향 반전")
        self.chk_wheel_reverse.setStyleSheet(f"color: {styles.CurrentTheme.TEXT_MAIN}; font-size: 14px;")
        add_row("휠 옵션:", self.chk_wheel_reverse)

        # 7. 프라이버시 모드
        self.chk_privacy = QCheckBox("일시정지 시 가리기")
        # 프라이버시 모드는 빨간색으로 강조
        self.chk_privacy.setStyleSheet(f"color: {styles.CurrentTheme.ACCENT_RED}; font-size: 14px;")
        add_row("보안 설정:", self.chk_privacy)

        self.layout.addLayout(form_layout)
        self.layout.addStretch(1) 
        
        self.layout.addSpacing(10)

        self.layout.addSpacing(10)

        # [폰트 정보 & 로그 확인 버튼 (5:5 배치)]
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)

        # 1. 폰트 정보
        self.btn_license = QPushButton("폰트 정보")
        self.btn_license.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_license.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {styles.CurrentTheme.TEXT_SUB};
                border: 1px solid {styles.CurrentTheme.OVERLAY};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {styles.CurrentTheme.OVERLAY};
                color: {styles.CurrentTheme.TEXT_MAIN};
                border-color: {styles.CurrentTheme.ACCENT_BLUE};
            }}
        """)
        self.btn_license.clicked.connect(self.on_license_clicked)
        self.btn_license.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # 확장
        
        # 2. 로그 확인
        self.btn_log = QPushButton("로그 확인")
        self.btn_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_log.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {styles.CurrentTheme.TEXT_SUB};
                border: 1px solid {styles.CurrentTheme.OVERLAY};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {styles.CurrentTheme.OVERLAY};
                color: {styles.CurrentTheme.TEXT_MAIN};
                border-color: {styles.CurrentTheme.ACCENT_GREEN};
            }}
        """)
        self.btn_log.clicked.connect(self.on_log_clicked)
        self.btn_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # 확장

        info_layout.addWidget(self.btn_license)
        info_layout.addWidget(self.btn_log)
        
        self.layout.addLayout(info_layout)

        self.layout.addSpacing(10)

        # [데이터 초기화 버튼]
        self.btn_reset_all = QPushButton("데이터 초기화")
        self.btn_reset_all.setStyleSheet(styles.BTN_RESET_STYLE)
        self.btn_reset_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_all.clicked.connect(self.on_reset_clicked)
        self.layout.addWidget(self.btn_reset_all)

        # [저장 / 취소 버튼]
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8) 

        self.btn_save = QPushButton("✓ 저장") # [수정] 체크 아이콘 느낌 추가
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.accept)
        self.btn_save.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_save.setFixedHeight(34) # 40 -> 34
        
        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_cancel.setFixedHeight(34) # 40 -> 34

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        self.layout.addLayout(btn_layout)

        self.load_settings()

    def showEvent(self, event):
        super().showEvent(event)
        GlobalBlur(self.winId(), hexColor='#2E344050', Dark=True, Acrylic=True)
        
        self._animation = QPropertyAnimation(self, b"windowOpacity")
        self._animation.setDuration(200)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()

    def load_settings(self):
        self.spin_seek.setValue(self.settings.seek_interval)
        self.chk_autoplay.setChecked(self.settings.auto_play)
        
        default_skip = self.settings.default_skip
        idx = self.combo_default_skip.findText(default_skip)
        if idx >= 0: self.combo_default_skip.setCurrentIndex(idx)
        
        self.combo_wheel.setCurrentIndex(self.settings.wheel_action)
        self.spin_wheel.setValue(self.settings.wheel_interval)
        self.chk_wheel_reverse.setChecked(self.settings.wheel_reverse)
        self.chk_privacy.setChecked(self.settings.privacy_mode)

    def save_settings(self):
        self.settings.seek_interval = self.spin_seek.value()
        self.settings.auto_play = self.chk_autoplay.isChecked()
        self.settings.default_skip = self.combo_default_skip.currentText()
        self.settings.wheel_action = self.combo_wheel.currentIndex()
        self.settings.wheel_interval = self.spin_wheel.value()
        self.settings.wheel_reverse = self.chk_wheel_reverse.isChecked()
        self.settings.privacy_mode = self.chk_privacy.isChecked()
        self.settings.sync() 
        
    def on_reset_clicked(self):
        warning_msg = (
            "⚠️ 모든 설정과 기록을 초기화하시겠습니까?\n\n"
            "• 삭제: 폴더 목록, 태그, 하이라이트, 휴지통\n"
            "• 보존: 실제 동영상 파일\n\n"
            "이 작업은 되돌릴 수 없습니다."
        )

        reply = ThemeMessageBox.question(
            self, 
            "기록 초기화 확인",
            warning_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.file_manager:
                self.file_manager.reset_all_data()
                if self.parent() and hasattr(self.parent(), 'reset_all_ui'):
                    self.parent().reset_all_ui()
                ThemeMessageBox.information(self, "완료", "모든 기록이 초기화되었습니다.")
                self.accept()
    
    def on_license_clicked(self):
        """라이센스 정보 팝업 표시"""
        from src.utils.utils_font import get_current_font_family
        import os
        
        font_name = get_current_font_family()
        license_text = f"사용 중인 폰트: {font_name}\n\n"
        
        # 라이센스 파일 읽기 시도
        license_path = os.path.join(os.getcwd(), "assets", "fonts", "LICENSE_Pretendard.txt")
        if os.path.exists(license_path):
            try:
                with open(license_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    license_text += "[라이센스 원문]\n" + content[:500] + "\n...(후략)"
            except:
                license_text += "라이센스 파일을 읽을 수 없습니다."
        else:
             license_text += "라이센스 파일이 'assets/fonts' 폴더 내에 존재하지 않습니다."
             
        ThemeMessageBox.information(self, "폰트 라이센스 정보", license_text)

    def on_log_clicked(self):
        """로그 파일 열기"""
        import os
        from src.utils.utils_logger import LOG_DIR
        
        log_file = os.path.join(LOG_DIR, "app.log")
        if os.path.exists(log_file):
            try:
                os.startfile(log_file) # 윈도우 기본 텍스트 뷰어로 열기
            except Exception as e:
                ThemeMessageBox.warning(self, "오류", f"로그 파일을 열 수 없습니다:\n{e}")
        else:
            # 아직 로그 파일이 없는 경우 (첫 실행 등) 폴더라도 열어줌
            if os.path.exists(LOG_DIR):
                 os.startfile(LOG_DIR)
            else:
                 ThemeMessageBox.information(self, "알림", "아직 생성된 로그가 없습니다.")