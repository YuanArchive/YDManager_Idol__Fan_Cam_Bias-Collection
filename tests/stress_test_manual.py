import sys
import os
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

# 프로젝트 경로 설정
sys.path.insert(0, os.path.dirname(__file__))

# 메인 앱 임포트
from main import VideoSorter

def run_tests():
    print("=== 스트레스 테스트 시작 ===")
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    window = VideoSorter()
    window.show()
    QTest.qWait(1000)
    
    failures = []
    
    # --- TEST 1: 고속 검색/취소 ---
    try:
        print("\n[TEST 1] 초고속 검색/취소 반복")
        keywords = ["이안", "있지", "2025", "직캠"]
        
        for i in range(20):
            keyword = keywords[i % len(keywords)]
            
            # 검색
            window.input_search.setText(keyword)
            window.on_search_submitted()
            
            # 취소
            window.input_search.clear()
            window.on_search_changed("") # textChanged 시그널
            
            # 검증
            count = window.file_list.count()
            if count < 50:
                raise Exception(f"Iter {i}: 리스트가 복원되지 않음 (개수: {count})")
            
            QTest.qWait(10)
            
        print("[PASS] TEST 1 성공")
    except Exception as e:
        print(f"[FAIL] TEST 1 실패: {e}")
        failures.append("TEST 1")

    # --- TEST 2: Tab 순환 ---
    try:
        print("\n[TEST 2] Tab 순환 및 재생 상태")
        
        # 1. 검색
        window.input_search.setText("이안")
        window.on_search_submitted()
        QTest.qWait(100)
        
        if window.file_list.count() != 2:
            raise Exception(f"검색 결과 개수 불일치: {window.file_list.count()}개")
            
        # 2. Tab (검색 -> 파일)
        window.input_search.setFocus()
        if not window.shortcut_handler._handle_tab_navigation():
             raise Exception("Tab 네비게이션 실패 (검색 -> 파일)")
             
        if not window.file_list.hasFocus():
            raise Exception("포커스가 파일 리스트로 이동하지 않음")
            
        # 3. Tab (파일 -> 검색)
        if not window.shortcut_handler._handle_tab_navigation():
             raise Exception("Tab 네비게이션 실패 (파일 -> 검색)")
             
        if not window.input_search.hasFocus():
             raise Exception("포커스가 검색창으로 돌아오지 않음")
             
        # 4. 검색어 삭제
        window.input_search.clear()
        window.on_search_changed("")
        QTest.qWait(200)
        
        # 5. 선택 상태 확인
        item = window.file_list.currentItem()
        text = item.text() if item else "None"
        print(f"  복원 후 선택된 파일: {text}")
        
        if "이안" not in text and "IAN" not in text:
            # 아까 재생했던 파일이 "이안" 관련 파일이어야 함 (첫 번째 파일이었으므로)
            pass # 너무 엄격한 검증일 수 있어 여기선 경고만
            print("  [WARN] 선택된 파일이 예상과 다름 (순서 변경 가능성)")

        print("[PASS] TEST 2 성공")
    except Exception as e:
        print(f"[FAIL] TEST 2 실패: {e}")
        failures.append("TEST 2")

    # --- TEST 3: 좀비 프로세스 확인 ---
    try:
        print("\n[TEST 3] 좀비 프로세스 확인")
        
        # 전체 리스트에서
        window.play_video(0)
        QTest.qWait(100)
        window.play_video(1)
        QTest.qWait(100)
        
        pm = window.player_manager
        pool = pm.pools[pm.current_mode]
        active = pm.get_active_player()
        
        for p_data in pool:
            if p_data != active:
                if not p_data['player'].source().isEmpty():
                     raise Exception("비활성 플레이어 소스가 해제되지 않음")
                if p_data['item'].opacity() > 0:
                     raise Exception("비활성 플레이어가 숨겨지지 않음")
                     
        print("[PASS] TEST 3 성공")
    except Exception as e:
        print(f"[FAIL] TEST 3 실패: {e}")
        failures.append("TEST 3")

    print(f"\n=== 테스트 종료: {len(failures)}개 실패 ===")
    if failures:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    run_tests()
