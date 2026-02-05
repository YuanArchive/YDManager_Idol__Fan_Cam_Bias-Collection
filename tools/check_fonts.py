from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase
import sys

def list_system_fonts():
    app = QApplication(sys.argv)
    fonts = QFontDatabase.families()
    
    print(f"=== 시스템에 설치된 폰트 목록 (총 {len(fonts)}개) ===")
    for font in fonts:
        # 한글 이름이 포함된 폰트나 주요 폰트 위주로 보려면 필터링이 필요할 수 있지만,
        # 일단 전체 목록을 보여드립니다.
        print(font)

if __name__ == "__main__":
    list_system_fonts()
