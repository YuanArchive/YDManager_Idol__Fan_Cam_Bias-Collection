# styles.py

# =============================================================================
# 1. 테마 팔레트 정의 (Color Palettes)
# =============================================================================

class NordTheme:
    # 기존: rgba(46, 52, 64, 80) -> 80을 0.3 같은 소수점으로 변경
    # 블러 효과가 잘 보이려면 배경색의 투명도를 아주 낮게(0.1 ~ 0.3) 주는 것이 좋습니다.
    BASE = "rgba(46, 52, 64, 0.2)" # [변경]  

    # --- 2. UI 요소 배경색 (선명하게 유지) ---
    # 메뉴와 리스트는 블러의 영향을 받지 않고 또렷하게 보입니다.
    SURFACE  = "#3B4252"
    OVERLAY  = "#4C566A"
    
    # --- 2. 텍스트 색상 (New Standard) ---
    TEXT_MAIN = "#ECEFF4" # 제목 (밝은 흰색)
    TEXT_SUB  = "#D8DEE9" # 설명 (회색)
    
    # --- 3. 포인트 색상 (New Standard) ---
    ACCENT_BLUE   = "#88C0D0"  # 정보/강조
    ACCENT_DARK   = "#5E81AC"  # 선택/버튼
    ACCENT_RED    = "#BF616A"  # 위험/삭제
    ACCENT_ORANGE = "#D08770"  # 경고
    ACCENT_YELLOW = "#EBCB8B"  # 주의/태그
    ACCENT_GREEN  = "#A3BE8C"  # 긍정/재생
    ACCENT_PURPLE = "#B48EAD"  # 하이라이트

    # --- [중요] 기존 코드 호환성 유지 (Legacy Aliases) ---
    # ui_components.py가 옛날 이름을 찾아도 에러가 나지 않도록 연결해줍니다.
    TEXT     = TEXT_MAIN
    SUBTEXT  = TEXT_SUB
    
    # [추가] BG_SUB 호환성 추가 (settings_ui.py에서 사용)
    BG_SUB   = SURFACE
    
    BLUE     = ACCENT_BLUE
    RED      = ACCENT_RED
    YELLOW   = ACCENT_YELLOW
    GREEN    = ACCENT_GREEN
    MAUVE    = ACCENT_PURPLE
    SAPPHIRE = ACCENT_DARK  # 기존 Sapphire 대체
    ORANGE   = ACCENT_ORANGE


class Catppuccin:
    """
    [Catppuccin Macchiato] 부드러운 파스텔 톤
    """
    BASE     = "rgba(46, 52, 64, 80)"  
    SURFACE  = "rgba(59, 66, 82, 150)"
    OVERLAY  = "#494d64"
    
    TEXT_MAIN = "#cad3f5"
    TEXT_SUB  = "#a5adcb"
    
    ACCENT_BLUE   = "#89adf4"
    ACCENT_DARK   = "#7dc4e4"
    ACCENT_RED    = "#ed8796"
    ACCENT_ORANGE = "#f5a97f"
    ACCENT_YELLOW = "#eed49f"
    ACCENT_GREEN  = "#a6da95"
    ACCENT_PURPLE = "#c6a0f6"

    # 호환성 연결
    TEXT     = TEXT_MAIN
    SUBTEXT  = TEXT_SUB
    BLUE     = ACCENT_BLUE
    RED      = ACCENT_RED
    YELLOW   = ACCENT_YELLOW
    GREEN    = ACCENT_GREEN
    MAUVE    = ACCENT_PURPLE
    SAPPHIRE = ACCENT_DARK
    ORANGE   = ACCENT_ORANGE


# ★ 여기서 테마를 선택하세요! (이 줄만 바꾸면 전체 적용) ★
CurrentTheme = NordTheme 
# CurrentTheme = Catppuccin 

# 호환성을 위해 남겨둠 (기존 코드 에러 방지)
Catppuccin = CurrentTheme


# =============================================================================
# 2. 공통 스타일 (Global Styles)
# =============================================================================

from src.utils.utils_font import get_current_font_family

# [폰트 설정] utils_font에서 선택된 폰트 가져오기
try:
    current_font = get_current_font_family()
except:
    current_font = "Malgun Gothic" # 기본값 (Fallback)

FONT_FAMILY = f"'{current_font}', 'Malgun Gothic', sans-serif"

