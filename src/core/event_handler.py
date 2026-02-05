# event_handler.py
import os # [필수] 경로 비교를 위해 추가
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtMultimedia import QMediaPlayer

class ShortcutHandler:
    def __init__(self, main_window):
        """메인 윈도우 인스턴스를 참조로 받아 명령을 수행합니다."""
        self.main = main_window

    def process_event(self, source, event):
        """프라이버시 모드 시 ESC와 Space 외 모든 입력 차단"""
        
        # 프라이버시 활성화 여부 판정
        is_privacy_on = getattr(self.main, 'conf_privacy_mode', False)
        is_paused = False
        try:
            if hasattr(self.main, 'player'):
                is_paused = self.main.player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        except (RuntimeError, AttributeError):
            # 플레이어 객체가 이미 삭제되었거나 접근 불가능한 경우
            is_paused = False
            
        privacy_active = is_privacy_on and is_paused

        if privacy_active:
            # 1. 키보드 이벤트: ESC와 Space만 허용
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Space:
                    self.main.toggle_play() # 재생 재개 시 main에서 UI를 다시 보여줌
                    return True
                if key == Qt.Key.Key_Escape:
                    self.main.close() # 긴급 종료
                    return True
                return True # 그 외 모든 키(Tab, 화살표 등) 무시
                
            # 2. 마우스 및 휠 이벤트: 프라이버시 모드일 땐 무조건 차단 (클릭 방지)
            if event.type() in [
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick, QEvent.Type.Wheel, 
                QEvent.Type.ContextMenu, QEvent.Type.HoverMove
            ]:
                return True

        # [2] 키보드 이벤트 처리
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()

            # 프라이버시 가드 (Space와 ESC만 통과)
            if privacy_active:
                if key not in [Qt.Key.Key_Space, Qt.Key.Key_Escape]:
                    return True

            # --- 일반 단축키 섹션 ---
            
            # Tab: 리스트 간 포커스 순환
            if key == Qt.Key.Key_Tab:
                return self._handle_tab_navigation()

            # 검색창 입력 중에는 다른 단축키 무시
            if self.main.input_search.hasFocus():
                return False

            # 복구 (R)
            if key == Qt.Key.Key_R:
                if self.main.file_manager.is_trash_mode:
                    self.main.restore_file()
                    return True

            # 재생 토글 (Space)
            if key == Qt.Key.Key_Space:
                self.main.toggle_play()
                return True

            # 태그 (1, 2)
            if key == Qt.Key.Key_1: self.main.toggle_tag_file('A'); return True
            if key == Qt.Key.Key_2: self.main.toggle_tag_file('B'); return True
            
            # 하이라이트 (3)
            if key == Qt.Key.Key_3: 
                if self.main.file_manager.current_mode == 'highlight': 
                    self.main.delete_current_highlight_item()
                else: 
                    self.main.save_current_highlight()
                return True

            # 리스트 탐색 (Up/Down)
            if key in [Qt.Key.Key_Up, Qt.Key.Key_Down]:
                if self.main.file_manager.current_mode == 'highlight' or not self.main.folder_list_widget.hasFocus():
                    delta = -1 if key == Qt.Key.Key_Up else 1
                    self.main.move_selection(delta)
                    return True

            # 시간 이동 (Left/Right)
            step = self.main.conf_seek_interval * 1000  
            if key == Qt.Key.Key_Left: 
                self.main.player.setPosition(max(0, self.main.player.position() - step)); return True
            if key == Qt.Key.Key_Right:
                self.main.player.setPosition(min(self.main.player.duration(), self.main.player.position() + step)); return True

            # 배속 조절 ([, ], Backspace)
            if key == Qt.Key.Key_BracketLeft: self.main.change_playback_rate(-1.0); return True
            if key == Qt.Key.Key_BracketRight: self.main.change_playback_rate(1.0); return True
            if key == Qt.Key.Key_Backspace: self.main.reset_playback_rate(); return True
            
            # 삭제 (Delete)
            if key == Qt.Key.Key_Delete:
                if self.main.file_manager.is_trash_mode: self.main.hard_delete_file()
                elif self.main.folder_list_widget.hasFocus(): self.main.delete_folder_history_item()
                else: self.main.soft_delete_file()
                return True

            # 확인/마킹 (Enter)
            if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                if self.main.file_manager.current_mode == 'highlight': self.main.replay_current_highlight()
                elif self.main.file_manager.is_trash_mode: self.main.restore_file()
                else: self.main.toggle_hash_mark()
                return True

        return False

    def _handle_tab_navigation(self):
        """탭 키를 이용한 위젯 포커스 제어 로직 (시각적 선택 배경색 복구 강화)"""
        m = self.main
        
        # [A] 검색창에서 Tab -> 파일 리스트로 바로 이동
        if m.input_search.hasFocus():
            m.file_list.setFocus()
            if m.file_list.count() > 0:
                m.file_list.blockSignals(True)  # 선택 시 재생 시작 방지
                m.file_list.clearSelection()
                m.file_list.setCurrentRow(0)  # 첫 번째 파일 선택
                
                item = m.file_list.item(0)
                if item:
                    item.setSelected(True)
                    m.file_list.scrollToItem(item)
                m.file_list.blockSignals(False)
                
                # 첫 번째 파일 재생 시작
                m.play_video(0)
                    
            m.file_list.repaint()
            return True
        
        # [B] 기타 -> 폴더 리스트로 이동
        elif not m.folder_list_widget.hasFocus() and not m.file_list.hasFocus():
            m.folder_list_widget.setFocus()
            
            if m.folder_list_widget.count() > 0:
                target_row = 0
                current_root = getattr(m, 'root_folder', None)
                
                # 현재 로드된 폴더 찾기
                if current_root:
                    norm_root = os.path.normpath(current_root)
                    for i in range(m.folder_list_widget.count()):
                        item = m.folder_list_widget.item(i)
                        data_path = item.data(Qt.ItemDataRole.UserRole)
                        if data_path and os.path.normpath(data_path) == norm_root:
                            target_row = i
                            break
                
                # [강력 수정] 기존 선택을 싹 지우고 다시 선택 (버그 방지 핵심)
                m.folder_list_widget.clearSelection() 
                m.folder_list_widget.setCurrentRow(target_row)
                
                item = m.folder_list_widget.item(target_row)
                if item:
                    item.setSelected(True)
                    m.folder_list_widget.scrollToItem(item)
            
            # 스타일 강제 갱신
            m.folder_list_widget.repaint()
            return True
            
        # [B] 폴더 리스트 -> 파일 리스트로 이동
        elif m.folder_list_widget.hasFocus():
            m.file_list.setFocus()
            if m.file_list.count() > 0:
                row = m.file_list.currentRow()
                if row < 0: row = 0
                
                m.file_list.clearSelection() # 기존 선택 초기화
                m.file_list.setCurrentRow(row)
                
                item = m.file_list.item(row)
                if item:
                    item.setSelected(True)
                    m.file_list.scrollToItem(item)
                    
            m.file_list.repaint()
            return True
            
        # [C] 파일 리스트 -> 검색창 또는 폴더 리스트로 이동
        elif m.file_list.hasFocus():
            # [신규] 검색 중이면 검색창으로 돌아감 (검색어 수정 편의)
            if m.file_manager.search_keyword:
                m.input_search.setFocus()
                m.input_search.selectAll()  # 텍스트 전체 선택 (바로 수정 가능)
                return True
            
            # 검색 중이 아니면 폴더 리스트로 이동
            m.folder_list_widget.setFocus()
            
            # [기존] 선택 상태 복구
            if m.folder_list_widget.count() > 0:
                target_row = 0
                current_root = getattr(m, 'root_folder', None)
                if current_root:
                    norm_root = os.path.normpath(current_root)
                    for i in range(m.folder_list_widget.count()):
                        item = m.folder_list_widget.item(i)
                        data_path = item.data(Qt.ItemDataRole.UserRole)
                        if data_path and os.path.normpath(data_path) == norm_root:
                            target_row = i
                            break
                            
                m.folder_list_widget.clearSelection()
                m.folder_list_widget.setCurrentRow(target_row)
                
                item = m.folder_list_widget.item(target_row)
                if item:
                    item.setSelected(True)
                    m.folder_list_widget.scrollToItem(item)
            
            m.folder_list_widget.repaint()
            return True
            
        return False

# -----------------------------------------------------------------------------
# [New] 전역 이벤트 필터 클래스 (모든 창보다 우선순위 높음)
# -----------------------------------------------------------------------------
from PyQt6.QtCore import QObject

class GlobalAppFilter(QObject):
    def eventFilter(self, obj, event):
        # 키보드를 눌렀을 때
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                # [핵심] 현재 활성화된 창이 무엇이든 상관없이 모든 창을 닫고 종료
                # closeAllWindows()를 호출하면 VideoSorter의 closeEvent가 정상 실행되어
                # 데이터(휴지통 등) 저장 로직도 안전하게 수행됩니다.
                from PyQt6.QtWidgets import QApplication
                QApplication.closeAllWindows()
                return True # 이벤트를 소비하여 다른 창으로 전파되지 않게 함
        return super().eventFilter(obj, event)