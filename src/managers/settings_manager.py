# settings_manager.py
from PyQt6.QtCore import QSettings
from src.core import consts

class SettingsManager:
    """
    [설정 관리자]
    QSettings를 캡슐화하여 애플리케이션 전역 설정을 안전하게 관리합니다.
    형변환(Type Casting)과 기본값 처리를 담당합니다.
    """
    def __init__(self):
        # QSettings(Organization, Application)
        self.settings = QSettings("MyVideoApp", consts.APP_NAME)
        
    def get(self, key, default=None, type_cls=None):
        """
        QSettings에서 값을 안전하게 가져옵니다.
        type_cls가 지정되면 해당 타입으로 형변환을 시도합니다.
        """
        val = self.settings.value(key, default)
        
        if type_cls is not None:
            # 1. 이미 올바른 타입인 경우
            if isinstance(val, type_cls):
                return val
            
            # 2. Boolean 처리 (문자열 'true'/'on' 등 대응)
            if type_cls is bool:
                if isinstance(val, str):
                    return val.lower() in ('true', '1', 'yes', 'on')
                # 숫자인 경우 (0=False, 그외=True)
                try:
                    return bool(int(val))
                except (ValueError, TypeError):
                    return bool(val)
            
            # 3. 그 외 타입 변환 시도
            try:
                return type_cls(val)
            except (ValueError, TypeError):
                return default
                
        return val

    def set(self, key, value):
        self.settings.setValue(key, value)
        
    def sync(self):
        self.settings.sync()

    # --- Typed Accessors (속성 접근자) ---
    # main.py에서 사용하는 모든 설정 키 포함
    
    @property
    def seek_interval(self) -> int:
        return self.get("seek_interval", consts.DEFAULT_SEEK_INTERVAL, int)
    
    @seek_interval.setter
    def seek_interval(self, value: int):
        self.set("seek_interval", value)

    @property
    def auto_play(self) -> bool:
        return self.get("auto_play", True, bool)
    
    @auto_play.setter
    def auto_play(self, value: bool):
        self.set("auto_play", value)

    @property
    def wheel_action(self) -> int:
        return self.get("wheel_action", 0, int)

    @wheel_action.setter
    def wheel_action(self, value: int):
        self.set("wheel_action", value)
        
    @property
    def wheel_interval(self) -> int:
        return self.get("wheel_interval", consts.DEFAULT_WHEEL_INTERVAL, int)

    @wheel_interval.setter
    def wheel_interval(self, value: int):
        self.set("wheel_interval", value)
        
    @property
    def wheel_reverse(self) -> bool:
        return self.get("wheel_reverse", False, bool)

    @wheel_reverse.setter
    def wheel_reverse(self, value: bool):
        self.set("wheel_reverse", value)

    @property
    def privacy_mode(self) -> bool:
        return self.get("use_privacy_mode", False, bool)
    
    @privacy_mode.setter
    def privacy_mode(self, value: bool):
        self.set("use_privacy_mode", value)
        
    @property
    def default_skip(self) -> str:
        return self.get("default_skip", consts.DEFAULT_SKIP_RATIO, str)

    @default_skip.setter
    def default_skip(self, value: str):
        self.set("default_skip", value)