DARK_THEME = f"""
    /* 1. 모든 위젯 기본 설정 */
    QWidget {{ 
        background: transparent; 
        color: {CurrentTheme.TEXT_MAIN}; 
        font-family: {FONT_FAMILY};
    }}
    
    /* 2. 메인 프레임 */
    QMainWindow {{
        background: transparent;
    }}
    
    /* 3. 배경 판 */
    QWidget#CentralWidget {{ 
        background-color: {CurrentTheme.BASE}; 
        border-radius: 10px;
    }}
    
    /* 4. 리스트 위젯 */
    QListWidget#RoundList {{ 
        background-color: transparent;
        border: 1px solid rgba(255, 255, 255, 20); 
        border-radius: 10px;
        outline: none;
        padding: 5px;
    }}

    /* 5. 재생 옵션 그룹박스 */
    QGroupBox {{ 
        border: 1px solid {CurrentTheme.SURFACE};
        border-radius: 10px;
        background: transparent;
        margin-top: 0px;
        font-weight: bold;
        color: {CurrentTheme.TEXT_SUB};
        padding: 0px;      /* 내부 여백 제거로 밀착 */
    }}

    /* 6. 라벨 및 기타 요소 */
    QLabel {{ color: {CurrentTheme.TEXT_SUB}; }}
    
    QToolTip {{
        background-color: {CurrentTheme.SURFACE}; 
        color: {CurrentTheme.TEXT_MAIN}; 
        border: 1px solid {CurrentTheme.ACCENT_BLUE}; 
        border-radius: 10px;
        padding: 5px;
    }}

    /* 7. 콤보박스 및 스플리터 */
    QComboBox {{ 
        background-color: {CurrentTheme.SURFACE}; 
        color: {CurrentTheme.TEXT_MAIN}; 
        border: 1px solid {CurrentTheme.OVERLAY}; 
        padding: 4px; 
        border-radius: 10px;
    }}
    
    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:hover {{ background: {CurrentTheme.OVERLAY}; }}
    QSplitter::handle:horizontal {{ width: 4px; }}
    QSplitter::handle:vertical {{ height: 4px; }}
"""

MODERN_SCROLLBAR = f"""
    /* [수직 스크롤바] - 세로 */
    QScrollBar:vertical {{
        border: none;
        background: transparent; /* 배경을 투명하게 해서 '떠 있는' 느낌 */
        width: 5px;              /* 두께를 얇게 (10px -> 8px) */
        margin: 0px 0px 0px 0px;
    }}
    
    /* 스크롤바 손잡이 (핸들) */
    QScrollBar::handle:vertical {{
        background: {CurrentTheme.OVERLAY}; /* 평소엔 차분한 색 */
        min-height: 30px;        /* 너무 작아지지 않게 최소 길이 확보 */
        border-radius: 4px;      /* 둥근 모서리 (두께의 절반) */
        margin: 0px 1px 0px 1px; /* 양옆에 1px 여백을 줘서 더 날렵하게 보임 */
    }}
    
    /* 마우스 올렸을 때 핸들 색상 */
    QScrollBar::handle:vertical:hover {{
        background: {CurrentTheme.ACCENT_DARK}; /* 포인트 컬러로 변신 */
    }}
    
    /* 위/아래 화살표 버튼 제거 (모던 UI 필수) */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}

    /* [수평 스크롤바] - 가로 */
    QScrollBar:horizontal {{
        border: none;
        background: transparent;
        height: 5px;             /* 두께 얇게 */
        margin: 0px 0px 0px 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background: {CurrentTheme.OVERLAY};
        min-width: 30px;
        border-radius: 4px;
        margin: 1px 0px 1px 0px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background: {CurrentTheme.ACCENT_DARK};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        background: none;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: none;
    }}
    
    /* [모서리] 수직/수평 스크롤바가 만나는 지점 투명 처리 */
    QAbstractScrollArea::corner {{
        background: transparent;
    }}
"""
DARK_THEME += MODERN_SCROLLBAR


# =============================================================================
# 3. 위젯별 전용 스타일 (Specific Widget Styles)
# =============================================================================

