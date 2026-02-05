# src/controllers/file_action_controller.py
"""
파일 관리 액션 컨트롤러
- 파일 삭제, 복원, 태그, 하이라이트 등 파일 관련 액션을 담당
- main.py의 VideoSorter 클래스에서 분리됨
"""
import os
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QMessageBox
from src.ui.ui_components import ThemeMessageBox
from src.utils.utils_logger import get_logger

logger = get_logger()


class FileActionController:
    """
    파일 관리 액션 컨트롤러.
    main.py의 VideoSorter 인스턴스를 참조하여 파일 관련 액션을 수행합니다.
    """
    
    def __init__(self, app):
        """
        Args:
            app: VideoSorter 인스턴스 (메인 윈도우)
        """
        self.app = app
    
    # =========================================================================
    # 파일 삭제/복원
    # =========================================================================
    
    def soft_delete_file(self):
        """선택된 파일을 휴지통으로 이동"""
        row = self.app.file_list.currentRow()
        if row < 0: return
        item_widget = self.app.file_list.item(row)
        path = item_widget.data(Qt.ItemDataRole.UserRole)
        if not path: return

        deleted_item = self.app.file_manager.soft_delete_by_path(path)
        
        if deleted_item:
            logger.info(f"Soft Delete: {path}")
            self.app.file_list.takeItem(row)
            self.app.update_trash_button_text()
            self.app.lbl_info.setText(f"휴지통으로 이동됨: {deleted_item['text']}")
            
            self.app.auto_play_next(row)
            if self.app.file_manager.filter_type:
                self.app.lbl_info.setText(f"{self.app.file_manager.filter_type}급 태그: {self.app.file_list.count()}개 남음")

    def hard_delete_file(self):
        """선택된 파일을 영구 삭제"""
        row = self.app.file_list.currentRow()
        if row < 0: return
        
        item_widget = self.app.file_list.item(row)
        path = item_widget.data(Qt.ItemDataRole.UserRole)
        if not path: return
        
        # 1. 플레이어 잠금 해제
        if hasattr(self.app, 'player_manager'):
            self.app.player_manager.stop_and_release_path(path)
        
        # 2. 파일 삭제 실행
        success, msg = self.app.file_manager.hard_delete_by_path(path)
        
        if success:
            logger.info(f"Hard Delete: {path}")
            self.app.file_list.takeItem(row)
            self.app.update_trash_button_text()
            self.app.lbl_info.setText("영구 삭제되었습니다.")
            self.app.auto_play_next(row)
        else:
            logger.error(f"Hard Delete Failed: {path} - {msg}")
            ThemeMessageBox.critical(self.app, "오류", f"삭제 실패: {msg}")

    def restore_file(self):
        """휴지통 파일 복원"""
        row = self.app.file_list.currentRow()
        item = self.app.file_manager.restore(row)
        if item:
            logger.info(f"Restored: {item.get('path', 'Unknown')}")
            self.app.file_list.blockSignals(True)
            self.app.file_list.takeItem(row)
            self.app.file_list.blockSignals(False)
            self.app.update_trash_button_text()
            self.app.lbl_info.setText(f"복구됨: {item['text']}")
            self.app.auto_play_next(row)

    def restore_all_files(self):
        """휴지통 전체 복원"""
        count = self.app.file_manager.restore_all()
        if count > 0:
            self.app.update_ui_mode()
            self.app.lbl_info.setText(f"파일 {count}개가 모두 복구되었습니다.")
            ThemeMessageBox.information(
                self.app, "완료", 
                f"휴지통에 있던 {count}개의 파일이\n모두 원래 목록으로 복구되었습니다."
            )

    def delete_all_trash_files(self):
        """휴지통 비우기"""
        trash_list = self.app.file_manager.trash_files
        if not trash_list:
            ThemeMessageBox.information(self.app, "알림", "휴지통이 비어 있습니다.")
            return

        reply = ThemeMessageBox.question(
            self.app, "휴지통 비우기",
            f"휴지통에 있는 {len(trash_list)}개의 파일을\n영구 삭제하시겠습니까?\n\n⚠️ 이 작업은 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = self.app.file_manager.clear_trash()
            self.app.update_trash_button_text()
            self.app.lbl_info.setText(f"{deleted_count}개 파일 영구 삭제 완료")
            self.app.reset_viewer_state()

    # =========================================================================
    # 태그 관리
    # =========================================================================

    def toggle_tag_file(self, tag_char):
        """파일에 A/B 태그 토글"""
        row = self.app.file_list.currentRow()
        if row < 0: return
        item_widget = self.app.file_list.item(row)
        path = item_widget.data(Qt.ItemDataRole.UserRole)
        if not path: return

        new_tag = self.app.file_manager.toggle_file_tag(path, tag_char)
        target_path_norm = os.path.normpath(path)
        
        # 목록 내 동일 파일 태그 일괄 업데이트
        for i in range(self.app.file_list.count()):
            current_item = self.app.file_list.item(i)
            current_path = current_item.data(Qt.ItemDataRole.UserRole)
            
            if current_path and os.path.normpath(current_path) == target_path_norm:
                base_text = current_item.text()
                # 기존 태그 제거
                if base_text.startswith("⭐ "): base_text = base_text[2:]
                elif base_text.startswith("🔵 "): base_text = base_text[2:]
                
                prefix = ""
                if new_tag == 'A': prefix = "⭐ "
                elif new_tag == 'B': prefix = "🔵 "
                
                current_item.setText(f"{prefix}{base_text}")

        if new_tag:
            self.app.lbl_info.setText(f"태그 설정: {new_tag}급 ({os.path.basename(path)})")
        else:
            self.app.lbl_info.setText(f"태그 해제: {os.path.basename(path)}")

    def on_clear_all_tags(self, tag_type: str):
        """특정 태그 전체 초기화"""
        count = self.app.file_manager.clear_tags_by_type(tag_type)
        if count > 0:
            self.app.go_to_main_mode()
            self.app.lbl_info.setText(f"{tag_type}급 태그 {count}개 초기화됨")
            ThemeMessageBox.information(
                self.app, "완료", 
                f"{tag_type}급 태그가 모두 초기화되었습니다. ({count}개)"
            )
        else:
            ThemeMessageBox.information(
                self.app, "알림", 
                f"{tag_type}급 태그가 설정된 파일이 없습니다."
            )

    # =========================================================================
    # 해시 마킹 (#)
    # =========================================================================

    def toggle_hash_mark(self):
        """파일명에 # 추가/제거"""
        row = self.app.file_list.currentRow()
        if row < 0: return
        item_widget = self.app.file_list.item(row)
        path = item_widget.data(Qt.ItemDataRole.UserRole)
        if not path: return

        # 현재 모드에 맞는 파일 리스트 사용
        current_list = self.app.file_manager.get_current_list()
        real_index = -1
        for i, item in enumerate(current_list):
            if os.path.normpath(item['path']) == os.path.normpath(path):
                real_index = i
                break
        
        if real_index == -1: return
        current_item = current_list[real_index]
        old_basename = os.path.basename(current_item['path'])
        
        # 파일명에서 # 추가 또는 제거 결정
        new_basename = old_basename[1:] if old_basename.startswith("#") else "#" + old_basename 
        current_pos = self.app.player.position()
        
        # 현재 활성 플레이어의 인덱스 저장 (같은 플레이어 재사용)
        active_idx = self.app.player_manager.active_indices[self.app.player_manager.current_mode]
        active_data = self.app.player_manager.get_active_player()
        
        # 파일 이름 변경 전 핸들 해제
        if active_data:
            active_data['player'].stop()
            active_data['player'].setSource(QUrl())
            active_data['path'] = None
        
        # 이벤트 루프 강제 처리
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # 핸들 해제 후 딜레이를 주고 rename 실행
        def _do_rename_and_play():
            success, msg = self.app.file_manager.rename_file_by_path(current_item['path'], new_basename)
            if success: 
                item_widget.setText(msg) 
                new_path = current_list[real_index]['path']
                item_widget.setData(Qt.ItemDataRole.UserRole, new_path)
                
                # 같은 플레이어에 직접 새 소스 설정
                self.app.player_manager.active_indices[self.app.player_manager.current_mode] = active_idx
                active_data['path'] = new_path
                active_data['player'].setSource(QUrl.fromLocalFile(new_path))
                active_data['item'].setOpacity(1.0)
                active_data['item'].setZValue(10.0)
                
                # 위치 복원 및 재생
                def _seek_and_play():
                    if current_pos > 0:
                        active_data['player'].setPosition(current_pos)
                    if self.app.conf_auto_play:
                        active_data['player'].play()
                    active_data['audio'].setMuted(not self.app.chk_audio.isChecked())
                QTimer.singleShot(50, _seek_and_play)
            else: 
                ThemeMessageBox.warning(self.app, "오류", msg)
        
        QTimer.singleShot(100, _do_rename_and_play)

    # =========================================================================
    # 하이라이트 관리
    # =========================================================================

    def save_current_highlight(self):
        """현재 위치 하이라이트 저장"""
        current_row = self.app.file_list.currentRow()
        current_list = self.app.file_manager.get_current_list()
        
        if 0 <= current_row < len(current_list):
            item = current_list[current_row]
            path = item['path']
            timestamp = self.app.player.position() 
            
            if timestamp == 0 and self.app.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                timestamp = self.app.player.duration()
            
            success, msg = self.app.file_manager.add_highlight(path, timestamp)
            
            if success:
                self.app.setWindowTitle(f"하이라이트 저장됨! [{int(timestamp/1000)}초]")
                QTimer.singleShot(2000, lambda: self.app.setWindowTitle("Pro 동영상 플레이어"))
            else:
                self.app.setWindowTitle(f"⚠ {msg}")
                QTimer.singleShot(2000, lambda: self.app.setWindowTitle("Pro 동영상 플레이어"))

    def delete_current_highlight_item(self):
        """현재 하이라이트 삭제"""
        if self.app.file_manager.current_mode != 'highlight': return
        row = self.app.file_list.currentRow()
        if row < 0: return
        success, msg = self.app.file_manager.delete_highlight(row)
        if success:
            self.app.file_manager.get_highlight_display_list()
            self.app.update_ui_mode()
            self.app.setWindowTitle("삭제 완료")
            self.app.auto_play_next(row)
        else: 
            QMessageBox.warning(self.app, "오류", msg)

    def replay_current_highlight(self):
        """현재 하이라이트 재생"""
        if self.app.file_manager.current_mode != 'highlight': return
        row = self.app.file_list.currentRow()
        if 0 <= row < self.app.file_list.count():
            item_data = self.app.file_manager.get_current_list()[row]
            start_pos = item_data.get('start_pos', 0)
            self.app._execute_seek_and_play(start_pos)

    def on_clear_all_highlights(self):
        """하이라이트 전체 초기화"""
        highlight_list = self.app.file_manager.get_highlight_display_list()
        if not highlight_list:
            ThemeMessageBox.information(self.app, "알림", "저장된 하이라이트가 없습니다.")
            return  

        msg = (
            f"저장된 하이라이트 {len(highlight_list)}개를 모두 삭제하시겠습니까?\n\n"
            "⚠️ 이 작업은 되돌릴 수 없습니다."
        )
        
        reply = ThemeMessageBox.question(
            self.app, "하이라이트 전체 초기화", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            count = self.app.file_manager.clear_all_highlights()
            self.app.go_to_main_mode()
            ThemeMessageBox.information(
                self.app, "완료", 
                f"하이라이트 {count}개가 모두 삭제되었습니다."
            )
