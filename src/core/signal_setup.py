from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtCore import Qt

def setup_app_connections(window):
    """
    VideoSorter 메인 윈도우의 시그널 연결을 담당하는 헬퍼 함수입니다.
    main.py의 비대화를 막기 위해 별도 모듈로 분리되었습니다.
    """
    
    # [1] UI Resize Event
    window.splitter.splitterMoved.connect(lambda: window._delayed_resize())
    
    # [2] Main Toolbar Buttons
    window.btn_settings.clicked.connect(window.open_settings)
    window.btn_trash_mode.clicked.connect(window.toggle_trash_mode)
    window.btn_main_list.clicked.connect(window.go_to_main_mode)
    window.btn_refresh.clicked.connect(window.load_files)
    
    # [3] Filter & Tag Buttons
    window.btn_filter_a.clicked.connect(lambda: window.apply_filter('A'))
    window.btn_filter_b.clicked.connect(lambda: window.apply_filter('B'))
    window.btn_clear_tag_a.clicked.connect(lambda: window.on_clear_all_tags('A'))
    window.btn_clear_tag_b.clicked.connect(lambda: window.on_clear_all_tags('B'))
    window.btn_clear_highlight.clicked.connect(window.on_clear_all_highlights)
    
    # [4] Highlight Controls
    window.btn_highlight.clicked.connect(window.toggle_highlight_mode)
    window.btn_del_highlight.clicked.connect(window.delete_current_highlight_item)
    window.btn_add_highlight.clicked.connect(window.save_current_highlight)
    window.btn_replay_highlight.clicked.connect(window.replay_current_highlight)
    
    # [5] Playback Controls
    window.btn_play.clicked.connect(window.toggle_play)
    window.btn_mark.clicked.connect(window.toggle_hash_mark)
    window.btn_soft_delete.clicked.connect(window.soft_delete_file)
    window.btn_restore.clicked.connect(window.restore_file)        
    window.btn_restore_all.clicked.connect(window.restore_all_files)
    window.btn_del_selected.clicked.connect(window.hard_delete_file)
    window.btn_del_all.clicked.connect(window.delete_all_trash_files)
    
    # [6] List Widgets
    window.folder_list_widget.folder_dropped.connect(window.add_folder_by_path)
    window.folder_list_widget.currentItemChanged.connect(window.on_folder_selection_changed)
    window.folder_list_widget.installEventFilter(window)
    window.folder_list_widget.reordered.connect(window.on_folder_reordered)

    window.file_list.currentItemChanged.connect(window.on_current_item_changed)
    window.file_list.installEventFilter(window)
    
    # [7] Options
    window.chk_audio.toggled.connect(window.toggle_audio)
    window.chk_autoscan.toggled.connect(window.toggle_autoscan)
    
    # [8] Video View Inputs
    window.video_view.click_ratio_signal.connect(window.on_video_clicked)
    window.video_view.installEventFilter(window)
    
    # [9] Search Input (Korean IME & Event Filter)
    window.input_search.returnPressed.connect(window.on_search_submitted)
    window.input_search.textChanged.connect(window.on_search_changed)
    window.input_search.installEventFilter(window)
    
    # [10] Initialize Combo Box
    if hasattr(window, 'combo_skip') and hasattr(window, 'conf_default_skip'):
        index = window.combo_skip.findText(window.conf_default_skip)
        if index >= 0: 
            window.combo_skip.setCurrentIndex(index)