# [리스트 위젯]
LIST_WIDGET_STYLE_GLOBAL = f"""
    /* 1. 리스트 기본 상태 */
    QListWidget#RoundList {{ 
        background-color: transparent;
        color: {CurrentTheme.TEXT_SUB}; 
        border: 1px solid {CurrentTheme.SURFACE}; 
        border-radius: 10px;
        padding: 0px;
        outline: none; 
    }}
    
    /*    [추가] 리스트 내부 뷰포트도 투명하게 설정 (안전장치) */
    QListWidget#RoundList QWidget {{
        background-color: transparent;
    }}

    /* 2. [강조] 클릭 또는 Tab으로 선택된 상태 (Focus) */
    /* 테두리를 밝은 파란색으로 바꾸고 두께를 유지하여 리스트가 '활성화'됨을 알림 */
    QListWidget#RoundList:focus {{
        background-color: {CurrentTheme.BASE}; /* 배경을 메인 배경색으로 살짝 낮춰 대비 강조 */
        border: 1px solid {CurrentTheme.ACCENT_BLUE}; /* 강조색 테두리 */
    }}

    /* 3. 아이템 스타일 (기존 유지하되 선택 색상 확인) */
    QListWidget#RoundList::item {{ 
        height: 25px; 
        padding-left: 0px; 
        border-radius: 0px; 
        margin-bottom: 2px;
    }}

    QListWidget#RoundList::item:hover {{ 
        background-color: {CurrentTheme.OVERLAY}; 
        color: {CurrentTheme.TEXT_MAIN}; 
    }}

    /* 아이템이 선택되었을 때의 색상 (ACCENT_DARK) */
    QListWidget#RoundList::item:selected {{ 
        background-color: {CurrentTheme.ACCENT_DARK}; 
        color: {CurrentTheme.TEXT_MAIN}; 
        font-weight: bold;
    }}
    
    /* 포커스를 잃었을 때 선택된 아이템의 색상 유지 */
    QListWidget#RoundList::item:selected:!active {{
        background-color: {CurrentTheme.OVERLAY};
    }}
"""

# 전역 테마에 합치기
DARK_THEME += LIST_WIDGET_STYLE_GLOBAL

# [검색창]
SEARCH_INPUT_STYLE = f"""
    QLineEdit {{ 
        background-color: {CurrentTheme.BASE}; 
        color: {CurrentTheme.TEXT_MAIN}; 
        border: 1px solid {CurrentTheme.OVERLAY}; 
        border-radius: 10px; 
        padding-left: 8px; 
        font-size: 13px;
    }}
    QLineEdit:focus {{ border: 1px solid {CurrentTheme.ACCENT_BLUE}; }}
"""

# [설정 창 - 초기화 버튼]
BTN_RESET_STYLE = f"""
    QPushButton {{ 
        background-color: transparent;
        color: {CurrentTheme.ACCENT_RED}; 
        border: 1px solid {CurrentTheme.ACCENT_RED}; 
        padding: 10px; 
        font-weight: bold;
        border-radius: 4px;
    }}
    QPushButton:hover {{ 
        background-color: {CurrentTheme.ACCENT_RED}; 
        /* [수정] 마우스 올렸을 때 글자색을 검정(#000000)으로 변경 */
        color: #000000; 
    }}
"""

# [체크박스]
def checkbox_style(color):
    return f"""
        QCheckBox {{ color: {color}; font-weight: bold; spacing: 8px; }}
        QCheckBox::indicator {{ 
            width: 16px; height: 16px; 
            border-radius: 3px; 
            border: 1px solid {CurrentTheme.OVERLAY}; 
            background: {CurrentTheme.SURFACE}; 
        }}
        QCheckBox::indicator:checked {{ 
            background-color: {color}; 
            border-color: {color}; 
        }}
    """

CHK_AUDIO_STYLE    = checkbox_style(CurrentTheme.TEXT_SUB)
CHK_RANDOM_STYLE   = checkbox_style(CurrentTheme.ACCENT_BLUE)
CHK_AUTOSCAN_STYLE = checkbox_style(CurrentTheme.ACCENT_RED)

# [작은 콤보박스]
COMBO_MINI_STYLE = f"""
    QComboBox {{
        background-color: {CurrentTheme.SURFACE};
        color: {CurrentTheme.TEXT_MAIN};
        border: 1px solid {CurrentTheme.OVERLAY};
        border-radius: 6px;
        padding-left: 8px; /* 텍스트가 중앙에 오도록 여백 조정 */
        font-size: 12px;
        font-weight: bold;
    }}
    /* ▼ 화살표 버튼 영역 자체를 0px로 만들어 숨김 */
    QComboBox::drop-down {{
        width: 0px;
        border: none;
    }}
    /* 화살표 아이콘 이미지 제거 */
    QComboBox::down-arrow {{
        image: none;
        border: none;
    }}
    /* 리스트가 펼쳐질 때의 디자인 */
    QComboBox QAbstractItemView {{
        border: 1px solid {CurrentTheme.OVERLAY};
        background-color: {CurrentTheme.SURFACE};
        selection-background-color: {CurrentTheme.ACCENT_DARK};
        outline: none;
    }}
"""

