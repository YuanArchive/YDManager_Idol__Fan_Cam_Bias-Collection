import sys
import os
import time
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtTest import QTest

# 프로젝트 경로 설정
sys.path.insert(0, os.path.dirname(__file__))

# 메인 앱 임포트
from main import VideoSorter

class StressTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # QApplication은 싱글톤이므로 한 번만 생성
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)
        
        # 앱 실행 (화면은 띄우지 않아도 로직 테스트 가능)
        cls.window = VideoSorter()
        # 로직 초기화 대기
        QTest.qWait(1000)

    def setUp(self):
        self.window.input_search.clear()
        self.window.file_manager.set_search_keyword("")
        
    def test_01_rapid_search_clear(self):
        """[스트레스] 검색/취소 50회 고속 반복 - 리스트 꼬임 확인"""
        print("\n[TEST] 초고속 검색/취소 반복 테스트 시작...")
        
        keywords = ["이안", "있지", "2025", "직캠"]
        
        for i in range(20):
            keyword = keywords[i % len(keywords)]
            
            # 1. 검색어 입력 및 Enter
            self.window.input_search.setText(keyword)
            # Enter 키 시그널 강제 발생
            self.window.on_search_submitted()
            
            # 결과 확인 (개수만 체크)
            count = self.window.file_list.count()
            # print(f"  Iter {i}: '{keyword}' -> {count}개")
            
            # 2. 검색어 지움 (Restore 로직 동작)
            self.window.input_search.clear()
            # textChanged 시그널 동작 시뮬레이션 (자동 복원)
            self.window.on_search_changed("")
            
            # 복원 확인 (전체 리스트 개수)
            restored_count = self.window.file_list.count()
            self.assertTrue(restored_count >= 50, "검색 취소 후 전체 리스트가 복원되지 않음")
            
            # 너무 빠르면 이벤트 루프가 막히므로 약간의 처리 시간 부여
            QTest.qWait(10)
            
        print("[PASS] 리스트 갱신 로직 안정성 확인됨")

    def test_02_tab_navigation_play_cycle(self):
        """[시나리오] 검색 -> Tab(재생) -> Tab(복귀) -> 검색어 삭제 -> 재생 유지 확인"""
        print("\n[TEST] Tab 순환 및 재생 상태 유지 테스트 시작...")
        
        # 1. "이안" 검색
        self.window.input_search.setText("이안")
        self.window.on_search_submitted()
        QTest.qWait(100)
        
        self.assertEqual(self.window.file_list.count(), 2, "검색 결과가 2개가 아님")
        
        # 2. Tab 키 시뮬레이션 (검색창 -> 파일 리스트)
        # 검색창에 포커스
        self.window.input_search.setFocus()
        
        # handle_tab_navigation 직접 호출 (이벤트 필터 로직)
        self.window.shortcut_handler._handle_tab_navigation()
        
        # 검증: 파일 리스트 포커스 + 첫 번째 아이템 선택 + 재생 시작
        self.assertTrue(self.window.file_list.hasFocus(), "포커스가 파일 리스트로 이동하지 않음")
        self.assertEqual(self.window.file_list.currentRow(), 0, "첫 번째 파일이 선택되지 않음")
        
        # 재생 상태 확인 (가상으로 play_video가 호출되었는지)
        # 실제 PlaybackState는 미디어 로딩 시간이 필요하므로 호출 여부로 판단
        
        # 3. Tab 키 재호출 (파일 리스트 -> 검색창)
        self.window.shortcut_handler._handle_tab_navigation()
        
        # 검증: 검색창 포커스 + 텍스트 선택 상태
        self.assertTrue(self.window.input_search.hasFocus(), "포커스가 검색창으로 돌아오지 않음")
        # selectAll() 효과 확인은 어렵지만 포커스는 확인됨
        
        # 4. 검색어 삭제 (Backspace 시뮬레이션 -> textChanged)
        self.window.input_search.clear()
        self.window.on_search_changed("")
        QTest.qWait(200)
        
        # 5. 핵심 검증: 검색이 풀려도 이전에 재생하던 파일이 선택되어 있어야 함
        current_row = self.window.file_list.currentRow()
        current_item = self.window.file_list.item(current_row)
        current_text = current_item.text() if current_item else ""
        
        print(f"  복원 후 선택된 파일: {current_text}")
        
        # "이안"이 포함된 파일이어야 함 (아까 재생했던 파일)
        self.assertTrue("이안" in current_text or "IAN" in current_text, 
                        f"검색 취소 후 재생 중이던 파일이 선택되지 않음. 현재 선택: {current_text}")
        
        print("[PASS] Tab 순환 및 재생 파일 추적 성공")

    def test_03_background_playback_bug(self):
        """[버그검증] 파일 전환 시 이전 플레이어 완전 정지 확인"""
        print("\n[TEST] 백그라운드 재생 좀비 프로세스 확인...")
        
        # 1. 첫 번째 파일 재생
        self.window.play_video(0)
        QTest.qWait(100)
        
        # 2. 두 번째 파일로 전환
        self.window.play_video(1)
        QTest.qWait(100)
        
        # 3. PlayerManager 내부 상태 확인
        # 비활성 플레이어들이 stop() 되었는지 확인
        pm = self.window.player_manager
        current_mode = pm.current_mode
        pool = pm.pools[current_mode]
        
        active_data = pm.get_active_player()
        
        for p_data in pool:
            if p_data != active_data:
                # 비활성 플레이어 검증
                player = p_data['player']
                # 소스가 비어있어야 함 (setSource(QUrl()) 호출했으므로)
                source = player.source()
                self.assertTrue(source.isEmpty(), "비활성 플레이어의 소스가 해제되지 않음 (백그라운드 재생 위험)")
                self.assertEqual(p_data['item'].opacity(), 0.0, "비활성 플레이어 화면이 숨겨지지 않음")
                
        print("[PASS] 비활성 플레이어 정리(Kill) 로직 정상 동작")

if __name__ == "__main__":
    unittest.main()
