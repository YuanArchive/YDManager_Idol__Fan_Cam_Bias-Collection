import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 로그 저장 폴더
LOG_DIR = os.path.join(os.getcwd(), "logs")

# 프라이버시 모드 플래그
_PRIVACY_MODE = False


def setup_logging():
    """
    로깅 시스템을 초기화합니다.
    - logs 폴더 생성
    - 파일 핸들러 (최대 5MB, 백업 3개)
    - 콘솔 핸들러
    """
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # 기본 로거 설정
    logger = logging.getLogger("YDManager")
    logger.setLevel(logging.DEBUG) # 모든 레벨 캡처

    # 이미 핸들러가 있다면 제거 (중복 방지)
    if logger.handlers:
        logger.handlers.clear()

    # 포맷터 정의
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 프라이버시 필터 생성
    privacy_filter = PrivacyFilter()


    # 1. 파일 핸들러 (RotatingFileHandler)
    log_file = os.path.join(LOG_DIR, "app.log")
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024, # 5MB
        backupCount=3, 
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(privacy_filter) # 필터 추가
    logger.addHandler(file_handler)


    # 2. 콘솔 핸들러 (터미널 출력용)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO) # 콘솔에는 INFO 이상만
    console_handler.setFormatter(formatter)
    console_handler.addFilter(privacy_filter) # 필터 추가
    logger.addHandler(console_handler)

    
    # 3. 전역 예외 처리 (Uncaught Exceptions)
    sys.excepthook = handle_exception
    
    logger.info("==========================================")
    logger.info("YDManager Started")
    logger.info("==========================================")
    
    return logger

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    처리되지 않은 예외(Crash)를 로그에 기록합니다.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = logging.getLogger("YDManager")
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

def get_logger():
    """설정된 로거 인스턴스를 반환합니다."""
    return logging.getLogger("YDManager")

def open_log_folder():
    """로그 파일이 있는 폴더를 엽니다."""
    try:
        os.startfile(LOG_DIR)
    except Exception as e:
        print(f"로그 폴더 열기 실패: {e}")

# 평문 텍스트 패턴 (단순화된 파일 경로 감지)
import re
FILE_PATH_PATTERN = re.compile(r'[a-zA-Z]:\\[^/:*?"<>|\r\n]+')

class PrivacyFilter(logging.Filter):
    """
    프라이버시 모드 활성화 시 로그 메시지에 포함된 파일 경로를 마스킹합니다.
    """
    def filter(self, record):
        if _PRIVACY_MODE:
            if isinstance(record.msg, str):
                # 파일 경로 패턴을 찾아 마스킹
                record.msg = FILE_PATH_PATTERN.sub(r'[HIDDEN_PATH]', record.msg)
                # args가 있는 경우도 처리 (복잡성을 피하기 위해 msg만 우선 처리하거나, 필요시 args도 처리)
                # 대부분의 로깅이 f-string을 사용하므로 msg만 처리해도 충분한 경우가 많음
        return True

def set_log_privacy_mode(enabled: bool):
    """
    로그 프라이버시 모드를 설정합니다.
    True일 경우 로그에 기록되는 파일 경로가 마스킹됩니다.
    """
    global _PRIVACY_MODE
    _PRIVACY_MODE = enabled