# [상태 라벨]
LABEL_PLAYBACK_STYLE = f"""
    color: {CurrentTheme.ACCENT_GREEN};
    font-weight: bold;
    margin-top: 8px;
"""

LABEL_INFO_STYLE = f"""
    color: {CurrentTheme.TEXT_SUB};
    font-weight: bold;
    margin-top: 0px;
"""


# =============================================================================
# 4. 버튼 스타일 (Ghost Button Design)
# =============================================================================

def ghost_btn(color, text_color=None):
    if text_color is None: text_color = color
    return f"""
        /* 1. 기본 상태 (비활성) */
        QPushButton {{ 
            background-color: transparent; 
            color: {text_color}; 
            font-weight: bold; 
            font-size: 12px;
            border: 1px solid {CurrentTheme.OVERLAY}; 
            border-radius: 6px; 
        }}
        
        /* 2. [요청 반영] 마우스 호버(Hover) & 체크됨(Checked) & 눌림(Pressed) 
           - 배경: 모두 회색(OVERLAY)으로 통일
           - 글자: 포인트 색상(text_color) 유지
           - 테두리: 회색(OVERLAY)으로 하되, 체크된 건 티가 나게 살짝 포인트 컬러를 줄 수도 있음
        */
        QPushButton:hover, QPushButton:checked, QPushButton:pressed {{ 
            background-color: {CurrentTheme.OVERLAY}; 
            border: 1px solid {CurrentTheme.OVERLAY}; 
            color: {text_color}; 
        }}
        
        /* (옵션) 켜져있는 버튼(Checked)은 테두리로 살짝 티내기 
           (싫으시면 이 부분 지우셔도 됩니다) */
        QPushButton:checked {{
            border: 1px solid {color}; 
        }}
    """


# 상단 탭
# 사용법: ghost_btn( 호버_배경색, 텍스트_아이콘_색상 )

# 1. 상단 탭 (배경은 OVERLAY로 통일, 아이콘은 고유 색상 유지)
# 상단 탭 (각자의 색상을 지정하면 -> 함수가 알아서 글자색으로 적용함)
BTN_MAIN_LIST = ghost_btn(CurrentTheme.ACCENT_GREEN)   # 초록 글자
BTN_HIGHLIGHT = ghost_btn(CurrentTheme.ACCENT_PURPLE)  # 보라 글자
BTN_TRASH     = ghost_btn(CurrentTheme.ACCENT_RED)     # 빨강 글자
BTN_SETTINGS  = ghost_btn(CurrentTheme.TEXT_SUB)       # 회색 글자
BTN_REFRESH   = ghost_btn(CurrentTheme.ACCENT_BLUE)    # 파랑 글자

# 필터 버튼
BTN_FILTER_A  = ghost_btn(CurrentTheme.ACCENT_YELLOW)
BTN_FILTER_B  = ghost_btn(CurrentTheme.ACCENT_BLUE)

# 태그 삭제
BTN_A_TAGDELETE  = ghost_btn(CurrentTheme.ACCENT_YELLOW)
BTN_B_TAGDELETE  = ghost_btn(CurrentTheme.ACCENT_BLUE)
BTN_HL_TAGDELETE = ghost_btn(CurrentTheme.ACCENT_PURPLE)

# 하단 액션
BTN_ADD_HL      = ghost_btn(CurrentTheme.ACCENT_PURPLE)
BTN_REPLAY_HL   = ghost_btn(CurrentTheme.ACCENT_BLUE)
BTN_DEL_HL      = ghost_btn(CurrentTheme.ACCENT_RED)
BTN_RESTORE_ALL = ghost_btn(CurrentTheme.ACCENT_BLUE)
BTN_MARK        = ghost_btn(CurrentTheme.ACCENT_YELLOW)
BTN_SOFT_DEL    = ghost_btn(CurrentTheme.ACCENT_RED)
BTN_RESTORE     = ghost_btn(CurrentTheme.ACCENT_BLUE)
BTN_DEL_REAL    = ghost_btn(CurrentTheme.ACCENT_RED)
BTN_PLAY        = ghost_btn(CurrentTheme.ACCENT_GREEN)

