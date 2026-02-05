# -*- mode: python ; coding: utf-8 -*-

"""
YDManager PyInstaller Spec File
--------------------------------
이 파일은 PyInstaller를 사용하여 프로젝트를 EXE로 빌드할 때 사용되는 설정 파일입니다.
사용법: pyinstaller YDManager.spec

[주요 설정]
1. Assets 포함: 'assets' 폴더를 실행 파일 내부에 포함시킵니다.
2. QtAwesome: 아이콘 폰트 파일 누락을 방지하기 위해 데이터를 수집합니다.
3. Hidden Imports: 런타임에 동적으로 로딩되는 모듈들을 명시합니다.
"""

from PyInstaller.utils.hooks import collect_all
import sys
import os

block_cipher = None

# 1. 의존성 라이브러리 데이터 자동 수집
# qtawesome 등 리소스가 필요한 라이브러리들을 수집합니다.
datas = []
binaries = []
hiddenimports = ['send2trash', 'BlurWindow']

# qtawesome의 폰트 데이터 수집
tmp_ret = collect_all('qtawesome')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# 2. 로컬 Assets 폴더 포함
# 문법: (로컬_소스_경로, EXE_내부_목적지_경로)
datas += [
    ('assets', 'assets'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YDManager_v8.2',  # 생성될 파일 이름
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # GUI 프로그램이므로 콘솔 숨김 (디버깅 시 True로 변경)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico', # 윈도우 EXE 아이콘 (assets/icon.ico 필요)
)
