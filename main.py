# main.py (Part 1/3)
"""
YDManager - Video Organization & Playback System
------------------------------------------------
Author: User / Assistant
Version: 8.1 (Refactored & Optimized)
Description: 
    Main entry point for the Video Sorter application. 
    Handles UI orchestration, media playback control, and user interactions.
"""
import winreg
import ctypes
import sys
import os
import random
from typing import Optional, List, Tuple
from BlurWindow.blurWindow import GlobalBlur

# --- Third Party Imports ---
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QListWidgetItem, QAbstractItemView
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, Qt, QTimer, QEvent, QSizeF, QObject
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QFont

# --- Local Module Imports ---
from src.ui import styles 
from src.ui.styles import Catppuccin, DARK_THEME
from src.ui.settings_ui import SettingsDialog
from src.managers.file_manager import FileManager
from src.managers.settings_manager import SettingsManager
from src.utils.utils_font import load_fonts
from src.ui.ui_layout import init_ui
from src.managers.player_manager import PlayerManager
from src.core.event_handler import ShortcutHandler, GlobalAppFilter
from src.core.signal_setup import setup_app_connections
from src.ui.ui_components import ThemeMessageBox, ProVideoView
from src.controllers.file_action_controller import FileActionController
from src.utils.utils_logger import get_logger, set_log_privacy_mode


logger = get_logger()


