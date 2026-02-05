# ⚡️ Synapse Protocol: AI Behavior & Operating Procedures

이 파일은 안티그래비티(OpenClaw) 및 기타 AI 에이전트가 이 프로젝트를 다룰 때 반드시 따라야 할 **통합 행동 강령**입니다.

## 🛑 PRIME DIRECTIVES (NON-NEGOTIABLE)

### 1. 🔍 Search Before You Strike (Context Acquisition)
**절대** 코드를 직접 확인하기 전에는 수정하거나 답변하지 않는다.
- **Action**: `synapse search <query>`를 실행하여 관련 파일과 정의를 먼저 찾는다.
- **Why**: 파일 경로와 내용을 추측하는 것은 환각(Hallucination)과 빌드 오류의 원인이 된다.

### 2. 🕸️ Check the Graph (Impact Analysis)
공유 컴포넌트를 수정하거나 리팩토링하기 전:
- **Action**: `synapse graph <file_path>`를 실행하여 의존성(Dependencies)과 피의존성(Dependents)을 확인한다.
- **Why**: 함수 하나를 고쳤을 때 어디가 깨질지 완벽하게 이해해야 한다.

### 3. 🧠 Deep Think on Failure (Self-Correction)
에러가 발생하거나 빌드가 실패했을 때:
- **Action**: 무작정 고치지 말고 `synapse ask "<error message>" --think`를 실행한다.
- **Why**: 복잡한 버그는 단순히 다시 시도하는 것이 아니라, 논리적인 추론(CoT)이 필요하다.

---

## 🌐 1. 언어 및 소통 (Language & Communication)
- **모든 대화 및 문서**: 사용자에게 제공하는 모든 대화, 작업 계획서, 구현 계획 등은 반드시 **한국어**로 작성한다.
- **주석**: 코드 내 모든 주석은 **한국어**로 작성하며, 누구나 쉽게 이해할 수 있도록 명확하게 설명한다.
- **결과 중심 소통**: 사용자는 최종 결과물만을 원한다. 불필요한 추론 과정, 생각의 흐름 등은 출력하지 않아 토큰을 절약한다.
- **톤앤매너**: 실리콘밸리 10x 엔지니어처럼 전문적이고 명확하게 소통하되, 친절함을 유지한다.

## 🔍 2. 작업 전 필수 절차 (Pre-Work Protocol)
작업을 시작하기 전, 반드시 다음 절차를 수행하여 맥락을 파악한다.
1.  **인덱스 갱신**: `synapse analyze .`을 실행하여 최신 프로젝트 지도를 그린다.
    - 증분 업데이트가 기본이므로 변경된 파일만 빠르게 처리됨
2.  **구조 파악**: `.synapse/INTELLIGENCE.md` 파일을 읽고 전체 아키텍처를 숙지한다.

## 👁️ 3. 실시간 감시 (Real-time Watcher)
**장시간 개발 세션**에서는 File Watcher를 활용하여 항상 최신 인덱스를 유지한다.
1.  **상태 확인**: `synapse watch status`로 Watcher 실행 여부 확인
2.  **필요 시 시작**: 
    - 포그라운드: `synapse watch start` (Ctrl+C로 종료)
    - 백그라운드: `synapse watch start --daemon` (별도 프로세스)
3.  **중지**: `synapse watch stop`

> Watcher가 실행 중이면 파일 변경 시 자동으로 증분 인덱싱이 수행되므로
> AI가 항상 최신 코드베이스에 접근할 수 있다.

## 💾 4. 작업 후 마무리 (Post-Work Protocol)
코드 수정이나 기능 추가 후에는 반드시 다음을 수행한다.
1.  **인덱스 갱신**: Watcher가 실행 중이 아니면 `synapse analyze .`를 실행한다.
2.  **정리정돈**: 불필요한 임시 파일이나 디버그 로그는 즉시 삭제한다.

## 🛡️ 5. 안전 및 보안 (Safety & Security)
- **중요 파일 보호**: `.env`, 보안 키, 설정 파일은 절대 삭제하거나 외부로 노출하지 않는다.
- **파괴적 명령어**: `rm -rf` 등 위험한 명령어 실행 전에는 반드시 사용자에게 확인을 받는다.

## 🔧 6. 에러 대응 프로토콜 (Error Handling Protocol)
에러가 발생했을 때 AI는 다음 순서로 자동 대응한다:

### Step 1: 상세 로그 수집
```bash
synapse analyze . --verbose
```
- `--verbose` 옵션으로 상세 디버그 정보 확인
- 에러 발생 위치와 스택 트레이스 분석

### Step 2: 로그 파일 확인
```bash
# 로그 파일 위치: .synapse/synapse_YYYYMMDD.log
cat .synapse/synapse_*.log | tail -50
```
- 최근 50줄의 로그를 분석하여 에러 패턴 파악

### Step 3: 에러 메시지 분석
```bash
synapse ask "<에러 메시지>" --think
```
- Chain-of-Thought 추론으로 근본 원인 분석
- 단순 재시도 금지, 논리적 해결책 도출

### Step 4: 에러 유형별 대응
| 에러 타입 | 대응 |
|-----------|------|
| `ParserError` | 파일 문법 확인, tree-sitter 파서 상태 점검 |
| `IndexingError` | `.synapse/db` 삭제 후 `--full` 재인덱싱 |
| `GraphError` | `dependency_graph.gml` 무결성 확인 |
| `SearchError` | 쿼리 수정 또는 인덱스 재생성 |
| `WatcherError` | `synapse watch stop` 후 재시작 |

## 🛠️ Tool Quick Reference

| Goal | Command |
| :--- | :--- |
| **Start/Re-index** | `synapse analyze` |
| **Full Re-index** | `synapse analyze --full` |
| **Verbose Debug** | `synapse analyze --verbose` |
| **Find Code** | `synapse search "<query>"` |
| **Check Impact** | `synapse graph <file_path>` |
| **Debug/Reason** | `synapse ask "<question>" --think` |
| **Start Watcher** | `synapse watch start` (or `--daemon`) |
| **Watcher Status** | `synapse watch status` |
| **Stop Watcher** | `synapse watch stop` |

---
**이 프로젝트에서 활동하는 모든 AI는 위 프로토콜을 엄격히 준수할 것을 약속한다.**
*Powered by Synapse & Jiyu*

