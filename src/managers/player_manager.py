# player_manager.py
import os
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import QSizeF, QUrl

class PlayerManager:
    """
    [격벽 시스템 전담 매니저]
    - 목록(main/A/B/trash): 3개 플레이어 (부드러운 전환)
    - 하이라이트(highlight): 1개 플레이어 (안정성 최우선)
    """
    
    def prepare_player_for_path(self, target_path: str) -> dict:
        """
        [추가] 경로에 적합한 플레이어를 선택하고 활성화 인덱스를 갱신합니다.
        기존에 로드된 플레이어가 있다면 우선적으로 선택합니다.
        """
        pool = self.pools[self.current_mode]
        pool_size = len(pool)
        active_idx = self.active_indices[self.current_mode]
        norm_target = os.path.normpath(target_path)

        # 1. 이미 해당 파일을 물고 있는 플레이어가 있는지 확인
        target_pool_idx = -1
        for i, p_data in enumerate(pool):
            if p_data['path'] and os.path.normpath(p_data['path']) == norm_target:
                target_pool_idx = i
                break
        
        # 2. 없다면 현재 활성화된 플레이어가 아닌 '노는' 플레이어 중 하나 선택
        if target_pool_idx == -1:
            if pool_size > 1:
                candidates = [i for i in range(pool_size) if i != active_idx]
                target_pool_idx = candidates[0]
            else:
                target_pool_idx = 0

        self.active_indices[self.current_mode] = target_pool_idx
        return pool[target_pool_idx]
    
    def __init__(self, video_view, chk_audio_widget):
        self.video_view = video_view
        self.chk_audio = chk_audio_widget
        
        # 5개의 독립 구역 정의
        self.modes = ['main', 'highlight', 'trash', 'A', 'B']
        self.pools = {mode: [] for mode in self.modes}
        self.active_indices = {mode: 0 for mode in self.modes}
        self.current_mode = 'main'
        
        self._init_all_players()

    def _init_all_players(self):
        """구역별 플레이어 생성 (하이라이트는 1개, 나머지는 3개)"""
        for mode in self.modes:
            # [수정] 하이라이트 모드는 1개만 생성하여 단순화 (버그 방지)
            count = 1 if mode == 'highlight' else 3
            
            for _ in range(count):
                player = QMediaPlayer()
                audio = QAudioOutput()
                player.setAudioOutput(audio)
                player.setLoops(QMediaPlayer.Loops.Infinite)
                
                # 화면 생성 및 씬에 추가
                item = QGraphicsVideoItem()
                item.setSize(QSizeF(self.video_view.size()))
                item.setZValue(0.0)
                item.setOpacity(0.0) # 기본적으로 숨김
                self.video_view.scene.addItem(item)
                player.setVideoOutput(item)
                
                # 소리는 기본적으로 끔
                audio.setMuted(True)
                
                self.pools[mode].append({
                    'player': player,
                    'audio': audio,
                    'item': item,
                    'path': None
                })

    def switch_mode(self, target_mode, *, preserve_current=True):
        """Switch visible player mode.

        Passive switches keep existing media sources alive. Destructive release is
        reserved for explicit cleanup paths such as reset, folder close, and delete.
        """
        if target_mode not in self.pools:
            raise ValueError(f"Unknown player mode: {target_mode}")

        if self.current_mode == target_mode:
            return
            
        if not preserve_current:
            old_pool = self.pools[self.current_mode]
            for p_data in old_pool:
                p_data['player'].stop()
                p_data['player'].setSource(QUrl()) # 파일 핸들 즉시 해제
                p_data['item'].setOpacity(0.0)
                p_data['audio'].setMuted(True)
                p_data['path'] = None

        self.current_mode = target_mode
        # 새 모드의 첫 번째 플레이어 준비 (인덱스 초기화 방지)
        active_idx = self.active_indices[target_mode]
        self.pools[target_mode][active_idx]['player'].blockSignals(False)
        
    def release_unfocused_players(self):
        """[추가] 현재 활성화된 플레이어 외의 모든 리소스를 해제하여 성능 확보"""
        curr_pool = self.pools[self.current_mode]
        active_idx = self.active_indices[self.current_mode]
        
        for i, p_data in enumerate(curr_pool):
            if i != active_idx:
                # 다음 재생을 위해 비워둠
                p_data['player'].setSource(QUrl())
                p_data['path'] = None

    def get_active_player(self):
        """현재 모드의 주인공(활성) 플레이어 데이터 반환"""
        idx = self.active_indices[self.current_mode]
        return self.pools[self.current_mode][idx]

    def get_idle_players(self):
        """현재 모드에서 놀고 있는 플레이어 인덱스들 반환"""
        idx = self.active_indices[self.current_mode]
        # [수정] 고정값 3 대신 실제 풀 크기 기반으로 계산
        pool_len = len(self.pools[self.current_mode])
        return [i for i in range(pool_len) if i != idx]

    def get_player_by_index(self, index):
        pool = self.pools[self.current_mode]
        if not 0 <= index < len(pool):
            raise IndexError(f"Player index out of range: {index}")
        return self.pools[self.current_mode][index]

    def engine_slots(self):
        from src.managers.player_engine import PlayerSlot

        slots = []
        slot_id = 0
        for mode, pool in self.pools.items():
            for pool_index, entry in enumerate(pool):
                slots.append(
                    PlayerSlot(
                        slot_id=slot_id,
                        mode=mode,
                        pool_index=pool_index,
                        player=entry["player"],
                        audio=entry["audio"],
                        video_item=entry["item"],
                        expected_path=os.path.normpath(entry["path"]) if entry.get("path") else None,
                        entry=entry,
                    )
                )
                slot_id += 1
        return slots

    def set_active_index(self, index):
        pool = self.pools[self.current_mode]
        if not 0 <= index < len(pool):
            raise IndexError(f"Player index out of range: {index}")
        self.active_indices[self.current_mode] = index

    def resize_all(self, new_size):
        for mode in self.pools:
            for p_data in self.pools[mode]:
                p_data['item'].setSize(new_size)

    def stop_all_in_mode(self, mode):
        if mode in self.pools:
            for p_data in self.pools[mode]:
                p_data['player'].stop()
                p_data['player'].setSource(QUrl())
                p_data['path'] = None
                

    def cleanup(self):
        """프로그램 종료 시 모든 플레이어 정지 및 파일 잠금 해제"""
        for mode in self.pools:
            for p_data in self.pools[mode]:
                p_data['player'].stop()
                p_data['player'].setSource(QUrl()) # 파일 핸들 해제
                p_data['path'] = None
                
    def stop_and_release_path(self, target_path):
        """특정 경로를 잡고 있는 모든 플레이어를 찾아 정지 및 해제"""
        if not target_path: return False
        target_norm = os.path.normpath(target_path) # import os 필요 (상단에 있는지 확인)
        found = False
        
        for mode_name, pool in self.pools.items():
            for p_data in pool:
                p_path = p_data.get('path')
                if p_path and os.path.normpath(p_path) == target_norm:
                    p_data['player'].stop()
                    p_data['player'].setSource(QUrl())
                    p_data['item'].setOpacity(0.0)
                    p_data['item'].setZValue(0.0)
                    p_data['audio'].setMuted(True)
                    p_data['path'] = None
                    found = True
        return found