class VideoSorter(QMainWindow):
    """
    메인 애플리케이션 윈도우 클래스.
    UI 초기화, 이벤트 핸들링, 비즈니스 로직 연결을 담당합니다.
    """

    # =========================================================================
    # 1. Initialization & Configuration (초기화 및 설정)
    # =========================================================================

    def __init__(self):
        super().__init__()
        
        # 윈도우 배경 반투명 (BlurWindow 적용 준비)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        is_dark = self.sync_title_bar_theme()
        
        # [WinId 확보] 윈도우 핸들이 생성된 후 블러 적용
        self.show() 
        GlobalBlur(self.winId(), hexColor='#2E344030', Dark=is_dark, Acrylic=True)
        self.hide() # 초기화 중 깜빡임 방지용 (init_ui 후 다시 show됨)
        
        # [폰트 로드] UI 초기화 전에 폰트 준비
        load_fonts()

        # 설정 및 데이터 매니저 초기화
        self.settings = SettingsManager()
        self.file_manager = FileManager()
        
        # 윈도우 설정
        self.setAcceptDrops(True)
        self.load_config()

        # 상태 변수 초기화
        self.root_folder: str = "" 
        self.file_manager.main_files = [] 
        
        self.target_start_pos: int = 0      # 재생 시작 지점 (ms)
        self.is_waiting_for_seek: bool = False 
        
        self.last_played_path: Optional[str] = None 
        self.playback_rate: float = 1.0 
        self.last_main_row: int = 0         # 메인 목록 마지막 선택 행
        self.last_main_pos: int = 0         # 메인 목록 마지막 재생 위치
        self.last_main_path: Optional[str] = None 
        
        # 스레드 및 타이머 초기화
        self.codec_thread = None 
        
        # 자동 스캔 타이머
        self.scan_timer = QTimer()
        self.scan_timer.setInterval(500) 
        # [주의] execute_auto_scan은 Part 3에서 정의되므로 지금은 연결만 해둠
        self.scan_timer.timeout.connect(lambda: self.execute_auto_scan())

        # 프리로드 타이머 (버퍼링 최소화)
        self.preload_timer = QTimer()
        self.preload_timer.setSingleShot(True)
        self.preload_timer.timeout.connect(self._run_preload)

        # 탐색 안전 타이머 (화면 깜빡임 방지)
        self.seek_safety_timer = QTimer()
        self.seek_safety_timer.setSingleShot(True)
        self.seek_safety_timer.setInterval(1500) 
        self.seek_safety_timer.timeout.connect(self._force_show_screen)
        
        # [버그 수정] 검색 디바운스 타이머 (한글 조합형 입력 문제 해결)
        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.setInterval(400)  # 400ms 대기 (한글 조합 시간 고려)
        self.search_debounce_timer.timeout.connect(self._execute_search)
        
        # 키 이벤트 필터 핸들러
        self.shortcut_handler = ShortcutHandler(self)
        
        # [Shift 감지용 상태]
        self._is_shift_pressed = False
        self._is_shift_combined = False

        # UI 및 플레이어 매니저 구성
        init_ui(self)
        
        # 16:9 비율 강제 적용 (비동기 호출로 UI 생성 후 적용)
        QTimer.singleShot(0, self.apply_16_9_ratio)
        
        self.player_manager = PlayerManager(self.video_view, self.chk_audio)
        
        # [리팩토링] 파일 액션 컨트롤러 초기화
        self.file_action = FileActionController(self)
        
        # 시그널 연결 및 초기 상태 설정
        self.connect_signals()   
        self._connect_player_signals()
        
        # [FileManager 연결] 인덱싱 및 데이터 신호
        self.file_manager.indexing_data_received.connect(self.on_indexing_data_received)
        self.file_manager.indexing_finished.connect(self.on_indexing_finished)
        
        self.refresh_folder_history_ui()
        self.reset_viewer_state()
        self.update_trash_button_text()
        
        # 백그라운드 인덱싱 시작
        self.file_manager.start_indexing()
        
        # [ESC] 절대 0순위 종료 (어떤 포커스에 있든 작동 보장)
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.esc_shortcut.activated.connect(self.close)
        
        # 입력 포커스 설정
        self.setFocus()
        self.video_view.wheel_signal.connect(self.on_video_wheel)
        self.installEventFilter(self)
                
    @property
    def player(self) -> QMediaPlayer:
        """현재 활성화된 플레이어 객체를 반환합니다."""
        return self.player_manager.get_active_player()['player']

    @property
    def audio_output(self) -> QAudioOutput:
        """현재 활성화된 오디오 출력 객체를 반환합니다."""
        return self.player_manager.get_active_player()['audio']

    def set_window_icon(self) -> None:
        """애플리케이션 아이콘 및 Windows AppID 설정"""
        icon_path = os.path.join(os.getcwd(), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        if sys.platform == 'win32':
            myappid = 'mycompany.ydmanager.subproduct.02' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    def load_config(self) -> None:
        """SettingsManager에서 사용자 환경설정을 로드합니다."""
        try:
            self.conf_seek_interval = self.settings.seek_interval
            self.conf_auto_play = self.settings.auto_play
            self.conf_wheel_action = self.settings.wheel_action
            self.conf_wheel_interval = self.settings.wheel_interval
            self.conf_privacy_mode = self.settings.privacy_mode
            set_log_privacy_mode(self.conf_privacy_mode) # [보안] 로그 프라이버시 설정 동기화
            self.conf_wheel_reverse = self.settings.wheel_reverse

            self.conf_default_skip = self.settings.default_skip
        except Exception as e:
            print(f"Config load error: {e}")
            # 기본값 설정 (Fallback)
            self.conf_seek_interval = 2
            self.conf_auto_play = True
            self.conf_wheel_action = 0
            self.conf_wheel_interval = 5
            self.conf_privacy_mode = False # [보안] 기본값: 공개
            set_log_privacy_mode(False)
            self.conf_wheel_reverse = False

            self.conf_default_skip = "10%"

    def apply_16_9_ratio(self) -> None:
        """윈도우 크기를 16:9 비율에 맞춰 조정합니다."""
        left_panel_w = 230
        target_video_w = 1305
        target_video_h = 720
        extra_w, extra_h = 40, 80
        
        total_w = left_panel_w + target_video_w + extra_w
        total_h = target_video_h + extra_h
        
        self.resize(total_w, total_h)
        self.setMinimumSize(800, 600)
        self.set_window_icon()
        self.setWindowTitle("YDManager")
        
        self.splitter.setSizes([left_panel_w, target_video_w])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        
    def is_system_dark_mode(self):
        """윈도우 레지스트리를 읽어 현재 시스템이 다크 모드인지 확인합니다."""
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0이면 다크 모드, 1이면 라이트 모드
        except Exception:
            return True # 에러 발생 시 기본값은 다크 모드로 설정
        
    def sync_title_bar_theme(self):
        """시스템 설정에 맞춰 타이틀 바 테마를 동기화합니다."""
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20 
        hwnd = int(self.winId())
        
        dark_mode_active = self.is_system_dark_mode()
        value = ctypes.c_int(1 if dark_mode_active else 0)
        
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception as e:
            print(f"타이틀 바 동기화 실패: {e}")
        
        return dark_mode_active
        
    # =========================================================================
    # 2. Event Handlers (이벤트 핸들러)
    # =========================================================================

    def closeEvent(self, event) -> None:
        """애플리케이션 종료 시 자원 정리 시퀀스"""
        self.scan_timer.stop()
        
        # 1. 인덱싱 스레드 안전하게 종료 (FileManager 위임)
        if hasattr(self, 'file_manager'):
            self.file_manager.stop_indexing()

        # 2. 모든 플레이어 리소스 완전 해제 (파일 락 방지)
        if hasattr(self, 'player_manager'):
            self.player_manager.cleanup()
            
        # 3. 설정값 강제 저장 (휴지통 데이터 등)
        if hasattr(self, 'file_manager'):
            self.file_manager.save_trash()
            
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        
        # UI 렉 방지를 위한 Throttled Resize 적용
        if not hasattr(self, '_resize_timer'):
            self._resize_timer = QTimer()
            self._resize_timer.setSingleShot(True)
            self._resize_timer.setInterval(100) # 100ms 지연
            self._resize_timer.timeout.connect(self._delayed_resize)
        
        self._resize_timer.start()

    def _delayed_resize(self) -> None:
        if hasattr(self, 'player_manager') and hasattr(self, 'video_view'):
            new_size = QSizeF(self.video_view.size())
            self.player_manager.resize_all(new_size)

    # =========================================================================
    # 3. File & Folder Management (파일 및 폴더 관리)
    # =========================================================================

    def add_folder_by_path(self, path: str) -> None:
        """탐색기에서 드롭된 경로를 목록에 추가합니다."""
        if self.file_manager.add_folder_to_history(path):
            self.refresh_folder_history_ui() 
            self.file_manager.start_indexing()
            self.lbl_info.setText(f"새 폴더 추가됨: {os.path.basename(path)}")
        else:
            self.lbl_info.setText("이미 등록된 폴더입니다.")

    def on_indexing_data_received(self, chunk_list):
        """인덱싱 스레드로부터 데이터 청크를 받아 캐시를 업데이트합니다."""
        # UI 업데이트 방지 (성능 최적화)
        self.file_list.setUpdatesEnabled(False)
        try:
            # 1. 현재 검색어가 있다면 검색 결과 갱신
            if self.input_search.text():
                self.on_search_changed(self.input_search.text())

            # 2. [SYNC FIX] 현재 보고 있는 폴더에 파일이 추가되었다면 즉시 리로드
            # (단, 사용자가 스크롤 중이거나 하면 방해가 될 수 있어 신중해야 함.
            #  여기서는 단순하게 현재 폴더에 속한 파일이 청크에 있으면 리스트 재로딩)
            elif self.root_folder:
                current_norm = os.path.normpath(self.root_folder)
                needs_reload = False
                for item in chunk_list:
                    # item['folder'] 가 현재 폴더와 같다면
                    if os.path.normpath(item.get('folder', '')) == current_norm:
                        needs_reload = True
                        break
                
                if needs_reload:
                    # 전체 리로딩은 무거울 수 있으므로, 
                    # 현재 리스트에 없는 것만 추가하는 것이 좋으나
                    # 로직 단순화를 위해 load_files 호출 (이미 scan_folder에서 중복체크 함)
                    self.load_files()

        finally:
            self.file_list.setUpdatesEnabled(True)  

    def on_indexing_finished(self, count: int) -> None:
        """백그라운드 색인이 모두 완료되었을 때 호출됩니다."""
        self.lbl_info.setText(f"색인 완료: 총 {count}개 파일 스캔됨")
        if self.input_search.text():
            self.on_search_changed(self.input_search.text())

    def refresh_folder_history_ui(self) -> None:
        """폴더 히스토리 UI를 갱신합니다."""
        self.folder_list_widget.clear()
        history = self.file_manager.get_folder_history()
        for full_path in history:
            folder_name = os.path.basename(full_path) or full_path
            item = QListWidgetItem(f"≡  {folder_name}")
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            item.setToolTip(full_path)
            self.folder_list_widget.addItem(item)
            
    def on_folder_reordered(self) -> None:
        """폴더 리스트의 순서 변경 시 호출됩니다."""
        new_order = []
        for i in range(self.folder_list_widget.count()):
            item = self.folder_list_widget.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                new_order.append(path)
        self.file_manager.update_history_order(new_order)

    def load_files(self) -> None:
        """새로고침 시 호출되는 로직"""
        # 레거시 코덱 스레드 정리 (만약 있다면)
        if self.codec_thread and self.codec_thread.isRunning(): 
            self.codec_thread.stop()
        
        mode = self.file_manager.current_mode
        
        # 1. 모드별 데이터 로드
        if mode == 'trash': 
            self.file_manager.load_trash()
        elif mode == 'highlight': 
            self.file_manager.get_highlight_display_list()
        
        # 2. 실제 폴더 스캔 (여기서 정렬이 수행됨)
        if self.root_folder and os.path.isdir(self.root_folder):
            self.file_manager.scan_folder(self.root_folder)
        else:
            self.file_manager.main_files = []

        # 3. UI 업데이트 (정렬된 리스트 반영)
        self.update_ui_mode()

    # =========================================================================
    # 4. UI Mode & Filter Logic (뷰 모드 및 필터 로직)
    # =========================================================================

    def _change_view_mode(self, mode: str, filter_type: Optional[str] = None, is_trash: bool = False) -> None:
        """
        [Core Logic] 뷰 모드 변경 통합 관리 함수.
        모드 변경 시 필요한 상태 저장, 검색어 초기화, UI 갱신을 순차적으로 처리합니다.
        """
        # 1. 상태 저장 (메인 모드에서 나갈 때만)
        if self.file_manager.current_mode == 'main' and not self.file_manager.is_trash_mode:
            self.save_main_state()

        # 2. 검색어 및 UI 상태 강제 초기화 (상태 충돌 방지)
        self.input_search.blockSignals(True)
        self.input_search.clear()
        self.input_search.blockSignals(False)
        self.file_manager.set_search_keyword("")

        # 3. 모드 설정 적용
        self.file_manager.set_view_state(mode, filter_type, is_trash)
        
        # 버튼 상태 초기화
        self.btn_filter_a.setChecked(False)
        self.btn_filter_b.setChecked(False)
        
        # 4. UI 업데이트 실행
        self.update_ui_mode()

    def go_to_main_mode(self):
        # 이미 메인 모드라면 버튼만 체크하고 리턴
        if (self.file_manager.current_mode == 'main' and 
            not self.file_manager.is_trash_mode and 
            self.file_manager.filter_type is None):
            self.btn_main_list.setChecked(True)
            return
        self.btn_main_list.clearFocus()
        self._change_view_mode('main', None, False)
        

    def apply_filter(self, tag: str):
        # 같은 태그를 다시 누르면 상태 유지 (Toggle 아님)
        if self.file_manager.filter_type == tag:
            if tag == 'A': self.btn_filter_a.setChecked(True)
            else: self.btn_filter_b.setChecked(True)
            return 
        
        # 버튼 UI 반영
        if tag == 'A': self.btn_filter_a.setChecked(True)
        else: self.btn_filter_b.setChecked(True)
            
        self._change_view_mode('main', tag, False)

    def toggle_highlight_mode(self):
        if self.file_manager.current_mode == 'highlight':
            self.btn_highlight.setChecked(True)
            return
        self.file_manager.get_highlight_display_list() 
        self._change_view_mode('highlight', None, False)

    def toggle_trash_mode(self):
        if self.file_manager.is_trash_mode:
            self.btn_trash_mode.setChecked(True)
            return
        self._change_view_mode('trash', None, True)

    def update_ui_mode(self):
        """현재 상태(mode, filter)에 따라 파일 리스트와 UI 위젯을 갱신합니다."""
        mode = self.file_manager.current_mode
        f_type = self.file_manager.filter_type
        is_trash = self.file_manager.is_trash_mode
        
        if is_trash: target_mode = 'trash'
        elif mode == 'highlight': target_mode = 'highlight'
        elif f_type == 'A': target_mode = 'A'
        elif f_type == 'B': target_mode = 'B'
        else: target_mode = 'main'
        
        # 플레이어 모드 전환 (화면 레이어 정리)
        self.player_manager.switch_mode(target_mode)

        self.file_list.blockSignals(True)
        self.file_list.clear()
        
        current_list = self.file_manager.get_current_list()
        
        # 버튼 체크 상태 동기화
        self.btn_main_list.setChecked(target_mode == 'main')
        self.btn_highlight.setChecked(target_mode == 'highlight')
        self.btn_trash_mode.setChecked(target_mode == 'trash')
        self.btn_filter_a.setChecked(target_mode == 'A')
        self.btn_filter_b.setChecked(target_mode == 'B')
        
        self.update_trash_button_text()
        self._update_visible_widgets(mode, f_type, is_trash, len(current_list))

        # 검색창 표시 여부 제어
        should_show_search = (not is_trash and mode == 'main' and f_type is None)
        if self.input_search.isVisible() != should_show_search:
            self.input_search.setVisible(should_show_search)
            if not should_show_search:
                self.input_search.blockSignals(True) 
                self.input_search.clear()
                self.file_manager.set_search_keyword("")
                self.input_search.blockSignals(False)

        # 리스트 아이템 추가 (최적화)
        self.file_list.setUpdatesEnabled(False) # [최적화] 대량 데이터 렌더링 시 깜빡임 방지 및 속도 향상
        try:
            for item in current_list:
                prefix = "🗑️ " if is_trash else ""
                list_item = QListWidgetItem(f"{prefix}{item['text']}")
                list_item.setData(Qt.ItemDataRole.UserRole, item['path']) 
                if 'start_pos' in item:
                    list_item.setData(Qt.ItemDataRole.UserRole + 1, item['start_pos'])
                list_item.setForeground(Qt.GlobalColor.white)
                self.file_list.addItem(list_item) 
        finally:
            self.file_list.setUpdatesEnabled(True)

        # [버그 수정 코드 시작] -----------------------------------------------------
        # 화면이 'Main' 모드로 돌아왔을 때, 현재 보고 있는 폴더를 폴더 리스트에서 찾아 다시 선택해줍니다.
        if target_mode == 'main' and self.folder_list_widget.isVisible() and self.root_folder:
            norm_root = os.path.normpath(self.root_folder)
            found_folder = False
            for i in range(self.folder_list_widget.count()):
                f_item = self.folder_list_widget.item(i)
                f_path = f_item.data(Qt.ItemDataRole.UserRole)
                if f_path and os.path.normpath(f_path) == norm_root:
                    self.folder_list_widget.setCurrentRow(i) # 강제 선택
                    f_item.setSelected(True)
                    self.folder_list_widget.scrollToItem(f_item)
                    found_folder = True
                    break
            
            # 만약 못 찾았다면(삭제됨 등) 선택 해제
            if not found_folder:
                self.folder_list_widget.clearSelection()
                self.folder_list_widget.setCurrentRow(-1)
        # [버그 수정 코드 끝] -------------------------------------------------------

        # 스크롤 이동 및 자동 재생 로직
        if self.file_list.count() > 0:
            self.video_view.set_progressbar_visible(True)
            
            # 검색 중이라면 재생하지 않고 리스트만 갱신
            if self.input_search.hasFocus():
                self.file_list.blockSignals(False)
                return 

            if target_mode == 'main':
                # 이전 위치 기억 후 복원
                target_row = 0
                if self.last_main_path:
                    for i in range(self.file_list.count()):
                        if self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == self.last_main_path:
                            target_row = i; break
                else:
                    target_row = max(0, min(self.last_main_row, self.file_list.count() - 1))
                
                self.file_list.setCurrentRow(target_row)
                
                # [UX] 선택된 아이템을 화면 중앙으로 스크롤
                currentItem = self.file_list.item(target_row)
                self.file_list.scrollToItem(currentItem, QAbstractItemView.ScrollHint.PositionAtCenter)
                
                start_pos = self.last_main_pos if self.last_main_pos > 0 else 0
                # play_video는 3단계에서 정의되지만 호출은 가능
                self.play_video(target_row, specific_start_pos=start_pos)
            else:
                self.file_list.setCurrentRow(0)
                self.play_video(0)
        else:
            self.video_view.set_progressbar_visible(False)
            self.reset_viewer_state()
            
        self.file_list.blockSignals(False)

    def _update_visible_widgets(self, mode, f_type, is_trash, list_count):
        """UI 요소들의 가시성(Visibility)을 상태에 맞춰 토글합니다."""
        show_tag_a = (not is_trash and mode == 'main' and f_type == 'A')
        show_tag_b = (not is_trash and mode == 'main' and f_type == 'B')
        show_highlight_clear = (mode == 'highlight')
        
        if self.btn_clear_tag_a.isVisible() != show_tag_a:
            self.btn_clear_tag_a.setVisible(show_tag_a)
        if self.btn_clear_tag_b.isVisible() != show_tag_b:
            self.btn_clear_tag_b.setVisible(show_tag_b)
        if self.btn_clear_highlight.isVisible() != show_highlight_clear:
            self.btn_clear_highlight.setVisible(show_highlight_clear)
            
        is_searching = bool(self.input_search.text().strip())

        if is_trash:
            self.folder_list_widget.hide()
            self.file_list.set_watermark("[ 휴지통 ]", Catppuccin.RED, 60)
            self.lbl_info.setText(f" {list_count}개")
            self.btn_mark.hide(); self.btn_soft_delete.hide()
            self.btn_add_highlight.hide(); self.btn_del_highlight.hide(); self.btn_replay_highlight.hide()
            self.btn_restore.show(); self.btn_restore_all.show() 
            self.btn_del_selected.show(); self.btn_del_all.show()
            
        elif mode == 'highlight':
            self.folder_list_widget.hide()
            self.file_list.set_watermark("[ 하이라이트 ]", Catppuccin.MAUVE, 60)
            self.lbl_info.setText(f"하이라이트: {list_count}개 저장됨")
            self.btn_mark.hide(); self.btn_soft_delete.hide(); self.btn_restore.hide()
            self.btn_add_highlight.hide(); self.btn_restore_all.hide()
            self.btn_del_selected.hide(); self.btn_del_all.hide()
            self.btn_replay_highlight.show(); self.btn_del_highlight.show()
        else:
            # 태그 필터가 있거나, '검색 중'이면 폴더 리스트를 숨김
            if f_type or is_searching: 
                self.folder_list_widget.hide()
                
                if f_type:
                    w_color = (Catppuccin.YELLOW) if f_type == 'A' else (Catppuccin.BLUE)
                    self.file_list.set_watermark(f"[ {f_type}급 모아보기 ]", w_color, 60)
                    self.lbl_info.setText(f"{f_type}급 태그: 총 {list_count}개 검색됨")
                else:
                    self.file_list.set_watermark("") 
                    self.lbl_info.setText(f"검색 결과: {list_count}개")
            else:
                self.folder_list_widget.show()
                self.file_list.set_watermark("")
                self.lbl_info.setText(f"목록: {list_count}개")
            
            self.btn_mark.show(); self.btn_soft_delete.show(); self.btn_add_highlight.show()
            self.btn_restore.hide(); self.btn_del_highlight.hide(); self.btn_replay_highlight.hide() 
            self.btn_restore_all.hide(); self.btn_del_selected.hide(); self.btn_del_all.hide()

    def _apply_privacy_visibility(self, is_playing: bool):
        """프라이버시 모드 시 UI와 타이틀 바의 파일명을 모두 숨깁니다."""
        is_privacy_on = getattr(self, 'conf_privacy_mode', False)
        privacy_active = is_privacy_on and not is_playing

        if privacy_active:
            # 1. UI 및 마우스 차단
            self.splitter.hide()
            self.video_view.set_privacy_screen(True)
            self.setWindowTitle("YDManager") 
            self.setFocus()
        else:
            # 1. UI 복구
            self.splitter.show()
            self.video_view.set_privacy_screen(False)
            
            # 2. 타이틀 바 제목 복구
            curr_source = self.player.source().toLocalFile()
            if curr_source:
                self.setWindowTitle(f"재생: {os.path.basename(curr_source)}")
            else:
                self.setWindowTitle("YDManager")
            
    # =========================================================================
    # 5. Playback Logic (재생 로직)
    # =========================================================================
    
    def update_timer_state(self):
        """[통합 관리] 재생 상태와 옵션에 따라 타이머(오토스캔) 제어"""
        is_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        is_autoscan_enabled = self.chk_autoscan.isChecked()
        
        if is_playing and is_autoscan_enabled:
            if not self.scan_timer.isActive(): self.scan_timer.start()
        else:
            self.scan_timer.stop()

    def toggle_play(self):
        """재생/일시정지 토글 (방어 로직 강화)"""
        # 1. 현재 재생 중이면 일시 정지
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self._apply_privacy_visibility(False)
        else:
            # 2. 정지 상태면 재생 시도
            # 소스가 없으면 현재 선택된 파일이나 첫 번째 파일 재생 시도
            if self.player.source().isEmpty():
                if self.file_list.count() > 0:
                    row = self.file_list.currentRow()
                    if row < 0: row = 0
                    self.play_video(row)
                else:
                    logger.debug("재생할 파일이 없습니다.")
                    return

            self.player.play()
            self._apply_privacy_visibility(True)
            
        self.update_timer_state()

    def toggle_autoscan(self, checked):
        self.update_timer_state()
        if checked: 
            self.video_view.show_temp_message("자동 건너뛰기 활성화")

    def execute_auto_scan(self):
        """[중복 제거됨] 설정된 비율만큼 건너뛰기 실행"""
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState: return
        dur = self.player.duration()
        if dur <= 0: return
        
        step = max(1000, int(dur * self.get_skip_ratio()))
        next_pos = self.player.position() + step
        
        # 영상 끝을 넘어가면 0으로, 아니면 이동
        self.player.setPosition(0 if next_pos >= dur else next_pos)

    def play_video(self, index: int, specific_start_pos: Optional[int] = None) -> None:
        """[Entry] 비디오 재생 메인 진입점. 끊김 없는 재생 보장."""
        # 1. 검증 및 준비
        target_path, item_widget = self._prepare_playback(index)
        if not target_path:
            return

        # 2. 시작 위치 결정 (가장 먼저 수행해야 같은 파일일 때도 이동 가능)
        self.target_start_pos = self._resolve_start_pos(item_widget, specific_start_pos)

        # [중요] 현재 재생 중인 소스와 같다면 리로드 방지 (단, 명시적 위치 이동은 허용)
        current_source = self.player.source().toLocalFile()
        if current_source and os.path.normpath(current_source) == os.path.normpath(target_path):
            # [버그 수정] 같은 파일이라도 목표 위치가 다르면 이동 (하이라이트 등)
            if self.target_start_pos != -1: # 랜덤(-1)이 아닐 때
                # 1초 이상 차이나면 이동 (불필요한 점프 방지)
                if abs(self.player.position() - self.target_start_pos) > 1000:
                    self.player.setPosition(self.target_start_pos)
            
            if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self.player.play()
            return

        # 3. 플레이어 할당 및 상태 정리
        active_data = self.player_manager.prepare_player_for_path(target_path)
        self._sync_player_layers(active_data)

        # 4. 실제 재생 실행
        self._execute_media_load(active_data, target_path)

    def _prepare_playback(self, index: int) -> Tuple[Optional[str], Optional[QListWidgetItem]]:
        self.scan_timer.stop()
        self.preload_timer.stop()
        self.seek_safety_timer.stop()
        self.is_waiting_for_seek = False
        
        if index < 0 or index >= self.file_list.count():
            return None, None
            
        item = self.file_list.item(index)
        path = item.data(Qt.ItemDataRole.UserRole)
        return path, item

    def _resolve_start_pos(self, item, specific_pos) -> int:
        if specific_pos is not None:
            return specific_pos
        if self.chk_random.isChecked():
            return -1  # 랜덤 신호
        
        saved_pos = item.data(Qt.ItemDataRole.UserRole + 1)
        return int(saved_pos) if saved_pos is not None else 0

    def _sync_player_layers(self, active_data: dict):
        """[버그 수정] 파일 전환 시 이전 플레이어를 확실히 정지시킵니다."""
        current_mode = self.player_manager.current_mode
        pool = self.player_manager.pools[current_mode]
        
        # [DEBUG] 플레이어 교체 로그
        active_idx = pool.index(active_data)
        # print(f"[DEBUG] _sync_player_layers: Active Player -> {active_idx}")
        
        for i, p_data in enumerate(pool):
            player = p_data['player']
            
            if p_data == active_data:
                # 새로 활성화될 플레이어 설정
                player.blockSignals(False)
                p_data['audio'].setMuted(not self.chk_audio.isChecked())
                p_data['item'].setZValue(20.0)  # 주인공은 맨 위로
            else:
                # [핵심 수정] 이전 플레이어를 즉시 정지 및 화면 숨김
                # print(f"[DEBUG]   Killing Player {i}: {p_data['path']}")
                player.blockSignals(True)
                player.stop()
                player.setSource(QUrl())  # 소스 해제
                p_data['audio'].setMuted(True)
                p_data['item'].setOpacity(0.0)
                p_data['item'].setZValue(0.0)
                p_data['path'] = None

    def _execute_media_load(self, active_data: dict, target_path: str):
        """[수정됨] 자동 재생 해제 시에도 화면이 나오도록 강제 렌더링 및 안전장치 가동"""
        norm_path = os.path.normpath(target_path)
        curr_path = os.path.normpath(active_data['path']) if active_data['path'] else ""
        
        self.video_view.set_info_visible(False)
        is_playing = self.conf_auto_play
        is_privacy_on = getattr(self, 'conf_privacy_mode', False)
        
        if is_privacy_on and not is_playing:
            self.setWindowTitle("YDManager")
        else:
            self.setWindowTitle(f"재생: {os.path.basename(target_path)}")

        # [1] 경로 변경 여부에 따른 분기
        if norm_path != curr_path:
            # 새로운 파일: 로딩 전까지 숨김 (깜빡임 방지)
            active_data['path'] = target_path
            active_data['item'].setOpacity(0.0) 
            active_data['player'].setSource(QUrl.fromLocalFile(target_path))
            
            # [Fix 1] 신호가 안 올 경우를 대비해 안전장치 타이머 가동 (최대 1.5초 뒤 강제 표시)
            self.seek_safety_timer.start()
        else:
            # 프리로드 적중: 이미 로드된 상태면 바로 표시
            status = active_data['player'].mediaStatus()
            if status in [QMediaPlayer.MediaStatus.BufferedMedia, QMediaPlayer.MediaStatus.LoadedMedia]:
                 active_data['item'].setOpacity(1.0)
        
        active_data['player'].setPlaybackRate(self.playback_rate)
        
        # [2] 재생 또는 정지 상태 처리
        if self.target_start_pos != 0:
            # 저장된 위치나 랜덤 위치로 이동하는 경우
            if active_data['player'].duration() > 0:
                self._handle_immediate_seek(active_data)
            else:
                # 메타데이터가 아직 로드되지 않았다면 시그널을 기다림
                self.is_waiting_for_seek = True
                self.seek_safety_timer.start()
        else:
            # 처음부터 재생하는 경우
            if self.conf_auto_play:
                active_data['player'].play()
            else:
                # [Fix 2] 자동 재생이 꺼져 있어도 0초 위치로 강제 이동하여 첫 프레임 렌더링 유도
                active_data['player'].setPosition(0)
                # 만약 로딩이 매우 빠르면 여기서 바로 보여주기 위해 타이머 체크
                if active_data['player'].mediaStatus() == QMediaPlayer.MediaStatus.LoadedMedia:
                     active_data['item'].setOpacity(1.0)

        if self.chk_autoscan.isChecked():
            self.scan_timer.start()
        self.preload_timer.start(50)

    def _handle_immediate_seek(self, active_data):
        if self.target_start_pos == -1:
            dur = active_data['player'].duration()
            pos = random.randint(int(dur*0.1), int(dur*0.9))
            self._execute_seek_and_play(pos)
        else:
            self._execute_seek_and_play(self.target_start_pos)

    def _execute_seek_and_play(self, target_pos: int) -> None:
        self.is_waiting_for_seek = True
        self._pending_seek_pos = target_pos 
        self.seek_safety_timer.start()
        self.player.setPosition(target_pos)
        
        if self.conf_auto_play and self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.player.play()
            
        if self.chk_autoscan.isChecked(): 
            self.scan_timer.start()
            
    def preload_next_file(self, current_index: int) -> None:
        """다음/이전 영상을 백그라운드 플레이어에 미리 로드"""
        if self.file_list.count() == 0: return 
        
        next_idx = current_index + 1 if current_index + 1 < self.file_list.count() else -1
        prev_idx = current_index - 1 if current_index - 1 >= 0 else -1
        
        targets = []
        is_random = self.chk_random.isChecked()

        for idx in [next_idx, prev_idx]:
            if idx != -1:
                item = self.file_list.item(idx)
                if item is None: continue

                path = item.data(Qt.ItemDataRole.UserRole)
                if not path: continue

                if is_random:
                    target_pos = -1 
                else:
                    saved_pos = item.data(Qt.ItemDataRole.UserRole + 1)
                    target_pos = int(saved_pos) if saved_pos is not None else 0
                    
                targets.append((path, target_pos))

        idle_indices = self.player_manager.get_idle_players()
        
        for path, pos in targets:
            if not idle_indices: break 
            
            already_has = -1
            for idx in idle_indices:
                p_data = self.player_manager.get_player_by_index(idx)
                if p_data['path'] and os.path.normpath(p_data['path']) == os.path.normpath(path):
                    already_has = idx; break
            
            if already_has != -1:
                idle_indices.remove(already_has)
                continue
            
            worker_idx = idle_indices.pop(0)
            p_data = self.player_manager.get_player_by_index(worker_idx)
            
            p_data['item'].setOpacity(0.0)
            p_data['audio'].setMuted(True)
            p_data['path'] = path
            p_data['player'].setSource(QUrl.fromLocalFile(path))
            p_data['player'].pause() 
            
            if pos > 0:
                p_data['player'].setPosition(pos)

    def _run_preload(self):
        # 현재 재생 중인 인덱스 기준으로 프리로드
        curr_row = self.file_list.currentRow()
        if curr_row >= 0:
            self.preload_next_file(curr_row)
            
    def _force_show_screen(self):
        """탐색 지연 시 강제로 화면 표시"""
        if self.is_waiting_for_seek:
            self.is_waiting_for_seek = False
            active_data = self.player_manager.get_active_player()
            if active_data:
                active_data['item'].setOpacity(1.0)
                
    def on_clear_all_tags(self, tag_type: str) -> None:
        """[위임] 특정 태그 전체 초기화"""
        self.file_action.on_clear_all_tags(tag_type)
            
    def on_clear_all_highlights(self) -> None:
        """[위임] 하이라이트 전체 초기화"""
        self.file_action.on_clear_all_highlights()

    # =========================================================================
    # 6. Signal Slots (시그널 슬롯)
    # =========================================================================

    def on_media_status_changed(self, status):
        sender_player = self.sender()
        active_p = self.player_manager.get_active_player()['player']
        if sender_player != active_p:
            return

        if status in [QMediaPlayer.MediaStatus.BufferedMedia, QMediaPlayer.MediaStatus.LoadedMedia]:
            active_data = self.player_manager.get_active_player()
            if active_data:
                active_data['item'].setOpacity(1.0)
                active_data['item'].setZValue(10.0)
                
                # 다른 플레이어 숨김 및 완전 정지
                idle_indices = self.player_manager.get_idle_players()
                current_source = active_data['player'].source().toLocalFile()
                for idx in idle_indices:
                    p_data = self.player_manager.get_player_by_index(idx)
                    # [Fix] 현재 재생 중인 파일과 동일한 경로면 해제하지 않음
                    if p_data['path'] and current_source and os.path.normpath(p_data['path']) == os.path.normpath(current_source):
                        continue
                    # [Fix] 로딩 중인 플레이어는 건드리지 않음 (프리로드 보호)
                    if p_data['player'].mediaStatus() == QMediaPlayer.MediaStatus.LoadingMedia:
                        continue
                    p_data['item'].setOpacity(0.0)
                    p_data['item'].setZValue(0.0)
                    p_data['player'].stop()
                    p_data['player'].setSource(QUrl())  # 소스 해제
                    p_data['path'] = None  # 경로 초기화

            sender_player.setPlaybackRate(self.playback_rate)
            self.video_view.set_duration(self.player.duration())
            
            # 지속 재생 로직
            if self.target_start_pos == -1: 
                if self.player.duration() > 0:
                    rand_pos = random.randint(0, int(self.player.duration() * 0.90))
                    self._execute_seek_and_play(rand_pos)
                else:
                    self._force_show_screen()
            elif self.target_start_pos > 0: 
                 self._execute_seek_and_play(self.target_start_pos)

    def on_position_changed(self, position):
        if self.player.duration() <= 0: return
        self.video_view.set_position(position)
        
        if self.is_waiting_for_seek:
            target = getattr(self, '_pending_seek_pos', -1)
            if target != -1 and abs(position - target) < 1000:
                active_data = self.player_manager.get_active_player()
                if active_data:
                    active_data['item'].setOpacity(1.0)
                
                self.is_waiting_for_seek = False
                self.seek_safety_timer.stop()
                
                if self.conf_auto_play and self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                    self.player.play()

    def on_duration_changed(self, duration): 
        if self.sender() == self.player and duration > 0:
            self.video_view.set_duration(duration)

    def on_search_changed(self, text):
        """검색어 입력 시 호출 (검색어가 비어지면 즉시 복원)"""
        # 검색어가 비어지면 즉시 전체 목록으로 복원
        if not text.strip():
            self.file_manager.set_search_keyword('')
            if self.root_folder:
                self.file_manager.scan_folder(self.root_folder)
            
            # [버그 수정] 현재 재생 중인 파일의 경로 저장
            current_playing_path = self.player.source().toLocalFile()
            
            self.update_ui_mode()
            
            # [버그 수정] 현재 재생 중인 파일을 리스트에서 찾아 선택
            if current_playing_path:
                self.file_list.blockSignals(True)  # 선택 시 재생이 다시 시작되지 않도록
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    if item and os.path.normpath(item.data(Qt.ItemDataRole.UserRole)) == os.path.normpath(current_playing_path):
                        self.file_list.setCurrentRow(i)
                        self.file_list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                        break
                self.file_list.blockSignals(False)
            
            self.lbl_info.setText("검색어 지움 (전체 목록)")
    
    def on_search_submitted(self):
        """[신규] Enter 키로 검색 실행"""
        text = self.input_search.text().strip()
        
        logger.debug(f"Search Submitted: '{text}'")
        
        self.file_manager.set_search_keyword(text)
        
        if not text and self.root_folder:
            self.file_manager.scan_folder(self.root_folder)
        
        self.update_ui_mode()
        count = self.file_list.count()
        
        logger.debug(f"Search Result: {count} items found")
        
        if text:
            self.lbl_info.setText(f"검색 결과: {count}개")
        else:
            self.lbl_info.setText("검색어 지움 (전체 목록)")
    
    def _execute_search(self):
        """실제 검색 실행 (디바운스 후 호출됨) - 레거시 호환용"""
        text = getattr(self, '_pending_search_text', '')
        
        if text and len(text) < 2:
            return
        
        self.file_manager.set_search_keyword(text)
        
        if not text and self.root_folder:
            self.file_manager.scan_folder(self.root_folder)
        
        self.update_ui_mode()
        count = self.file_list.count()
        
        if text:
            self.lbl_info.setText(f"검색 결과: {count}개")
        else:
            self.lbl_info.setText("검색어 지움 (전체 목록)")

    def on_folder_selection_changed(self, current, previous):
        if current and self.folder_list_widget.hasFocus():
            self.on_folder_history_clicked(current)

    def on_folder_history_clicked(self, item):
        full_path = item.data(Qt.ItemDataRole.UserRole)
        
        if os.path.isdir(full_path):
            self.player_manager.stop_all_in_mode('main')
            
            self.last_main_row = 0
            self.last_main_pos = 0
            self.last_main_path = None 
            self.target_start_pos = 0
            
            self.root_folder = full_path
            self.load_files()
            self.lbl_info.setText(f"로드됨: {os.path.basename(full_path)}")
            self.folder_list_widget.setFocus()
            pass
        else:
            ThemeMessageBox.warning(self, "오류", f"폴더를 찾을 수 없습니다.\n{full_path}")

    def on_current_item_changed(self, current, previous):
        if not current: return
        self.target_start_pos = 0 
        row = self.file_list.row(current)
        self.play_video(row)

    # =========================================================================
    # 7. Button & Action Implementation (기능 구현)
    # =========================================================================

    def open_settings(self):
        dlg = SettingsDialog(self, self.file_manager)
        if dlg.exec():
            dlg.save_settings() 
            self.load_config() 
            self.video_view.show_temp_message("환경설정이 적용되었습니다")

            if not self.file_manager.get_folder_history():
                self.root_folder = ""
                self.file_list.clear()
                self.reset_viewer_state()
                self.lbl_info.setText("상태: 준비됨")
            else:
                if self.file_manager.current_mode == 'main':
                    self.save_main_state()
                self.refresh_folder_history_ui()
                self.update_ui_mode()
        self.video_view.set_info_visible(True)

    def reset_viewer_state(self):
        if hasattr(self, 'player_manager'):
            active_data = self.player_manager.get_active_player()
            if active_data:
                active_data['player'].stop()
                active_data['player'].setSource(QUrl())
                active_data['item'].setOpacity(0.0)

        if hasattr(self, 'lbl_info'):
            self.lbl_info.setText("상태: 준비됨")

        if hasattr(self, 'video_view') and hasattr(self.video_view, 'info_text'):
            self.video_view.info_text.setVisible(True)
            self.video_view.set_progressbar_visible(False)
                
    def update_trash_button_text(self):
        count = len(self.file_manager.trash_files)
        self.btn_trash_mode.setText("")
        self.btn_trash_mode.setToolTip(f"휴지통 ({count}개 파일)")

    def save_main_state(self):
        if self.file_manager.current_mode == 'main' and self.file_manager.filter_type is None:
            self.last_main_row = self.file_list.currentRow()
            self.last_main_pos = self.player.position()
            
            item = self.file_list.currentItem()
            if item:
                self.last_main_path = item.data(Qt.ItemDataRole.UserRole)
            else:
                self.last_main_path = None

    def soft_delete_file(self):
        """[위임] 선택된 파일을 휴지통으로 이동"""
        self.file_action.soft_delete_file()

    def hard_delete_file(self):
        """[위임] 선택된 파일을 영구 삭제"""
        self.file_action.hard_delete_file()

    def restore_file(self):
        """[위임] 휴지통 파일 복원"""
        self.file_action.restore_file()

    def restore_all_files(self):
        """[위임] 휴지통 전체 복원"""
        self.file_action.restore_all_files()    

    def delete_all_trash_files(self):
        """[위임] 휴지통 비우기"""
        self.file_action.delete_all_trash_files()

    def toggle_hash_mark(self):
        """[위임] 파일명에 # 추가/제거"""
        self.file_action.toggle_hash_mark()

    def save_current_highlight(self):
        """[위임] 현재 위치 하이라이트 저장"""
        self.file_action.save_current_highlight()

    def delete_current_highlight_item(self):
        """[위임] 현재 하이라이트 삭제"""
        self.file_action.delete_current_highlight_item()

    def replay_current_highlight(self):
        """[위임] 현재 하이라이트 재생"""
        self.file_action.replay_current_highlight()

    def toggle_tag_file(self, tag_char):
        """[위임] 파일에 A/B 태그 토글"""
        self.file_action.toggle_tag_file(tag_char)

    def auto_play_next(self, row):
        current_len = self.file_list.count()
        if row < current_len: 
            self.file_list.setCurrentRow(row)
            self.play_video(row)
        elif current_len > 0: 
            self.file_list.setCurrentRow(current_len - 1)
            self.play_video(current_len - 1)
        else: 
            self.reset_viewer_state()
            self.setWindowTitle("Pro 동영상 플레이어")

    def delete_folder_history_item(self):
        row = self.folder_list_widget.currentRow()
        if row >= 0:
            removed_path = self.file_manager.remove_folder_from_history(row)
            self.refresh_folder_history_ui()
            if removed_path:
                self.lbl_info.setText(f"삭제됨: {os.path.basename(removed_path)}")
                
                # 현재 보고 있는 폴더가 삭제되었으면 초기화
                current_viewing = os.path.normpath(self.root_folder) if self.root_folder else ""
                if current_viewing == os.path.normpath(removed_path) or not self.file_manager.get_folder_history():
                    self.file_list.clear() 
                    self.reset_viewer_state()
                    
                if self.input_search.text():
                    self.on_search_changed(self.input_search.text())
            
    def toggle_audio(self, checked): 
        self.audio_output.setMuted(not checked)

    def get_skip_ratio(self):
        try: return int(self.combo_skip.currentText().replace('%', '')) / 100.0
        except: return 0.1

    def change_playback_rate(self, delta):
        new_rate = max(1.0, min(10.0, self.playback_rate + delta))
        self.playback_rate = round(new_rate, 1)
        self.player.setPlaybackRate(self.playback_rate)
        self.video_view.show_temp_message(f"<div style='font-size:30px;color:white;background:rgba(0,0,0,0.6);padding:10px;'>⚡ x {int(self.playback_rate)}</div>")

    def reset_playback_rate(self):
        self.playback_rate = 1.0
        self.player.setPlaybackRate(1.0)
        self.video_view.show_temp_message(f"<div style='font-size:30px;color:white;background:rgba(0,0,0,0.6);padding:10px;'>▶ x 1.0</div>")

    def move_selection(self, delta):
        count = self.file_list.count()
        if count == 0: return
        current = self.file_list.currentRow()
        self.file_list.setCurrentRow(max(0, min(current + delta, count - 1)))

    def on_video_clicked(self, ratio):
        dur = self.player.duration()
        if dur <= 0: return

        self.is_waiting_for_seek = False
        self.seek_safety_timer.stop()
        
        active_data = self.player_manager.get_active_player()
        if active_data:
            active_data['item'].setOpacity(1.0)

        target_pos = int(dur * ratio)
        self.player.setPosition(target_pos)
        
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.player.play()
            if self.chk_autoscan.isChecked(): self.scan_timer.start()

    def on_video_wheel(self, delta):
        if self.conf_wheel_action == 0:
            current_row = self.file_list.currentRow()
            if delta < 0: new_row = current_row + 1 
            else: new_row = current_row - 1        
            
            if 0 <= new_row < self.file_list.count():
                self.file_list.setCurrentRow(new_row)
        else:
            if self.player.duration() <= 0: return
            
            current_pos = self.player.position()
            step = self.conf_wheel_interval * 1000 
            
            is_forward = (delta < 0) 
            if self.conf_wheel_reverse:
                is_forward = not is_forward

            if is_forward:
                target = min(current_pos + step, self.player.duration())
            else:
                target = max(current_pos - step, 0)
            
            self.player.setPosition(target)

    # =========================================================================
    # 8. Event Filtering (이벤트 필터링)
    # =========================================================================
    
    def connect_signals(self):
        """
        [Refactoring] 모든 시그널 연결 로직을 별도 모듈(setup_app_connections)로 위임했습니다.
        """
        setup_app_connections(self)

    def _connect_player_signals(self):
        for mode in self.player_manager.pools:
            for p_data in self.player_manager.pools[mode]:
                player = p_data['player']
                player.mediaStatusChanged.connect(self.on_media_status_changed)
                player.positionChanged.connect(self.on_position_changed)
                player.durationChanged.connect(self.on_duration_changed)
                
    def reset_all_ui(self):
        """모든 UI 요소와 상태를 초기화합니다."""
        # 1. 실행 중인 기능 정지
        self.scan_timer.stop()
        self.player.stop()
        
        # 2. 내부 변수 초기화
        self.root_folder = ""
        self.last_main_row = 0
        self.last_main_pos = 0
        self.last_main_path = None
        
        # 3. UI 리스트 비우기
        self.folder_list_widget.clear()
        self.file_list.clear()
        self.input_search.blockSignals(True)
        self.input_search.clear()
        self.input_search.blockSignals(False)
        
        # 4. 플레이어 및 정보창 초기화
        self.reset_viewer_state()
        self.lbl_info.setText("상태: 초기화됨 (모든 데이터 삭제 완료)")
        self.setWindowTitle("YDManager")

    def eventFilter(self, source, event):
        """로직을 직접 처리하지 않고 ShortcutHandler에 위임합니다."""
        
        # [Shift 단독 실행 로직] - 검색창 바로가기
        if event.type() == QEvent.Type.KeyPress:
             if event.key() == Qt.Key.Key_Shift:
                 self._is_shift_pressed = True
                 self._is_shift_combined = False
             elif self._is_shift_pressed:
                 # Shift 누른 상태에서 다른 키 입력됨 -> 단독 실행 무효화
                 self._is_shift_combined = True
                 
        elif event.type() == QEvent.Type.KeyRelease:
             if event.key() == Qt.Key.Key_Shift:
                 # Shift만 눌렀다 뗏고 + 검색창이 아닐 때
                 if self._is_shift_pressed and not self._is_shift_combined:
                     if source is not self.input_search:
                         self.focus_search_input()
                 self._is_shift_pressed = False
        
        if self.shortcut_handler.process_event(source, event):
            return True
            
        return super().eventFilter(source, event)

    def focus_search_input(self):
        """검색창으로 포커스를 이동하고 텍스트를 전체 선택합니다."""
        self.input_search.setFocus()
        self.input_search.selectAll()
    
# -----------------------------------------------------------------------------
# [New] 전역 이벤트 필터 클래스 (모든 창보다 우선순위 높음)
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    # [High DPI 설정] 폰트가 자글거리는 현상 방지 (QApplication 생성 전 필수)
    # [Logging System]
    from src.utils.utils_logger import setup_logging, get_logger
    logger = setup_logging()
    
    # [High DPI 설정]
    # 4K 모니터에서 글자가 흐릿하게 보이는 문제를 해결하기 위해 PassThrough 정책 사용
    # * 중요: 'PreferNoHinting'과 함께 사용하여 macOS 스타일의 부드러운 렌더링 유도
    # os.environ["QT_FONT_DPI"] = "96" # [제거] 스마트 렌더링을 위해 고정값 제거
    
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    
    # [Smart Font Rendering] 모니터 해상도에 따른 자동 최적화
    screen = app.primaryScreen()
    dpi = screen.logicalDotsPerInch()
    pixel_ratio = screen.devicePixelRatio()
    
    logger.info(f"Display Detected - DPI: {dpi}, Pixel Ratio: {pixel_ratio}")

    logger.info(f"Display Detected - DPI: {dpi}, Pixel Ratio: {pixel_ratio}")

    font = app.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

    # [사용자 요청 반영] 해상도 관계없이 항상 부드러운 렌더링(Soft & Smooth) 적용
    # Crisp & Sharp(VerticalHinting)는 가독성이 떨어질 수 있음
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    logger.info("Applying Global Settings: PreferNoHinting (Soft & Smooth) - Forced by User")

    app.setFont(font)

    # 전역 폰트 로드 (여기서 Pretendard 등이 로드됨)
    try:
        load_fonts()
    except Exception as e:
        logger.error(f"Failed to load fonts: {e}")

    # 전역 이벤트 필터 (ESC 종료 등)
    app_filter = GlobalAppFilter()
    app.installEventFilter(app_filter)

    # 스타일 적용
    app.setStyleSheet(styles.GLOBAL_STYLE)

    # 메인 윈도우 실행
    ex = VideoSorter()
    ex.show() 

    logger.info("Application loop started")
    sys.exit(app.exec())