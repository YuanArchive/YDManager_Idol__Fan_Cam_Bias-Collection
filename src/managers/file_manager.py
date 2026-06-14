# file_manager.py
import os
import json
import unicodedata
import tempfile
import logging
import stat
from functools import lru_cache

from PyQt6.QtCore import QObject, pyqtSignal

from send2trash import send2trash
from src.core import consts
from src.utils.utils import VIDEO_EXTENSIONS
from src.core.threads import BackgroundIndexer

REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_reparse_point(entry):
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attributes & REPARSE_POINT_ATTRIBUTE)
    except OSError:
        return True


class FileManager(QObject):
    # Signals
    indexing_started = pyqtSignal()
    indexing_finished = pyqtSignal(int)
    indexing_data_received = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        consts.migrate_legacy_index_files()
        self.root_folder = ""
        self.main_files = []   
        self.trash_files = []
        self.highlight_list = [] 
        
        self.current_mode = 'main'
        self.filter_type = None 
        self.is_trash_mode = False
        
        # 인덱서 스레드
        self.indexer_thread = None
        self._removed_folder_keys = set()
        self._global_cache_dirty = False

        # 파일 경로 설정
        self.tags_file_path = consts.TAGS_FILE
        self.highlights_file_path = consts.HIGHLIGHTS_FILE
        self.history_file_path = consts.HISTORY_FILE
        self.trash_cache_path = consts.TRASH_CACHE_FILE
        self.global_cache_path = consts.GLOBAL_CACHE_FILE
        
        # 데이터 로드
        self.file_tags = self.load_normalized_dict(self.tags_file_path)
        self.highlights = self.load_normalized_dict(self.highlights_file_path)
        
        self.folder_history = self.load_json(self.history_file_path)
        if not isinstance(self.folder_history, list): self.folder_history = []
        self.folder_history = [os.path.normpath(p) for p in self.folder_history]
        
        self.global_files = self.load_json(self.global_cache_path)
        if not isinstance(self.global_files, list): self.global_files = []
        
        self.search_keyword = "" 
        self.load_trash()

    def set_view_state(self, mode: str, filter_type: str = None, is_trash: bool = False):
        """뷰 상태를 일괄 변경합니다."""
        self.current_mode = mode
        self.filter_type = filter_type
        self.is_trash_mode = is_trash
        
    def start_indexing(self):
        """백그라운드 인덱싱을 시작합니다."""
        if self.indexer_thread and self.indexer_thread.isRunning():
            return

        history = list(self.get_folder_history())
        if not history:
            return

        self.indexing_started.emit()
        
        self.indexer_thread = BackgroundIndexer(history)
        self.indexer_thread.data_signal.connect(self._on_worker_data)
        self.indexer_thread.finished_signal.connect(self._on_worker_finished)
        self.indexer_thread.start()
        
    def stop_indexing(self):
        """인덱싱 스레드를 안전하게 종료합니다."""
        if self.indexer_thread and self.indexer_thread.isRunning():
            self.indexer_thread.is_running = False
            self.indexer_thread.requestInterruption()
            self.indexer_thread.quit()
            if not self.indexer_thread.wait(3000):
                logging.warning("Background indexer did not stop within 3000 ms.")
                return False
            self.indexer_thread = None
            self._persist_global_cache_if_dirty()
        return True
            
    def _on_worker_data(self, chunk_list):
        filtered_chunk = self._filter_index_chunk(chunk_list)
        if not filtered_chunk:
            return

        self.update_global_cache(filtered_chunk, persist=False)
        self.indexing_data_received.emit(filtered_chunk)
        
    def _on_worker_finished(self, count):
        self._persist_global_cache_if_dirty()
        self.indexing_finished.emit(count)

    def _folder_key_with_separator(self, path):
        folder_key = self._get_norm_key(path)
        if folder_key and not folder_key.endswith(os.sep):
            folder_key += os.sep
        return folder_key

    def _is_within_folder_key(self, item_folder, folder_key):
        item_folder_key = self._get_norm_key(item_folder)
        if item_folder_key and not item_folder_key.endswith(os.sep):
            item_folder_key += os.sep
        return item_folder_key.startswith(folder_key)

    def _filter_index_chunk(self, chunk_list):
        if not self.folder_history:
            return []

        trash_keys = {
            self._get_norm_key(item.get('path'))
            for item in self.trash_files
            if isinstance(item, dict) and item.get('path')
        }
        active_folder_keys = [
            self._folder_key_with_separator(path)
            for path in self.folder_history
        ]
        filtered = []

        for item in chunk_list:
            clean_item = self._normalize_file_item(item)
            if not clean_item:
                continue

            item_key = self._get_norm_key(clean_item['path'])
            if item_key in trash_keys:
                continue

            item_folder = clean_item.get('folder', os.path.dirname(clean_item['path']))
            item_folder_key = self._folder_key_with_separator(item_folder)
            if item_folder_key in self._removed_folder_keys:
                continue

            if any(self._is_within_folder_key(item_folder, active_key) for active_key in active_folder_keys):
                filtered.append(clean_item)

        return filtered

    # --- [Core] 경로 정규화 및 캐싱 (최적화 핵심) ---
    @lru_cache(maxsize=4096)  # 캐시 용량 증설
    def _get_canonical_path(self, path):
        """
        [One Truth] 모든 경로 비교의 기준이 되는 함수입니다.
        절대 경로 + 소문자(Windows) + 유니코드 정규화(NFC)를 수행합니다.
        """
        if not path: return ""
        try:
            # 1. 절대 경로 및 구분자 통일
            norm_path = os.path.normpath(os.path.abspath(path))
            # 2. 대소문자 통일 (Windows: lower, Linux: 그대로)
            norm_path = os.path.normcase(norm_path)
            # 3. 한글 자모 분리 방지 (NFC)
            return unicodedata.normalize('NFC', norm_path)
        except Exception:
            return str(path)

    def _get_norm_key(self, path):
        """딕셔너리 키 조회용 헬퍼 (내부적으로 캐시된 함수 사용)"""
        return self._get_canonical_path(path)

    def _normalize_path(self, path):
        """경로 정규화 (NFC 적용)"""
        if not path: return ""
        return unicodedata.normalize('NFC', os.path.normpath(path))

    def _normalize_text(self, text):
        """[추가] 검색용 텍스트 정규화 (한글 자모 분리 방지)"""
        if not text: return ""
        return unicodedata.normalize('NFC', text)

    def _sanitize_highlight_times(self, key):
        raw_times = self.highlights.get(key, [])
        if not isinstance(raw_times, list):
            raw_times = []

        valid_times = []
        seen_times = set()
        for timestamp in raw_times:
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                continue
            timestamp = int(timestamp)
            if timestamp < 0 or timestamp in seen_times:
                continue
            seen_times.add(timestamp)
            valid_times.append(timestamp)

        valid_times.sort()
        self.highlights[key] = valid_times
        return valid_times

    # --- 데이터 입출력 ---
    def load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_json(self, path, data):
        """원자적 쓰기(Atomic Write)로 데이터 손상 방지"""
        dir_name = os.path.dirname(path)
        try:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', dir=dir_name, delete=False, encoding='utf-8') as tf:
                temp_name = tf.name
                json.dump(data, tf, ensure_ascii=False, indent=4)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(temp_name, path)
            return True
        except Exception as e:
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)
            logging.error(f"파일 저장 실패: {e}")
            return False

    def load_normalized_dict(self, path):
        data = self.load_json(path)
        if isinstance(data, dict):
            return {self._get_norm_key(k): v for k, v in data.items()}
        return {}
    
    def reset_all_data(self):
        if self.stop_indexing() is False:
            logging.warning("Reset aborted because the background indexer is still running.")
            return False
        self.file_tags = {}
        self.highlights = {}
        self.folder_history = []
        self.global_files = []
        self.trash_files = []
        
        targets = [
            self.tags_file_path, self.highlights_file_path,
            self.history_file_path, self.trash_cache_path,
            self.global_cache_path
        ]
        for path in targets:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        return True

    def _rebuild_tag_cache(self):
        """태그 딕셔너리 키 재정렬"""
        new_tags = {}
        for path, tag in self.file_tags.items():
            new_tags[self._get_norm_key(path)] = tag
        self.file_tags = new_tags

    def _normalize_file_item(self, item):
        if not isinstance(item, dict):
            return None

        path = item.get('path')
        if not path:
            return None

        clean_item = item.copy()
        clean_item['path'] = self._normalize_path(path)
        clean_item.setdefault('name', os.path.basename(clean_item['path']))
        clean_item['folder'] = os.path.dirname(clean_item['path'])
        return clean_item

    def _trash_path_keys(self):
        return {
            self._get_norm_key(clean_item['path'])
            for clean_item in (self._normalize_file_item(item) for item in self.trash_files)
            if clean_item
        }

    # --- 데이터 관리 ---
    def update_global_cache(self, new_file_list, persist=True):
        unique_map = {}
        for item in self.global_files:
            clean_item = self._normalize_file_item(item)
            if clean_item:
                unique_map[self._get_norm_key(clean_item['path'])] = clean_item

        for item in new_file_list:
            clean_item = self._normalize_file_item(item)
            if clean_item:
                key = self._get_norm_key(clean_item['path'])
                unique_map[key] = clean_item
        
        self.global_files = list(unique_map.values())
        self.global_files.sort(key=lambda x: x['name'].lower())
        if persist:
            self.save_json(self.global_cache_path, self.global_files)
        else:
            self._global_cache_dirty = True

    def _persist_global_cache_if_dirty(self):
        if not self._global_cache_dirty:
            return True

        saved = self.save_json(self.global_cache_path, self.global_files)
        if saved:
            self._global_cache_dirty = False
        return saved

    def save_trash(self):
        clean_list = []
        seen_keys = set()

        for item in self.trash_files:
            path = item.get('path') if isinstance(item, dict) else None
            if not path:
                continue
            path_key = self._get_norm_key(path)
            if path_key in seen_keys: continue
            seen_keys.add(path_key)

            clean_item = item.copy()
            if 'text' in clean_item: del clean_item['text']
            if 'folder' not in clean_item: 
                 clean_item['folder'] = os.path.dirname(path)
            clean_list.append(clean_item)
            
        self.save_json(self.trash_cache_path, clean_list)
        self.trash_files = clean_list
        for item in self.trash_files:
            if 'text' not in item:
                item['text'] = os.path.basename(item['path'])

    def load_trash(self):
        data = self.load_json(self.trash_cache_path)
        if isinstance(data, list):
            valid_trash = []
            seen_paths = set()
            for item in data:
                path = item.get('path') if isinstance(item, dict) else None
                if not path:
                    continue
                key = self._get_norm_key(path)
                if key in seen_paths: continue 
                seen_paths.add(key)
                
                if 'text' not in item:
                    item['text'] = item.get('name', os.path.basename(path))
                valid_trash.append(item)
            self.trash_files = valid_trash
        else:
            self.trash_files = []

    def update_history_order(self, new_path_list):
        self.folder_history = new_path_list
        self.save_json(self.history_file_path, self.folder_history)    

    def add_folder_to_history(self, path):
        path = self._normalize_path(path)
        self._removed_folder_keys.discard(self._folder_key_with_separator(path))
        lower_history = [self._get_norm_key(p) for p in self.folder_history]
        if self._get_norm_key(path) not in lower_history:
            self.folder_history.insert(0, path)
            self.save_json(self.history_file_path, self.folder_history)
            return True
        return False

    def remove_folder_from_history(self, index):
        if 0 <= index < len(self.folder_history):
            if self.stop_indexing() is False:
                return None
            removed_path = self.folder_history.pop(index)
            self._removed_folder_keys.add(self._folder_key_with_separator(removed_path))
            self.save_json(self.history_file_path, self.folder_history)
            
            # 히스토리 삭제 시 관련 글로벌 캐시도 정리
            if self.global_files:
                norm_removed_key = self._folder_key_with_separator(removed_path)
                    
                new_global = []
                for item in self.global_files:
                    clean_item = self._normalize_file_item(item)
                    if not clean_item:
                        continue

                    item_folder = clean_item.get('folder', os.path.dirname(clean_item['path']))
                    item_folder_key = self._get_norm_key(item_folder)
                    
                    # 해당 폴더에 속하지 않는 것만 남김
                    if not self._is_within_folder_key(item_folder, norm_removed_key):
                        new_global.append(clean_item)
                self.global_files = new_global
                self.save_json(self.global_cache_path, self.global_files)
            return removed_path
        return None

    def get_folder_history(self):
        return self.folder_history

    # --- [Action] 삭제/복구 로직 ---

    def soft_delete_by_path(self, path):
        target_key = self._get_canonical_path(path)
        
        # 중복 방지
        if target_key in self._trash_path_keys():
            return None

        deleted_item = None

        # Main List에서 삭제
        for i in range(len(self.main_files) - 1, -1, -1):
            if self._get_canonical_path(self.main_files[i]['path']) == target_key:
                deleted_item = self.main_files.pop(i)

        # Global Cache에서 삭제 및 데이터 확보
        if hasattr(self, 'global_files') and self.global_files:
            global_deleted = False
            clean_global_files = []
            for item in self.global_files:
                clean_item = self._normalize_file_item(item)
                if not clean_item:
                    continue

                if self._get_canonical_path(clean_item['path']) == target_key:
                    if deleted_item is None:
                        deleted_item = clean_item.copy()
                    global_deleted = True
                else:
                    clean_global_files.append(clean_item)
            
            if global_deleted or len(clean_global_files) != len(self.global_files):
                self.global_files = clean_global_files
                self.save_json(self.global_cache_path, self.global_files)

        # 휴지통 이동
        if deleted_item:
            if 'text' not in deleted_item: 
                deleted_item['text'] = os.path.basename(path)
            self.trash_files.append(deleted_item)
            self.save_trash()
            return deleted_item
            
        elif os.path.exists(path):
            newItem = {
                'path': path,
                'text': os.path.basename(path),
                'folder': os.path.dirname(path)
            }
            self.trash_files.append(newItem)
            self.save_trash()
            return newItem
            
        return None

    def restore(self, index):
        if self.current_mode != 'trash': return None
        if not (0 <= index < len(self.trash_files)): return None
        item = self.trash_files[index]
        path = item.get('path') if isinstance(item, dict) else None
        if not path or not os.path.exists(path):
            return None

        item = self.trash_files.pop(index)
        
        if 'folder' not in item:
            item['folder'] = os.path.dirname(item['path'])
        if 'name' not in item:
            item['name'] = os.path.basename(item['path'])
        item['text'] = item['name'] 

        # Global Cache 복구
        item_key = self._get_norm_key(item['path'])
        is_in_global = False
        clean_global_files = []
        if self.global_files:
            for g_item in self.global_files:
                clean_item = self._normalize_file_item(g_item)
                if not clean_item:
                    continue

                if self._get_norm_key(clean_item['path']) == item_key:
                    is_in_global = True
                clean_global_files.append(clean_item)
        
        if not is_in_global:
            clean_global_files.append(self._normalize_file_item(item) or item)
        if clean_global_files != self.global_files:
            self.global_files = clean_global_files
            self.global_files.sort(key=lambda x: x['path'])
            self.save_json(self.global_cache_path, self.global_files)

        # [수정] Main List 복구 판단 (폴더 포함 관계 정밀 체크)
        if self.root_folder:
            current_root_key = self._get_norm_key(self.root_folder)
            # 1. 루트 폴더와 파일 경로가 아예 같은 경우 (있을 수 없지만 방어코드)
            # 2. 파일 경로가 루트 폴더 + 구분자로 시작하는 경우 (하위 파일)
            if item_key.startswith(current_root_key + os.sep):
                self.main_files.append(item)
                self.main_files.sort(key=lambda x: os.path.basename(x['path']).lower())
        
        self.save_trash()
        return item

    def restore_all(self):
        if not self.trash_files: return 0
        count = 0
        for i in range(len(self.trash_files) - 1, -1, -1):
            if self.restore(i):
                count += 1
        return count

    # --- [Action] 하이라이트/태그 ---
    def add_highlight(self, file_path, timestamp):
        key = self._get_norm_key(file_path)
        if key not in self.highlights:
            self.highlights[key] = []
        times = self._sanitize_highlight_times(key)
        for t in times:
            if abs(t - timestamp) < 1000: return False, "이미 저장된 구간입니다."
        times.append(int(timestamp))
        times.sort()
        self.highlights[key] = times
        self.save_json(self.highlights_file_path, self.highlights)
        return True, "저장 완료"

    def delete_highlight(self, index):
        if self.current_mode != 'highlight': return False, "모드 불일치"
        if 0 <= index < len(self.highlight_list):
            item = self.highlight_list[index]
            key = self._get_norm_key(item['path'])
            target_time = item['start_pos']
            if key in self.highlights and target_time in self.highlights[key]:
                self.highlights[key].remove(target_time)
                if not self.highlights[key]: del self.highlights[key]
                self.save_json(self.highlights_file_path, self.highlights)
                return True, "삭제됨"
        return False, "실패"

    def get_highlight_display_list(self):
        self.highlight_list = []
        seen_keys = set()
        for path_key in list(self.highlights):
            if not os.path.exists(path_key): continue
            times = self._sanitize_highlight_times(path_key)
            
            norm_key = self._get_norm_key(path_key)
            if norm_key in seen_keys: continue
            seen_keys.add(norm_key)

            base_name = os.path.basename(path_key)
            tag = self.file_tags.get(norm_key)
            prefix = "⭐ " if tag == 'A' else ("🔵 " if tag == 'B' else "")
            
            for t in times:
                seconds = t // 1000; m, s = divmod(seconds, 60)
                display_text = f"{prefix}★ {base_name}   [{m:02d}:{s:02d}]"
                self.highlight_list.append({
                    'path': path_key, 'text': display_text, 'start_pos': t
                })
        return self.highlight_list

    def scan_folder(self, folder_path):
        """폴더 스캔 및 정렬 (중복 방지 추가)"""
        self.root_folder = self._normalize_path(folder_path)
        self.main_files = []
        trash_keys = self._trash_path_keys()
        seen_keys = set() # [Fix] 중복 방지용 Set
        
        if os.path.exists(self.root_folder):
            for full in self._iter_video_paths(self.root_folder):
                key = self._get_norm_key(full)

                if key not in trash_keys and key not in seen_keys:
                    seen_keys.add(key)
                    self.main_files.append({
                        'path': full,
                        'text': self._format_display_text(full)
                    })
        
        self.main_files.sort(key=lambda x: os.path.basename(x['path']).lower())

    def load_main_files_from_cache(self, folder_path):
        """전역 캐시에서 현재 폴더 목록을 복원합니다. 캐시가 없으면 False를 반환합니다."""
        self.root_folder = self._normalize_path(folder_path)
        self.main_files = []

        if not self.global_files:
            return False

        root_key = self._folder_key_with_separator(self.root_folder)
        trash_keys = {
            self._get_norm_key(item.get('path'))
            for item in self.trash_files
            if isinstance(item, dict) and item.get('path')
        }
        seen_keys = set()

        for item in self.global_files:
            clean_item = self._normalize_file_item(item)
            if not clean_item:
                continue

            path = clean_item['path']
            path_key = self._get_norm_key(path)
            if path_key in trash_keys or path_key in seen_keys:
                continue

            item_folder = clean_item.get('folder', os.path.dirname(path))
            if not self._is_within_folder_key(item_folder, root_key):
                continue

            if not os.path.exists(path):
                continue

            seen_keys.add(path_key)
            self.main_files.append({
                'path': path,
                'text': self._format_display_text(path)
            })

        self.main_files.sort(key=lambda x: os.path.basename(x['path']).lower())
        return bool(self.main_files)

    def _iter_video_paths(self, folder_path):
        try:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(VIDEO_EXTENSIONS):
                            yield self._normalize_path(entry.path)
                        elif entry.is_dir(follow_symlinks=False) and not _is_reparse_point(entry):
                            yield from self._iter_video_paths(entry.path)
                    except OSError:
                        continue
        except OSError:
            return

    def toggle_file_tag(self, path, tag_char):
        key = self._get_norm_key(path)
        current = self.file_tags.get(key)
        if current == tag_char:
            if key in self.file_tags: del self.file_tags[key]
            new_tag = None
        else:
            self.file_tags[key] = tag_char
            new_tag = tag_char
            
        self.save_json(self.tags_file_path, self.file_tags)
        
        # 메모리 동기화
        for item in self.main_files:
            if self._get_norm_key(item['path']) == key:
                item['text'] = self._format_display_text(item['path'])
                break
        return new_tag

    def _format_display_text(self, path):
        key = self._get_norm_key(path)
        tag = self.file_tags.get(key)
        prefix = "⭐ " if tag == 'A' else ("🔵 " if tag == 'B' else "")
        return f"{prefix}{os.path.basename(path)}"

    def set_search_keyword(self, text):
        # [버그 수정] 경로 정규화 대신 텍스트 정규화 사용
        self.search_keyword = self._normalize_text(text.strip().lower())

    def get_current_list(self):
        trash_keys = self._trash_path_keys()
        target_list = []
        is_global_search = False

        if self.current_mode == 'trash':
            target_list = self.trash_files
        elif self.current_mode == 'highlight':
            return self.get_highlight_display_list()
        else:
            if self.filter_type:
                temp = []
                for k, tag in self.file_tags.items():
                    if tag == self.filter_type and k not in trash_keys and os.path.exists(k):
                        prefix = "⭐ " if tag == 'A' else "🔵 "
                        temp.append({'path': k, 'text': f"{prefix}{os.path.basename(k)}"})
                target_list = temp
            else:
                if self.search_keyword:
                    is_global_search = True
                    target_list = self.global_files
                else:
                    target_list = self.main_files

        if self.search_keyword:
            result = []
            keyword = self.search_keyword
            seen_search_keys = set() # [Fix] 검색 결과 중복 방지
            
            for item in target_list:
                item = self._normalize_file_item(item)
                if not item:
                    continue
                item_path = item['path']
                key = self._get_norm_key(item_path)
                
                if key in trash_keys or key in seen_search_keys: continue
                if is_global_search and not os.path.exists(item_path):
                    continue
                
                search_text = item.get('text', item.get('name', os.path.basename(item_path)))
                norm_text = self._normalize_text(search_text).lower()
                
                if keyword in norm_text:
                    seen_search_keys.add(key) # 중복 체크 등록
                    if is_global_search:
                        new_item = item.copy()
                        new_item['text'] = self._format_display_text(item_path)
                        result.append(new_item)
                    else:
                        result.append(item)
            
            result.sort(key=lambda x: os.path.basename(x['path']).lower())
            return result
        
        clean_target_list = []
        for item in target_list:
            clean_item = self._normalize_file_item(item)
            if clean_item:
                clean_target_list.append(clean_item)

        clean_target_list.sort(key=lambda x: os.path.basename(x['path']).lower())
        return clean_target_list

    def rename_file_by_path(self, old_path, new_name):
        if self.current_mode != 'main': return False, "변경 불가"
        
        old_key = self._get_norm_key(old_path)
        target = None
        for item in self.main_files:
            if not isinstance(item, dict) or not item.get('path'):
                continue
            if self._get_norm_key(item['path']) == old_key:
                target = item; break
        
        if not target: return False, "파일 없음"
        
        dir_name = os.path.dirname(old_path)
        new_path = os.path.join(dir_name, new_name)
        new_path = self._normalize_path(new_path)
        new_key = self._get_norm_key(new_path)
        
        try:
            os.rename(old_path, new_path)
            target['path'] = new_path
            
            if old_key in self.file_tags:
                self.file_tags[new_key] = self.file_tags.pop(old_key)
                self.save_json(self.tags_file_path, self.file_tags)
            
            if old_key in self.highlights:
                self.highlights[new_key] = self.highlights.pop(old_key)
                self.save_json(self.highlights_file_path, self.highlights)

            global_updated = False
            clean_global_files = []
            for item in self.global_files:
                clean_item = self._normalize_file_item(item)
                if not clean_item:
                    global_updated = True
                    continue

                if self._get_norm_key(clean_item['path']) == old_key:
                    clean_item['path'] = new_path
                    clean_item['name'] = os.path.basename(new_path)
                    clean_item['folder'] = dir_name
                    clean_item['text'] = self._format_display_text(new_path)
                    global_updated = True
                clean_global_files.append(clean_item)
            if global_updated:
                self.global_files = clean_global_files
                self.global_files.sort(key=lambda x: os.path.basename(x['path']).lower())
                self.save_json(self.global_cache_path, self.global_files)

            target['text'] = self._format_display_text(new_path)
            return True, target['text']
        except Exception as e: return False, str(e)
    
    def hard_delete_by_path(self, path):
        try:
            if os.path.exists(path):
                send2trash(path)
            
            key = self._get_canonical_path(path)
            
            tag_keys_to_del = [k for k in self.file_tags if self._get_canonical_path(k) == key]
            for k in tag_keys_to_del: del self.file_tags[k]
                
            hl_keys_to_del = [k for k in self.highlights if self._get_canonical_path(k) == key]
            for k in hl_keys_to_del: del self.highlights[k]

            self.trash_files = [
                item
                for item in self.trash_files
                if (
                    isinstance(item, dict)
                    and item.get('path')
                    and self._get_canonical_path(item['path']) != key
                )
            ]
            self._remove_from_search_data(path)
            
            self.save_trash()
            self.save_json(self.tags_file_path, self.file_tags)
            self.save_json(self.highlights_file_path, self.highlights)
            self._rebuild_tag_cache()
            
            return True, "삭제 성공"
        except PermissionError:
            return False, "파일이 다른 프로그램에서 사용 중입니다."
        except Exception as e:
            return False, f"삭제 실패: {str(e)}"

    def clear_trash(self):
        count = 0
        deleted_paths = [] 
        
        for item in list(self.trash_files):
            item_path = item.get('path') if isinstance(item, dict) else None
            if not item_path:
                continue

            try:
                abs_path = os.path.abspath(item_path)
                if os.path.exists(abs_path):
                    send2trash(abs_path)
                
                key = self._get_canonical_path(item_path)
                
                tags_to_del = [k for k in self.file_tags if self._get_canonical_path(k) == key]
                for k in tags_to_del: del self.file_tags[k]
                
                hls_to_del = [k for k in self.highlights if self._get_canonical_path(k) == key]
                for k in hls_to_del: del self.highlights[k]

                deleted_paths.append(item_path)
                count += 1
                
            except Exception as e:
                print(f"Failed to delete {item_path}: {e}")
                continue

        if deleted_paths:
            deleted_keys = {self._get_canonical_path(path) for path in deleted_paths}
            self.trash_files = [
                item
                for item in self.trash_files
                if (
                    isinstance(item, dict)
                    and item.get('path')
                    and self._get_canonical_path(item['path']) not in deleted_keys
                )
            ]

            if hasattr(self, 'global_files'):
                self.global_files = [
                    clean_item
                    for item in self.global_files
                    if (clean_item := self._normalize_file_item(item))
                    and self._get_canonical_path(clean_item['path']) not in deleted_keys
                ]
                self.save_json(self.global_cache_path, self.global_files)
        
        self.save_trash()
        self.save_json(self.tags_file_path, self.file_tags)
        self.save_json(self.highlights_file_path, self.highlights)
        self._rebuild_tag_cache()
        
        return count
    
    def _remove_from_search_data(self, target_path):
        norm_target = self._get_canonical_path(target_path)
        
        self.main_files = [
            clean_item
            for item in self.main_files
            if (clean_item := self._normalize_file_item(item))
            and self._get_canonical_path(clean_item['path']) != norm_target
        ]
        
        if hasattr(self, 'global_files'):
            original_count = len(self.global_files)
            self.global_files = [
                clean_item
                for item in self.global_files
                if (clean_item := self._normalize_file_item(item))
                and self._get_canonical_path(clean_item['path']) != norm_target
            ]
            
            if len(self.global_files) != original_count:
                self.save_json(self.global_cache_path, self.global_files)
                
    def clear_tags_by_type(self, tag_type):
        keys_to_remove = [k for k, v in self.file_tags.items() if v == tag_type]
        count = len(keys_to_remove)
        
        for k in keys_to_remove:
            del self.file_tags[k]
        
        if count > 0:
            self.save_json(self.tags_file_path, self.file_tags)
            target_keys = set(keys_to_remove)
            for item in self.main_files:
                if self._get_norm_key(item['path']) in target_keys:
                    item['text'] = self._format_display_text(item['path'])
                    
        return count
    
    def clear_all_highlights(self):
        """저장된 모든 하이라이트 데이터를 삭제합니다."""
        count = 0
        # 전체 하이라이트 개수 카운트
        for key in self.highlights:
            count += len(self.highlights[key])
            
        self.highlights = {} # 딕셔너리 초기화
        self.save_json(self.highlights_file_path, self.highlights)
        self.highlight_list = [] # 메모리 리스트도 초기화
        
        return count
