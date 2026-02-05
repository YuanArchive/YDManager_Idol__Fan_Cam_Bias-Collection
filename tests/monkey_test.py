import sys
import os
import random
import inspect
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QDialog, QMessageBox, QWidget
from PyQt6.QtCore import QTimer, Qt, QObject
from PyQt6.QtTest import QTest

# 프로젝트 경로 설정
sys.path.insert(0, os.path.dirname(__file__))

from main import VideoSorter
from utils_logger import get_logger, setup_logging

# 로깅 시스템 초기화 (파일 저장을 위해 필수)
setup_logging()
logger = get_logger()

# =========================================================
# 🐒 지능형 멍키 봇 (Smart Monkey Bot)
# =========================================================
class SmartMonkeyBot(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.action_count = 0
        self.max_actions = 2000 
        self.timer = QTimer()
        self.timer.timeout.connect(self.do_smart_action)
        
        # [패치 적용] 블로킹 함수들을 논-블로킹으로 변환하거나 자동화
        self._apply_patches()

    def _apply_patches(self):
        """
        QDialog.exec() 나 QMessageBox 등이 호출될 때
        봇이 멈추지 않도록 미리 '난동'과 '탈출'을 예약하는 패치
        """
        print("💉 [PATCH] 블로킹 구간 돌파 패치 적용 중...")
        
        # 1. QDialog.exec 패치 (설정창 등)
        original_dialog_exec = QDialog.exec
        
        def patched_exec(dialog_self):
            print(f"💉 [Dialog] 창이 열렸습니다! ({type(dialog_self).__name__}) -> 난입 준비")
            
            # 창이 뜬 동안 수행할 동작 예약 (0.1초 간격으로 10번 시도)
            for i in range(1, 11):
                QTimer.singleShot(i * 100, lambda: self._chaos_in_wdiget(dialog_self))
            
            # 1.5초 뒤 자동 종료 예약 (닫기 or 승인)
            QTimer.singleShot(1500, lambda: self._try_close_dialog(dialog_self))
            
            return original_dialog_exec(dialog_self)
            
        QDialog.exec = patched_exec

        # 2. QMessageBox 패치 (경고창 등)
        # static method들은 패치가 까다로우므로, VideoSorter 내의 호출을 우회하거나
        # QTimer.singleShot으로 엔터키를 보내는 전략 사용
        
        # 여기서는 간단히 전역적인 키보드 엔터 예약을 주기적으로 거는 것으로 대체
        # (do_smart_action에서 수행)

    def _chaos_in_wdiget(self, widget):
        """특정 위젯(창) 내부의 버튼들을 무작위로 클릭"""
        if not widget.isVisible(): return
        
        buttons = widget.findChildren(QPushButton)
        if buttons:
            target = random.choice(buttons)
            if target.isVisible() and target.isEnabled():
                print(f"  ⚡ [Dialog] 내부 클릭: {target.text()}")
                QTest.mouseClick(target, Qt.MouseButton.LeftButton)

    def _try_close_dialog(self, dialog):
        """다이얼로그 탈출 시도"""
        if dialog.isVisible():
            print("  🚪 [Dialog] 탈출 시도!")
            dialog.accept() # 또는 reject()

    def start(self):
        print(f"🦍 스마트 멍키 테스트 시작! (목표: {self.max_actions}회)")
        self.timer.start(100) # 속도: 0.1초 (안정성 확보)

    def do_smart_action(self):
        if self.action_count >= self.max_actions:
            self.stop("목표 달성")
            return
            
        self.action_count += 1
        
        # 현재 활성화된(최상위) 윈도우 찾기
        top_widget = QApplication.activeModalWidget()
        if not top_widget:
            top_widget = self.window
            
        # 액션 가중치
        action_type = random.choices(
            ['click', 'list_nav', 'key_input', 'search', 'scroll'],
            weights=[40, 20, 20, 10, 10], k=1
        )[0]
        
        try:
            if action_type == 'click':
                # [Vision] 현재 창에 있는 모든 버튼 스캔
                all_buttons = top_widget.findChildren(QPushButton)
                visible_buttons = [b for b in all_buttons if b.isVisible() and b.isEnabled()]
                
                if visible_buttons:
                    btn = random.choice(visible_buttons)
                    # 텍스트가 없으면 건너뛰거나(아이콘), objectName 출력
                    name = btn.text() or btn.objectName() or "UnknownBtn"
                    
                    # [Safety] 복구/삭제 버튼은 덜 누르게 (로그 보존)
                    if "삭제" in name or "복구" in name:
                        if random.random() > 0.2: return # 80% 확률로 스킵
                        
                    print(f"[{self.action_count}] 🖱️ 클릭: {name}")
                    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
                    
                    # [Safety] 초기화 직후에는 앱이 재구성되므로 잠시 대기
                    if "초기화" in name:
                        print("  ⏳ 데이터 정리 중... 2초 대기")
                        QTest.qWait(2000)
            
            elif action_type == 'list_nav':
                # 메인 윈도우의 리스트 조작
                if self.window.file_list.isVisible():
                    count = self.window.file_list.count()
                    if count > 0:
                        row = random.randint(0, count - 1)
                        print(f"[{self.action_count}] 📑 리스트 선택: {row}")
                        # 뷰포트 클릭 시뮬레이션 (확실한 포커스 이동)
                        item = self.window.file_list.item(row)
                        rect = self.window.file_list.visualItemRect(item)
                        QTest.mouseClick(self.window.file_list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())

            elif action_type == 'key_input':
                # 키 입력 (Space, Arrow, Tab)
                keys = [Qt.Key.Key_Space, Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Tab]
                # 가끔 ESC 눌러보는데, 패치된 다이얼로그 닫기용으로 쓰임
                if random.random() > 0.9: keys.append(Qt.Key.Key_Escape)
                
                key = random.choice(keys)
                # print(f"[{self.action_count}] ⌨️ 키: {key}")
                QTest.keyClick(QApplication.focusWidget() or top_widget, key)

            elif action_type == 'search':
                # 검색바가 보일 때만
                if self.window.input_search.isVisible():
                    terms = ["직캠", "2024", "Unknown", "Live", "Shorts"]
                    term = random.choice(terms)
                    print(f"[{self.action_count}] 🔍 검색: {term}")
                    self.window.input_search.setText(term)
                    self.window.on_search_submitted()
                    
                    # 바로 지우기
                    if random.random() > 0.5:
                        self.window.input_search.clear()

            elif action_type == 'scroll':
                # 스크롤
                delta = random.choice([120, -120])
                if hasattr(self.window, 'on_video_wheel'):
                    self.window.on_video_wheel(delta)

        except Exception as e:
            print(f"\n❌ [CRASH CODE] {self.action_count}번째 동작 중 사망")
            print(e)
            # import traceback; traceback.print_exc()
            # self.stop("에러 발생") 
            # 봇은 멈추지 않는다 (Keep Going)

    def stop(self, reason):
        print(f"\n🏁 테스트 종료: {reason}")
        self.timer.stop()
        self.window.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 메인 앱 실행
    ex = VideoSorter()
    ex.show()
    
    bot = SmartMonkeyBot(ex)
    
    print("\n🧠 스마트 멍키(Smart Monkey) v2.0 가동 준비 완료")
    print("설정 창이 떠도 뚫고 들어갑니다. 지켜보세요!")
    
    QTimer.singleShot(2000, bot.start)
    
    sys.exit(app.exec())
