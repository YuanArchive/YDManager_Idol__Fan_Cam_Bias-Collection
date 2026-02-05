import os
import urllib.request
import zipfile
import shutil
import hashlib

from PyQt6.QtGui import QFontDatabase, QFont

# =============================================================================
# 폰트 설정 (여기에서 원하는 폰트의 주석을 풀어서 선택하세요)
# =============================================================================
# SELECTED_FONT = "Spoqa Han Sans Neo"
# SELECTED_FONT = "Wanted Sans"
# SELECTED_FONT = "IBM Plex Sans KR"
SELECTED_FONT = "Pretendard" 

# 폰트별 설정 데이터
FONT_CONFIGS = {
    "Pretendard": {  # Local Source
        "type": "local",
        "source_dir": os.path.join(os.getcwd(), "assets", "fonts"),
        "files": ["Pretendard-Medium.ttf", "Pretendard-Bold.ttf"],
        "license_path": os.path.join(os.getcwd(), "assets", "fonts", "LICENSE_Pretendard.txt"), # [라이센스] 파일 경로 추가
        "family": "Pretendard"
    }
}

def get_current_font_family():
    """현재 선택된 폰트 패밀리 이름을 반환합니다."""
    return FONT_CONFIGS[SELECTED_FONT]["family"]

import sys # sys 모듈 확인

# ...

def resource_path(relative_path):
    """ 
    PyInstaller 등으로 빌드된 실행 파일 내부의 리소스 경로를 반환합니다. 
    개발 환경에서는 현재 경로를 반환합니다.
    """
    try:
        # PyInstaller는 임시 폴더에 압축을 풀고 _MEIPASS에 경로를 저장합니다.
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def verify_file_hash(file_path, expected_hash):
    """
    파일의 SHA256 해시값을 검증합니다.
    - expected_hash: 예상되는 SHA256 해시 문자열 (소문자)
    - Return: 일치하면 True, 불일치하면 False
    """
    if not expected_hash:
        print("[FontLoader] 경고: 검증할 해시값이 설정되지 않았습니다. (보안 취약)")
        return True # 하위 호환성을 위해 True 반환하지만 경고 출력

    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        calculated_hash = sha256_hash.hexdigest()
        if calculated_hash.lower() == expected_hash.lower():
            return True
        else:
            print(f"[FontLoader] 해시 불일치!\n  기대값: {expected_hash}\n  실제값: {calculated_hash}")
            return False
    except Exception as e:
        print(f"[FontLoader] 해시 검증 중 오류: {e}")
        return False


