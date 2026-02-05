# threads.py (BackgroundIndexer 클래스 전체 수정)
import os
from PyQt6.QtCore import QThread, pyqtSignal
from src.utils.utils import VIDEO_EXTENSIONS

class BackgroundIndexer(QThread):
    finished_signal = pyqtSignal(int)
    data_signal = pyqtSignal(list)  # 청크(묶음) 단위로 전송

    def __init__(self, folder_history):
        super().__init__()
        self.folder_history = folder_history
        self.is_running = True
        self.chunk_size = 200  # 200개씩 끊어서 메인 스레드로 전송 (프리징 방지)

    def run(self):
        self.total_count = 0
        current_chunk = []
        
        for folder_path in self.folder_history:
            if not self.is_running: break
            if not os.path.exists(folder_path): continue
            
            # 재귀 스캔 시작
            self._scan_recursive(folder_path, current_chunk)
            
        # 루프 종료 후 남은 데이터 전송
        if current_chunk:
            self.data_signal.emit(current_chunk)
            
        self.finished_signal.emit(self.total_count)

    def _scan_recursive(self, base_path, chunk):
        """os.scandir를 사용한 고속 재귀 스캔"""
        try:
            with os.scandir(base_path) as it:
                for entry in it:
                    if not self.is_running: return
                    
                    if entry.is_file():
                        if entry.name.lower().endswith(VIDEO_EXTENSIONS):
                            full_path = os.path.normpath(entry.path)
                            file_data = {
                                'path': full_path,
                                'name': entry.name,
                                'size': entry.stat().st_size,
                                'folder': base_path
                            }
                            chunk.append(file_data)
                            self.total_count += 1
                            
                            # 청크 크기가 차면 UI 스레드로 발송 후 비움
                            if len(chunk) >= self.chunk_size:
                                self.data_signal.emit(list(chunk))
                                chunk.clear()
                                
                    elif entry.is_dir():
                        self._scan_recursive(entry.path, chunk)
        except PermissionError:
            pass  # 접근 권한 없는 폴더 무시