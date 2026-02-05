# 🚀 YDManager 빌드 가이드

이 문서는 YDManager 프로젝트를 Windows 실행 파일(.exe)로 배포하기 위한 절차를 설명합니다.

## 1. 사전 준비 (Prerequisites)

### 1.1 Python 환경 설정
Python 3.10 이상이 설치되어 있는지 확인하십시오.

### 1.2 의존성 라이브러리 설치
프로젝트 루트 폴더에서 다음 명령어를 실행하여 필수 라이브러리를 설치합니다.
```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 1.3 아이콘 파일 확인
`assets/icon.ico` 파일이 존재하는지 확인하십시오. 이 파일은 실행 파일의 아이콘으로 사용됩니다.

## 2. 빌드 실행 (Building)

프로젝트 루트 폴더에서 미리 작성된 Spec 파일을 사용하여 빌드를 시작합니다.

```bash
pyinstaller YDManager.spec
```

- **Spec 파일이란?**: 빌드 옵션(포함할 파일, 아이콘, 콘솔 표시 여부 등)을 정의한 설정 파일입니다.
- 이 명령어를 실행하면 `dist/YDManager_v8.2.exe` 파일이 생성됩니다.

## 3. 문제 해결 (Troubleshooting)

### 3.1 폰트가 깨지거나 아이콘이 안 보일 때
- `assets` 폴더가 실행 파일과 같은 위치(또는 임시 폴더)에 제대로 포함되었는지 Spec 파일의 `datas` 항목을 확인하십시오.
- `qtawesome` 라이브러리의 폰트 파일이 누락된 경우입니다. Spec 파일의 `collect_all('qtawesome')` 부분이 제대로 동작하는지 확인하십시오.

### 3.2 "Failed to execute script main" 오류
- 콘솔에서 에러 로그를 확인하기 위해 `YDManager.spec` 파일의 `console=False`를 `console=True`로 변경한 후 다시 빌드하여 실행해 봅니다.
- `main.py`에서 발생하는 Import Error나 경로 문제를 확인하십시오.

## 4. 배포 (Distribution)
`dist` 폴더 안에 생성된 `YDManager_v8.2.exe` 파일 하나만 배포하면 됩니다. 
(단, 내부적으로 임시 폴더에 리소스를 풀어서 사용하는 방식입니다.)