# 속성별 공통 스타일 (Legacy 호환)
BTN_DANGER  = BTN_SOFT_DEL
BTN_WARNING = BTN_MARK
BTN_PRIMARY = BTN_RESTORE

# =============================================================================
# 5. 팝업 및 다이얼로그 스타일 (Popup & Dialog Styles)
# =============================================================================

# =============================================================================
# 5. 팝업 및 다이얼로그 스타일 (Simple & Modern)
# =============================================================================

# [New] 심플하고 가독성 좋은 모던 팝업 스타일
POPUP_STYLE = f"""
    QDialog {{
        background-color: {CurrentTheme.BASE};
        border: 1px solid {CurrentTheme.OVERLAY};
        border-radius: 10px;
    }}
    
    /* 제목 라벨 */
    QLabel#TitleLabel {{
        color: {CurrentTheme.TEXT_MAIN};
        font-family: {FONT_FAMILY};
        font-size: 16px; /* 18px -> 16px */
        font-weight: bold;
        background: transparent;
        padding: 0px;
    }}
    
    /* 본문 텍스트 */
    QLabel#BodyLabel {{
        color: {CurrentTheme.TEXT_SUB};
        font-family: {FONT_FAMILY};
        font-size: 13px; /* 15px -> 13px */
        line-height: 130%; 
        background: transparent;
        padding: 2px;
    }}
    
    /* 하단 버튼 (완전한 고스트 스타일 - 미니멀) */
    QPushButton {{
        background-color: transparent;
        color: {CurrentTheme.TEXT_SUB};
        border: 1px solid {CurrentTheme.OVERLAY};
        border-radius: 5px;
        padding: 5px 15px; /* 패딩 축소 */
        font-size: 13px;   /* 폰트 축소 */
        font-weight: bold;
        min-width: 60px;   /* 너비 축소 */
    }}
    
    QPushButton:hover {{
        background-color: {CurrentTheme.OVERLAY};
        color: {CurrentTheme.TEXT_MAIN};
        border: 1px solid {CurrentTheme.TEXT_SUB};
    }}
    
    QPushButton:pressed {{
        background-color: {CurrentTheme.TEXT_SUB};
        color: {CurrentTheme.BASE};
    }}
"""

# [추가] 입력 필드 및 콤보박스 스타일 병합
POPUP_STYLE += f"""
    QSpinBox, QComboBox {{
        background-color: {CurrentTheme.SURFACE}; 
        color: {CurrentTheme.TEXT_MAIN}; 
        border: 1px solid {CurrentTheme.OVERLAY}; 
        padding: 10px;
        border-radius: 6px; 
        font-weight: bold;
    }}

    /* [수정 1] 콤보박스 화살표 버튼 영역 제거 (글자만 클릭해도 열림) */
    QComboBox::drop-down {{
        width: 0px; 
        border: none;
    }}
    
    /* [수정 1] 화살표 아이콘 이미지 제거 */
    QComboBox::down-arrow {{
        image: none;
        border: none;
    }}

    /* [수정 2] 콤보박스 클릭 시 나오는 리스트 창 스타일 (검정색 배경 해결) */
    QComboBox QAbstractItemView {{
        background-color: {CurrentTheme.SURFACE}; /* 테마 색상 적용 */
        color: {CurrentTheme.TEXT_MAIN};
        border: 1px solid {CurrentTheme.OVERLAY};
        selection-background-color: {CurrentTheme.ACCENT_DARK};
        outline: none;
        padding: 5px;
    }}
    
    /* 5. 버튼 스타일 (중앙 정렬 유지) */
    QPushButton {{
        background-color: {CurrentTheme.SURFACE};
        color: {CurrentTheme.TEXT_MAIN};
        border: 1px solid {CurrentTheme.OVERLAY};
        border-radius: 6px;
        padding: 10px 0px;
        font-size: 14px;
        min-width: 120px;
        font-weight: bold;
        text-align: center;
    }}
    
    QPushButton:hover {{
        background-color: {CurrentTheme.OVERLAY};
        border: 1px solid {CurrentTheme.ACCENT_BLUE};
        color: {CurrentTheme.ACCENT_BLUE};
    }}
    
    QPushButton:pressed {{
        background-color: {CurrentTheme.ACCENT_DARK};
        color: {CurrentTheme.BASE};
    }}
"""

# [호환성 별칭] main.py에서 GLOBAL_STYLE로 접근 가능하도록 설정
GLOBAL_STYLE = DARK_THEME
