# ui_layout.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QCheckBox, QGroupBox, QComboBox, QSplitter, 
                             QLineEdit, QSizePolicy, QAbstractItemView, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction
from .ui_components import ProVideoView, PlaceholderListWidget, WatermarkListWidget
from .thumbnail_rail import ThumbnailPreviewRailWidget
from . import styles 
import qtawesome as qta

MENUHEIGHT = 30

def init_ui(window):
    """
    메인 윈도우의 UI 레이아웃을 초기화합니다.
    [Updated] qtawesome 아이콘을 mdi6(Material Design) 스타일로 전면 교체
    """
    # 1. 중앙 위젯 및 메인 레이아웃 설정
    central_widget = QWidget()
    central_widget.setObjectName("CentralWidget")
    window.setCentralWidget(central_widget)
    
    main_layout = QVBoxLayout(central_widget)
    main_layout.setContentsMargins(5, 5, 5, 5)
    main_layout.setSpacing(5)
    
    central_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # 2. 메인 스플리터 (좌: 패널 / 우: 비디오)
    window.splitter = QSplitter(Qt.Orientation.Horizontal)
    window.splitter.setHandleWidth(5)

    # =========================================================================
    # [좌측 패널] 컨트롤 및 리스트
    # =========================================================================
    left_widget = QWidget()
    left_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    left_widget.setMinimumWidth(230)
    
    left_layout = QVBoxLayout(left_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(5)
    
    # --- [1층] 상단 메뉴 (목록/휴지통/설정) ---
    top_btn_layout = QHBoxLayout()
    top_btn_layout.setSpacing(5)
    
    window.btn_main_list = QPushButton()
    window.btn_main_list.setFixedHeight(MENUHEIGHT)
    # [Icon] 깔끔한 리스트 아이콘
    window.btn_main_list.setIcon(qta.icon('mdi6.view-list', color=styles.CurrentTheme.TEXT_SUB))
    window.btn_main_list.setIconSize(QSize(24, 24))
    window.btn_main_list.setStyleSheet(styles.BTN_MAIN_LIST)
    window.btn_main_list.setCheckable(True)

    window.btn_trash_mode = QPushButton()
    window.btn_trash_mode.setFixedHeight(MENUHEIGHT)
    # [Icon] 모던한 휴지통 라인 아이콘
    window.btn_trash_mode.setIcon(qta.icon('mdi6.trash-can-outline', color=styles.CurrentTheme.TEXT_SUB))
    window.btn_trash_mode.setIconSize(QSize(22, 22))
    window.btn_trash_mode.setStyleSheet(styles.BTN_TRASH)
    window.btn_trash_mode.setCheckable(True)

    window.btn_settings = QPushButton()
    window.btn_settings.setFixedSize(40, MENUHEIGHT)
    # [Icon] 심플한 톱니바퀴
    window.btn_settings.setIcon(qta.icon('mdi6.cog-outline', color=styles.CurrentTheme.TEXT_SUB))
    window.btn_settings.setIconSize(QSize(22, 22))
    window.btn_settings.setStyleSheet(styles.BTN_SETTINGS)
    
    top_btn_layout.addWidget(window.btn_main_list, 1)
    top_btn_layout.addWidget(window.btn_trash_mode, 1)
    top_btn_layout.addWidget(window.btn_settings, 0)
    left_layout.addLayout(top_btn_layout)

    # --- [2층] 필터 메뉴 (하이라이트/A/B/새로고침) ---
    addr_layout = QHBoxLayout()
    addr_layout.setSpacing(5)
    
    window.btn_highlight = QPushButton("하이라이트")
    window.btn_highlight.setFixedHeight(MENUHEIGHT)
    window.btn_highlight.setStyleSheet(styles.BTN_HIGHLIGHT)
    window.btn_highlight.setCheckable(True)
    
    ab_layout = QHBoxLayout()
    ab_layout.setSpacing(5) 
    
    window.btn_filter_a = QPushButton("A")
    window.btn_filter_a.setFixedHeight(MENUHEIGHT)
    window.btn_filter_a.setCheckable(True)
    window.btn_filter_a.setStyleSheet(styles.BTN_FILTER_A)

    window.btn_filter_b = QPushButton("B")
    window.btn_filter_b.setFixedHeight(MENUHEIGHT)
    window.btn_filter_b.setCheckable(True)
    window.btn_filter_b.setStyleSheet(styles.BTN_FILTER_B)
    
    ab_layout.addWidget(window.btn_filter_a)
    ab_layout.addWidget(window.btn_filter_b)
    
    window.btn_refresh = QPushButton()
    window.btn_refresh.setFixedSize(40, MENUHEIGHT)
    # [Icon] 부드러운 새로고침
    window.btn_refresh.setIcon(qta.icon('mdi6.refresh', color=styles.CurrentTheme.TEXT_SUB))
    window.btn_refresh.setIconSize(QSize(20, 20))
    window.btn_refresh.setStyleSheet(styles.BTN_REFRESH)

    addr_layout.addWidget(window.btn_highlight, 1)
    addr_layout.addLayout(ab_layout, 1) 
    addr_layout.addWidget(window.btn_refresh, 0) 
    left_layout.addLayout(addr_layout)

    # --- [2.5층] 검색창 ---
    window.input_search = QLineEdit()
    window.input_search.setPlaceholderText(" 추가된 전체 폴더 검색")
    window.input_search.setFixedHeight(30)
    window.input_search.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    window.input_search.setStyleSheet(styles.SEARCH_INPUT_STYLE)
    
    search_action = QAction(window.input_search)
    # [Icon] 돋보기
    search_action.setIcon(qta.icon('mdi6.magnify', color=styles.CurrentTheme.TEXT_SUB))
    window.input_search.addAction(search_action, QLineEdit.ActionPosition.LeadingPosition)
    
    left_layout.addWidget(window.input_search)

    # --- [태그 삭제 버튼] (평소엔 숨김) ---
    window.btn_clear_tag_a = QPushButton(" A급 태그 전체 삭제") # 텍스트 이모지 제거
    window.btn_clear_tag_a.setFixedHeight(30)
    # [Icon] 노란색 별 아이콘 (mdi6.star)
    window.btn_clear_tag_a.setIcon(qta.icon('mdi6.star', color=styles.CurrentTheme.ACCENT_YELLOW))
    window.btn_clear_tag_a.setIconSize(QSize(20, 20))
    window.btn_clear_tag_a.setStyleSheet(styles.BTN_A_TAGDELETE)
    window.btn_clear_tag_a.hide()
    left_layout.addWidget(window.btn_clear_tag_a)

    window.btn_clear_tag_b = QPushButton(" B급 태그 전체 삭제") # 텍스트 이모지 제거
    window.btn_clear_tag_b.setFixedHeight(30)
    # [Icon] 파란색 별 아이콘 (mdi6.star)
    window.btn_clear_tag_b.setIcon(qta.icon('mdi6.star', color=styles.CurrentTheme.ACCENT_BLUE))
    window.btn_clear_tag_b.setIconSize(QSize(20, 20))
    window.btn_clear_tag_b.setStyleSheet(styles.BTN_B_TAGDELETE)
    window.btn_clear_tag_b.hide()
    left_layout.addWidget(window.btn_clear_tag_b)

    # [New] 하이라이트 전체 삭제 버튼 추가
    window.btn_clear_highlight = QPushButton(" 하이라이트 전체 삭제") # 텍스트 이모지 제거
    window.btn_clear_highlight.setFixedHeight(30)
    # [Icon] 폭죽 아이콘 (mdi6.firework)
    window.btn_clear_highlight.setIcon(qta.icon('mdi6.firework', color=styles.CurrentTheme.ACCENT_PURPLE))
    window.btn_clear_highlight.setIconSize(QSize(20, 20))
    window.btn_clear_highlight.setStyleSheet(styles.BTN_HL_TAGDELETE)
    window.btn_clear_highlight.hide() 
    left_layout.addWidget(window.btn_clear_highlight)

    # --- [3층] 리스트 영역 (폴더/파일) ---
    left_v_splitter = QSplitter(Qt.Orientation.Vertical)
    left_v_splitter.setHandleWidth(5)

    # 1. 폴더 리스트
    window.folder_list_widget = PlaceholderListWidget()
    window.folder_list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    window.folder_list_widget.setFrameShape(QFrame.Shape.NoFrame)
    window.folder_list_widget.setObjectName("RoundList")
    window.folder_list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
    window.folder_list_widget.setAcceptDrops(True)
    window.folder_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    window.folder_list_widget.setDropIndicatorShown(False)
    window.folder_list_widget.setUniformItemSizes(True)

    sp_folder = window.folder_list_widget.sizePolicy()
    sp_folder.setRetainSizeWhenHidden(True)
    window.folder_list_widget.setSizePolicy(sp_folder)

    # 2. 파일 리스트
    window.file_list = WatermarkListWidget()
    window.file_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    window.file_list.setFrameShape(QFrame.Shape.NoFrame)
    window.file_list.setObjectName("RoundList")
    window.file_list.setUniformItemSizes(True)
    
    sp_file = window.file_list.sizePolicy()
    sp_file.setRetainSizeWhenHidden(True)
    window.file_list.setSizePolicy(sp_file)

    left_v_splitter.addWidget(window.folder_list_widget)
    left_v_splitter.addWidget(window.file_list)
    left_v_splitter.setStretchFactor(0, 3) 
    left_v_splitter.setStretchFactor(1, 7)
    left_layout.addWidget(left_v_splitter, 1)
    
    # --- [4층] 재생 옵션 그룹 ---
    group = QGroupBox()
    group.setMinimumWidth(200)
    
    vbox = QVBoxLayout()
    vbox.setSpacing(5) 
    vbox.setContentsMargins(10, 5, 10, 5)
    
    # 옵션 1: 소리 재생
    window.chk_audio = QCheckBox("소리 재생")
    # [Icon] 볼륨 아이콘 (High)
    window.chk_audio.setIcon(qta.icon('mdi6.volume-high', color=styles.CurrentTheme.TEXT_SUB))
    window.chk_audio.setIconSize(QSize(18, 18))
    window.chk_audio.setStyleSheet(styles.CHK_AUDIO_STYLE)
    window.chk_audio.setFixedHeight(20) 
    vbox.addWidget(window.chk_audio)
    
    # 옵션 2: 랜덤 재생
    window.chk_random = QCheckBox("랜덤 위치 재생")
    # [Icon] 셔플 아이콘
    window.chk_random.setIcon(qta.icon('mdi6.shuffle', color=styles.CurrentTheme.ACCENT_BLUE))
    window.chk_random.setIconSize(QSize(18, 18))
    window.chk_random.setStyleSheet(styles.CHK_RANDOM_STYLE)
    window.chk_random.setFixedHeight(20)
    vbox.addWidget(window.chk_random)

    # 옵션 3: 자동 건너뛰기
    h_scan = QHBoxLayout()
    h_scan.setSpacing(5)
    h_scan.setContentsMargins(0, 0, 0, 0)

    window.chk_autoscan = QCheckBox("자동 건너뛰기")
    # [Icon] 번개/플래시 아이콘
    window.chk_autoscan.setIcon(qta.icon('mdi6.lightning-bolt', color=styles.CurrentTheme.ACCENT_RED))
    window.chk_autoscan.setIconSize(QSize(18, 18))
    window.chk_autoscan.setStyleSheet(styles.CHK_AUTOSCAN_STYLE)
    window.chk_autoscan.setFixedHeight(20)
    h_scan.addWidget(window.chk_autoscan)
    
    window.combo_skip = QComboBox()
    window.combo_skip.addItems(["5%", "10%", "15%", "20%", "30%"])
    window.combo_skip.setFixedSize(40, 20) 
    window.combo_skip.setStyleSheet(styles.COMBO_MINI_STYLE) 
    h_scan.addWidget(window.combo_skip)
    h_scan.addStretch(1)
    
    vbox.addLayout(h_scan)
    group.setLayout(vbox)
    left_layout.addWidget(group)

    # 상태 표시줄: 재생 상태와 작업/검색 상태를 분리
    window.lbl_playback_status = QLabel("재생: 대기")
    window.lbl_playback_status.setStyleSheet(styles.LABEL_PLAYBACK_STYLE)
    window.lbl_playback_status.setToolTip("현재 플레이어가 가리키는 영상 상태")
    left_layout.addWidget(window.lbl_playback_status)

    window.lbl_info = QLabel("작업: 준비됨")
    window.lbl_info.setStyleSheet(styles.LABEL_INFO_STYLE)
    window.lbl_info.setToolTip("검색, 색인, 태그, 휴지통 작업 상태")
    left_layout.addWidget(window.lbl_info)

    # =========================================================================
    # [우측 패널] 비디오 뷰 및 컨트롤 버튼
    # =========================================================================
    right_widget = QWidget()
    right_layout = QVBoxLayout(right_widget)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(5)
    
    player_row = QHBoxLayout()
    player_row.setContentsMargins(0, 0, 0, 0)
    player_row.setSpacing(5)

    window.video_view = ProVideoView()
    window.thumbnail_rail = ThumbnailPreviewRailWidget()
    window.thumbnail_rail.setFixedWidth(ThumbnailPreviewRailWidget.width_for_height(720))
    
    sp_video = window.video_view.sizePolicy()
    sp_video.setRetainSizeWhenHidden(True)
    window.video_view.setSizePolicy(sp_video)
    
    player_row.addWidget(window.video_view, 1)
    player_row.addWidget(window.thumbnail_rail, 0)
    right_layout.addLayout(player_row, 1)

    # --- 하단 컨트롤 버튼 ---
    window.btn_layout = QHBoxLayout()
    window.btn_layout.setSpacing(5)
    
    def create_btn(text, style, height=35):
        btn = QPushButton(text)
        btn.setStyleSheet(style)
        btn.setFixedHeight(height)
        return btn
    
    # 버튼 생성
    window.btn_play = create_btn("재생/정지 [Space]", styles.BTN_PLAY)
    window.btn_add_highlight = create_btn("하이라이트 추가 [3]", styles.BTN_ADD_HL)
    window.btn_replay_highlight = create_btn("구간 다시 재생 [Enter]", styles.BTN_REPLAY_HL)
    window.btn_del_highlight = create_btn("하이라이트 삭제 [3]", styles.BTN_DEL_HL)
    window.btn_mark = create_btn("# 마킹 [Enter]", styles.BTN_WARNING)
    window.btn_soft_delete = create_btn("휴지통 [Del]", styles.BTN_DANGER)
    window.btn_restore = create_btn("복구 [R]", styles.BTN_PRIMARY)
    window.btn_restore_all = create_btn("전체 복구", styles.BTN_RESTORE_ALL)
    window.btn_del_selected = create_btn("선택 삭제 [Del]", styles.BTN_DANGER)
    window.btn_del_all = create_btn("전체 삭제", styles.BTN_DANGER)

    # 버튼 초기 숨김 상태 설정
    for btn in [window.btn_replay_highlight, window.btn_del_highlight, 
                window.btn_restore, window.btn_restore_all, 
                window.btn_del_selected, window.btn_del_all]:
        btn.hide()

    # 레이아웃 배치
    window.btn_layout.addWidget(window.btn_play, 15) 
    window.btn_layout.addWidget(window.btn_add_highlight, 10)
    window.btn_layout.addWidget(window.btn_replay_highlight, 10)
    window.btn_layout.addWidget(window.btn_del_highlight, 10)
    window.btn_layout.addWidget(window.btn_mark, 10)
    window.btn_layout.addWidget(window.btn_soft_delete, 10)
    
    window.btn_layout.addWidget(window.btn_restore, 10)
    window.btn_layout.addWidget(window.btn_restore_all, 10) 
    window.btn_layout.addWidget(window.btn_del_selected, 10) 
    window.btn_layout.addWidget(window.btn_del_all, 10)

    right_layout.addLayout(window.btn_layout)
    
    # 스플리터에 패널 추가 및 메인 레이아웃 적용
    window.splitter.addWidget(left_widget)
    window.splitter.addWidget(right_widget)
    main_layout.addWidget(window.splitter)
    
    # [Refactored] 포커스 정책 일괄 적용 (Space바 충돌 방지)
    all_buttons = [
        window.btn_main_list, window.btn_trash_mode, window.btn_settings, 
        window.btn_highlight, window.btn_filter_a, window.btn_filter_b, 
        window.btn_refresh, window.btn_play, window.btn_add_highlight,
        window.btn_replay_highlight, window.btn_del_highlight,
        window.btn_mark, window.btn_soft_delete, window.btn_restore,
        window.btn_restore_all, window.btn_del_selected, window.btn_del_all,
        window.btn_clear_tag_a, window.btn_clear_tag_b, window.btn_clear_highlight,
        window.chk_audio, window.chk_random, window.chk_autoscan, window.combo_skip
    ]
    
    for widget in all_buttons:
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
