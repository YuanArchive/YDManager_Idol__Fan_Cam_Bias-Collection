import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QListWidgetItem
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest

# 프로젝트 경로 설정
# 프로젝트 경로 설정 (부모 디렉토리 추가)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import VideoSorter
from src.managers.file_manager import FileManager

class ScenarioTester:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = VideoSorter()
        self.window.show()
        self.file_manager = self.window.file_manager
        self.results = []

    def log(self, msg, success=None):
        status = ""
        if success is True: status = "✅ [PASS] "
        elif success is False: status = "❌ [FAIL] "
        else: status = "ℹ️ [INFO] "
        
        print(f"{status}{msg}")
        self.results.append((success, msg))

    def run_all_tests(self):
        print("\n🎬 시나리오 테스트 시작 (기능 정밀 검증)\n" + "="*50)
        
        # 테스트 수행
        try:
            self.test_search_duplication()
            self.test_highlight_intervals()
            self.test_refresh_logic()
        except Exception as e:
            self.log(f"테스트 도중 치명적 오류 발생: {e}", False)
            import traceback
            traceback.print_exc()

        self.print_summary()
        self.window.close()
        # sys.exit()

    def print_summary(self):
        print("\n" + "="*50)
        print("📊 테스트 결과 리포트")
        print("="*50)
        success_cnt = sum(1 for r in self.results if r[0] is True)
        fail_cnt = sum(1 for r in self.results if r[0] is False)
        
        for success, msg in self.results:
            icon = "✅" if success else ("❌" if success is False else "ℹ️")
            print(f"{icon} {msg}")
            
        print("-"*30)
        print(f"총 {len(self.results)}개 항목 중 {success_cnt}개 성공, {fail_cnt}개 실패")

    # --------------------------------------------------------------------------
    # [시나리오 1] 검색 중복 경로 검증
    # --------------------------------------------------------------------------
    def test_search_duplication(self):
        self.log("시나리오 1: 검색 시 중복 파일 표시 여부 확인")
        
        # 1. 가상 데이터 주입
        # 같은 파일을 대소문자나 경로 형식을 다르게 해서 2개인 척 주입
        fake_files = [
            {'path': r'C:\Video\Test.mp4', 'text': 'Test.mp4'},
            # 중복된 경로 (정규화되면 같아야 함)
            {'path': r'c:\video\test.mp4', 'text': 'test.mp4'}, 
            {'path': r'C:\Video\Other.mp4', 'text': 'Other.mp4'}
        ]
        
        # file_manager의 main_files를 가해킹
        self.file_manager.main_files = fake_files
        self.file_manager.global_files = fake_files # 글로벌 검색용
        
        # 2. 검색 실행
        keyword = "test"
        self.window.input_search.setText(keyword)
        self.window.on_search_submitted()
        
        # 3. 결과 검증
        count = self.window.file_list.count()
        
        # 정규화가 제대로 작동한다면 'Test.mp4' 하나만 떠야 하거나, 
        # file_manager 로직상 중복을 걸러서 보여줘야 함.
        # 하지만 현재 로직은 'main_files'에 이미 중복이 들어있으면 그대로 보여줄 수도 있음.
        # file_manager.update_global_cache 에서는 중복을 거름.
        
        # 검색 결과 아이템들 경로 확인
        seen_paths = set()
        duplicates_found = False
        
        for i in range(count):
            item = self.window.file_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            norm_path = os.path.normpath(path).lower()
            
            if norm_path in seen_paths:
                duplicates_found = True
            seen_paths.add(norm_path)
            
        if duplicates_found:
            self.log(f"검색 결과에 중복된 경로가 발견됨 (총 {count}개)", False)
        else:
            self.log(f"검색 결과 중복 없음 (총 {count}개 항목)", True)

    # --------------------------------------------------------------------------
    # [시나리오 2] 하이라이트 구간 등록 및 이동 검증 (핵심)
    # --------------------------------------------------------------------------
    def test_highlight_intervals(self):
        self.log("시나리오 2: 하이라이트 구간별 이동 정확성 검증 (실제 파일 기반)")
        
        # 1. 실제 영상 파일 찾기 (테스트의 정확성을 위해)
        real_video_path = None
        # 사용자의 일반적인 비디오 폴더 탐색
        search_roots = [
            r"C:\Users\isuso\Videos",
            os.path.expanduser("~/Videos"),
            os.path.expanduser("~/Downloads")
        ]
        
        for root_cand in search_roots:
            if os.path.exists(root_cand):
                for root, _, files in os.walk(root_cand):
                    for f in files:
                        if f.lower().endswith(".mp4"):
                            real_video_path = os.path.join(root, f)
                            break
                    if real_video_path: break
            if real_video_path: break
            
        if not real_video_path:
            self.log("⚠️ 테스트용 실제 영상 파일을 찾을 수 없어 2번 테스트를 건너뜁니다.", None)
            return

        test_path = real_video_path
        self.log(f"테스트 대상 파일: {os.path.basename(test_path)}")
        
        # 2. 하이라이트 데이터 강제 주입 (5초, 10초, 15초)
        key = self.file_manager._get_norm_key(test_path)
        
        # 중요: 기존 데이터 백업
        old_hls = self.file_manager.highlights.copy()
        
        self.file_manager.highlights[key] = [5000, 10000, 15000] # ms 단위
        self.file_manager.save_json(self.file_manager.highlights_file_path, self.file_manager.highlights)
        
        # 3. 하이라이트 모드 진입 및 리스트 갱신
        self.window.toggle_highlight_mode() # 모드 전환
        
        # 리스트에 잘 떴는지 확인
        count = self.window.file_list.count()
        target_items = []
        for i in range(count):
            item = self.window.file_list.item(i)
            p = item.data(Qt.ItemDataRole.UserRole)
            if self.file_manager._get_norm_key(p) == key:
                target_items.append(item)
                
        if len(target_items) != 3:
            self.log(f"하이라이트 3개를 등록했는데 {len(target_items)}개만 표시됨", False)
            # 복구
            self.file_manager.highlights = old_hls
            return

        self.log(f"하이라이트 3개 목록 표시 성공", True)

        # 4. 각 구간 클릭 시 플레이어 위치 이동 검증
        # 실제 플레이어가 파일을 로드하려면 파일이 있어야 하므로, 
        # 여기서는 play_video 호출 후 target_start_pos 변수가 올바르게 세팅되었는지를 확인 (화이트박스 테스트)
        
        # (1) 5초 구간 클릭 (첫 번째 아이템이라고 가정 - 정렬에 따라 다를 수 있음)
        # item의 UserRole+1 에 시간이 저장되어 있어야 함
        
        errors = []
        for i, item in enumerate(target_items):
            expected_pos = item.data(Qt.ItemDataRole.UserRole + 1) # 저장된 시간
            
            # play_video 호출 시뮬레이션 (실제 파일이 없으므로 prepare에서 리턴될 수 있음)
            # 따라서 _resolve_start_pos 메서드를 직접 테스트하거나,
            # item 데이터를 신뢰 확인
            
            # 우리가 수정한 버그: play_video 내부에서 target_start_pos를 먼저 계산하는가?
            self.window.target_start_pos = -999 # 초기화
            
            # 강제로 play_video의 로직 일부 수행 (파일이 없어서 풀(full) 실행은 불가)
            resolved_pos = self.window._resolve_start_pos(item, None)
            
            if resolved_pos != expected_pos:
                errors.append(f"항목 {i}: 예상 {expected_pos}, 실제계산 {resolved_pos}")
            else:
                self.log(f"항목 {i} ({expected_pos}ms) 위치 계산 정확함", True)
                
        if errors:
            self.log(f"위치 계산 오류: {errors}", False)
        
        # 복구
        self.file_manager.highlights = old_hls
        self.file_manager.save_json(self.file_manager.highlights_file_path, self.file_manager.highlights)

    # --------------------------------------------------------------------------
    # [시나리오 3] 새로고침(Refresh) 동작 검증
    # --------------------------------------------------------------------------
    def test_refresh_logic(self):
        self.log("시나리오 3: 파일명 변경 후 새로고침 반영 확인")
        
        # [Fix] 이전 시나리오의 검색어 영향 제거
        self.window.input_search.clear()
        self.window.on_search_submitted()
        
        # [Fix] 하이라이트 모드에서 복귀 (필수)
        if self.file_manager.current_mode != 'main':
            self.window.go_to_main_mode()

        # 1. 임시 테스트 폴더 및 파일 생성
        base_dir = r"C:\Users\isuso\Videos" if os.path.exists(r"C:\Users\isuso\Videos") else os.path.expanduser("~")
        target_dir = os.path.join(base_dir, "YD_Refresh_Test_Folder")
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        file_a = os.path.join(target_dir, "File_A.mp4")
        file_b = os.path.join(target_dir, "File_B.mp4")
        
        # 파일 A 생성
        with open(file_a, 'w') as f: f.write("dummy video content")
        
        try:
            # 2. 앱에서 폴더 로드 (강제 설정)
            self.window.root_folder = target_dir
            self.window.load_files() # 초기 로드
            
            # 검증 1
            if not self._find_item("File_A.mp4"):
                count = self.window.file_list.count()
                items = [self.window.file_list.item(i).text() for i in range(count)]
                self.log(f"초기 파일 로드 실패. [현재 리스트({count}개)]: {items}", False)
                
                # 추가 정보: trash 목록에 있는지 확인
                trash_paths = [t['path'] for t in self.window.file_manager.trash_files]
                self.log(f"휴지통 파일 수: {len(trash_paths)}", None)
                return
                
            # 3. 외부에서 이름 변경 (A -> B)
            os.rename(file_a, file_b)
            
            # 4. 새로고침 버튼 동작 시뮬레이션
            self.window.load_files()
            
            # 5. 검증 2
            has_a = self._find_item("File_A.mp4")
            has_b = self._find_item("File_B.mp4")
            
            if not has_a and has_b:
                self.log("새로고침 반영 성공 (A -> B 변경 확인)", True)
            else:
                self.log(f"새로고침 반영 실패: A존재={has_a}, B존재={has_b}", False)
                
        except Exception as e:
            self.log(f"테스트 중 오류: {e}", False)
        finally:
            # 뒷정리
            if os.path.exists(file_a): os.remove(file_a)
            if os.path.exists(file_b): os.remove(file_b)
            if os.path.exists(target_dir): os.rmdir(target_dir)
            self.window.file_manager.main_files = [] # 클리어

    def _find_item(self, filename):
        for i in range(self.window.file_list.count()):
            # 아이템 텍스트에는 아이콘이 포함될 수 있으므로 포함 여부 확인
            if filename in self.window.file_list.item(i).text():
                return True
        return False


if __name__ == "__main__":
    tester = ScenarioTester()
    # 실행 전 1초 대기
    QTimer.singleShot(1000, tester.run_all_tests)
    tester.app.exec()