def load_fonts():
    """
    선택된 폰트(SELECTED_FONT)를 다운로드 및 로드합니다.
    우선 번들링(EXE 내부)된 폰트가 있는지 확인하고, 없으면 로컬/다운로드를 시도합니다.
    """
    config = FONT_CONFIGS[SELECTED_FONT]
    
    # 1. 번들링된 폰트 확인 (PyInstaller Resource)
    # 빌드할 때 fonts 폴더를 포함시켰다면 여기에서 발견됩니다.
    is_bundled = False
    bundled_cnt = 0
    
    # 로드 대상 파일 목록
    if config["type"] == "zip":
        load_files = [target[1] for target in config["targets"]]
    else:
        load_files = config["files"]

    print(f"[FontLoader] 선택된 폰트: {SELECTED_FONT}")

    # 번들된 경로 체크
    for filename in load_files:
        bundled_path = resource_path(os.path.join("fonts", filename))
        if os.path.exists(bundled_path) and hasattr(sys, '_MEIPASS'):
            # EXE 실행 환경이고 파일이 내부에 존재함
            font_id = QFontDatabase.addApplicationFont(bundled_path)
            if font_id != -1:
                bundled_cnt += 1
    
    if bundled_cnt > 0:
        print(f"[FontLoader] 내장(Bundled) 폰트 로드 완료 ({bundled_cnt}개)")
        return True

    # 2. 번들된게 없으면 기존 로직(다운로드/로컬복사) 수행
    # [수정] Program Files 권한 문제 방지: AppData에 폰트 저장
    app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    font_dir = os.path.join(app_data, 'YDManager', 'fonts')
    if not os.path.exists(font_dir):
        os.makedirs(font_dir)
    
    # ... (다운로드 및 추출 로직)
    if config["type"] == "zip":
        _process_zip_font(config, font_dir)
    elif config["type"] == "raw":
        _process_raw_font(config, font_dir)
    elif config["type"] == "local":
        _process_local_font(config, font_dir)


    # 2. 로드
    loaded_cnt = 0
    
    # 로드 대상 파일 목록 결정
    if config["type"] == "zip":
        load_files = [target[1] for target in config["targets"]]
    else:
        load_files = config["files"]
        
    for filename in load_files:
        local_path = os.path.join(font_dir, filename)
        if os.path.exists(local_path):
            try:
                font_id = QFontDatabase.addApplicationFont(local_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    print(f"[FontLoader] 로드 성공: {families}")
                    loaded_cnt += 1
                else:
                    print(f"[FontLoader] 로드 실패 (ID -1): {local_path}")
            except Exception as e:
                print(f"[FontLoader] 로드 중 오류: {e}")
        else:
            print(f"[FontLoader] 파일 없음: {filename}")

    return loaded_cnt > 0

def _process_local_font(config, font_dir):
    """지정된 로컬 폴더에서 폰트 파일을 복사해옵니다."""
    src_dir = config["source_dir"]
    if not os.path.exists(src_dir):
        print(f"[FontLoader] 오류: 로컬 소스 폴더가 없습니다: {src_dir}")
        return

    # 1. 폰트 파일 복사
    for filename in config["files"]:
        src_path = os.path.join(src_dir, filename)
        dst_path = os.path.join(font_dir, filename)
        
        # 파일이 없으면 복사
        if not os.path.exists(dst_path):
            try:
                print(f"[FontLoader] 로컬 복사: {filename}")
                shutil.copy2(src_path, dst_path)
            except Exception as e:
                print(f"[FontLoader] 복사 실패 ({filename}): {e}")

    # 2. 라이센스 파일 복사 (중요)
    if "license_path" in config:
        lic_src = config["license_path"]
        lic_dst = os.path.join(font_dir, "LICENSE_Pretendard.txt")
        if os.path.exists(lic_src) and not os.path.exists(lic_dst):
             try:
                print(f"[FontLoader] 라이센스 복사: LICENSE_Pretendard.txt")
                shutil.copy2(lic_src, lic_dst)
             except Exception as e:
                print(f"[FontLoader] 라이센스 복사 실패: {e}")

def _process_zip_font(config, font_dir):
    zip_path = os.path.join(font_dir, config["zip_name"])
    
    # 필요한 파일이 하나라도 없으면 다운로드 진행
    need_download = False
    for _, local_name in config["targets"]:
        if not os.path.exists(os.path.join(font_dir, local_name)):
            need_download = True
            break
            
    if need_download:
        try:
            print(f"[FontLoader] 다운로드 시작: {config['url']}")
            req = urllib.request.Request(
                config['url'], 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            print("[FontLoader] 다운로드 완료.")

            # 해시 검증
            if "sha256" in config:
                if not verify_file_hash(zip_path, config["sha256"]):
                    print("[FontLoader] 보안 오류: 다운로드된 파일의 해시가 일치하지 않습니다. 파일을 삭제합니다.")
                    os.remove(zip_path)
                    return
            else:
                print("[FontLoader] 경고: 폰트 설정에 'sha256' 해시값이 없습니다. 무결성을 보장할 수 없습니다.")

            
            print("[FontLoader] 압축 해제 중...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for zip_path_in, local_name in config["targets"]:
                    # Zip 내 경로가 정확한지 확인 (유연하게 찾기)
                    # 일부 Zip은 폴더 구조가 다를 수 있음
                    found = False
                    
                    # 1. 정확한 경로 시도
                    if zip_path_in in zip_ref.namelist():
                        src = zip_path_in
                        found = True
                    else:
                        # 2. 파일명만으로 검색 (느슨한 매칭)
                        target_filename = os.path.basename(zip_path_in)
                        for name in zip_ref.namelist():
                            if name.endswith(target_filename):
                                src = name
                                found = True
                                break
                    
                    if found:
                        target_path = os.path.join(font_dir, local_name)
                        with zip_ref.open(src) as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        print(f"  - 추출: {local_name}")
                    else:
                        print(f"  [경고] Zip 내부에서 파일 찾지 못함: {zip_path_in}")

            print("[FontLoader] 작업 완료.")
            # os.remove(zip_path) # 캐싱을 위해 삭제 안 함 (선택)
            
        except Exception as e:
            print(f"[FontLoader] 오류 발생: {e}")

def _process_raw_font(config, font_dir):
    base_url = config["base_url"]
    for filename in config["files"]:
        url = f"{base_url}/{filename}"
        file_path = os.path.join(font_dir, filename)
        
        if not os.path.exists(file_path):
            try:
                print(f"[FontLoader] 다운로드: {filename}")
                urllib.request.urlretrieve(url, file_path)
                
                # 해시 검증
                if "files_sha256" in config and filename in config["files_sha256"]:
                    if not verify_file_hash(file_path, config["files_sha256"][filename]):
                        print(f"[FontLoader] 해시 불일치로 파일 삭제: {filename}")
                        os.remove(file_path)
            except Exception as e:
                print(f"[FontLoader] 실패 ({filename}): {e}")
