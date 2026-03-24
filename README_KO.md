<div align="center">

# Soy Lunita

### 로컬 우선 계층형 작업 관리자

단일 사용자용 오프라인 우선 작업 관리 애플리케이션으로, 무한 계층 트리 구조,\
전문 검색, 파일 첨부, 영구 실행 취소/다시 실행을 지원하며 모든 것이 로컬 머신에서 실행됩니다.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-FTS5%20%7C%20WAL-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0--dev-blue)](#)
[![Status](https://img.shields.io/badge/status-Alpha-orange)](#)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Testing: pytest](https://img.shields.io/badge/testing-pytest-0A9EDC.svg?logo=pytest&logoColor=white)](https://pytest.org/)

</div>

---

## 목차

- [개요](#개요)
- [기능](#기능)
- [아키텍처](#아키텍처)
- [요구사항](#요구사항)
- [설치](#설치)
- [빠른 시작](#빠른-시작)
- [사용법](#사용법)
- [API 레퍼런스](#api-레퍼런스)
- [개발](#개발)
- [설정](#설정)
- [보안](#보안)
- [기여하기](#기여하기)
- [라이선스](#라이선스)
- [감사의 글](#감사의-글)

---

## 개요

**Soy Lunita**는 클라우드 도구가 적합하지 않은 환경, 특히 오프라인 또는 에어갭 워크플로우를 위해 만들어진 개인용 로컬 우선 작업 관리자입니다.

로컬 머신에 완전히 상주하면서 깊은 작업 계층 구조를 지원하고, 첨부 파일을 처리하며, 외부 서비스에 의존하지 않는 작업 관리자가 필요해서 만들게 되었습니다.

모든 작업 데이터는 로컬 SQLite 데이터베이스에 저장됩니다. 계정도, 텔레메트리도, 일반적인 사용에 필요한 네트워크 의존성도 없습니다.

## 프로젝트 현황

이 저장소는 개인 프로젝트이자 참조 구현으로 공개되었습니다.

- 주된 목표: 제한된 환경에서의 개인 워크플로우 해결
- 현재 상태: 사용 가능하나 아직 발전 중
- 범위: 단일 사용자 로컬 애플리케이션이며, 호스팅 기반 다중 사용자 제품이 아님

완성도 높은 범용 작업 관리자를 찾고 있다면, 이 저장소는 아마 적합하지 않을 것입니다. 로컬 우선 참조 프로젝트나 에어갭 환경의 개인 작업 관리자에 가까운 것이 필요하다면, 유용할 수 있습니다.

### 누구를 위한 것인가?

| 사용 사례 | Soy Lunita를 선택하는 이유 |
|----------|--------------------------|
| **에어갭 환경** | 네트워크 의존성 제로; 완전한 오프라인 작동 |
| **프라이버시 중시 사용자** | 로컬 전용 저장소를 통한 완전한 데이터 주권 |
| **보안이 중요한 워크플로우** | 데이터 유출 경로 없음; 기밀 환경에 이상적 |
| **파워 유저** | 키보드 중심 설계, 무한 중첩, 마크다운 설명 |

이 애플리케이션은 커스텀 다크 UI, 마크다운 렌더링, 구문 강조, WebSocket을 통한 실시간 브라우저 탭 동기화를 포함합니다.

---

## 기능

### 작업 관리

- **무한 계층 트리** — 클로저 테이블 모델을 사용한 무제한 중첩 하위 작업
- **5가지 작업 상태** — 대기 중, 진행 중, 완료됨, 보류됨, 삭제됨 (소프트)
- **4단계 우선순위** — 긴급, 높음, 중간, 낮음 (미설정 포함)
- **마감일 및 반복** — ISO 8601 날짜와 RFC 5545 반복 규칙
- **일괄 작업** — 단일 동작으로 전체 하위 트리 완료/미완료 처리
- **소프트 및 하드 삭제** — 기본적으로 복구 가능한 소프트 삭제; 필요시 영구 하드 삭제
- **이동 및 재정렬** — 작업의 상위 변경과 모든 레벨에서 하위 항목 재정렬

### 검색 및 탐색

- **전문 검색** — 트리거로 동기화되는 인덱스를 갖춘 SQLite FTS5 기반
- **대시보드** — 집계된 작업 통계와 검색 분석
- **검색 제안** — 입력하는 동안 자동 완성 제안

### 파일 첨부

- **콘텐츠 주소 지정 스토리지** — SHA-256 해시 블롭과 자동 중복 제거
- **설정 가능한 용량 제한** — 인스턴스당 기본 500 MB; 조정 가능
- **보안 검증** — 파일명 살균, 경로 순회 방지, 선택적 실행 파일 차단

### 실행 취소 / 다시 실행

- **영구 이력** — SQLite에 저장되는 JSON-Patch 기반 작업 로그
- **충돌 안전** — PENDING/APPLIED 상태 추적을 통한 2단계 커밋
- **완전한 가역성** — 생성, 수정, 삭제, 이동, 일괄 작업에 대한 실행 취소/다시 실행

### 실시간 업데이트

- **WebSocket 동기화** — 여러 브라우저 탭 간 실시간 업데이트
- **연결 상태 확인** — 자동 재연결 기능을 갖춘 백그라운드 하트비트
- **상태 표시기** — UI에서 연결 상태 시각적으로 표시

### 사용자 인터페이스

- **오로라 다크 테마** — 애니메이션 시차 별 배경과 그라데이션 강조
- **마크다운 렌더링** — 작업 설명에서 Marked.js를 통한 전체 마크다운 지원
- **LaTeX 수식** — KaTeX를 통한 인라인 및 디스플레이 수식 표현
- **구문 강조** — Atom One Dark 테마의 Highlight.js를 사용한 코드 블록
- **키보드 중심** — 모든 일반 작업에 대한 포괄적인 단축키
- **토스트 알림** — 사용자 동작에 대한 비침습적 피드백
- **반응형 레이아웃** — 다양한 화면 크기에 적응

---

## 아키텍처

```
┌────────────────────────────────────────────────────────────────┐
│  프론트엔드 (SPA)                                               │
│  바닐라 JS (ES6+) · HTML5 · CSS3 (오로라 테마)                  │
│  Lucide 아이콘 · Marked.js · KaTeX · Highlight.js              │
└──────────────────────────┬─────────────────────────────────────┘
                           │  REST API + WebSocket
┌──────────────────────────▼─────────────────────────────────────┐
│  백엔드 — FastAPI + Uvicorn (ASGI)                              │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌───────────────┐  │
│  │   작업   │ │   검색   │ │   첨부파일  │ │ 실행취소/다시 │  │
│  └──────────┘ └──────────┘ └─────────────┘ └───────────────┘  │
│  ┌──────────┐ ┌───────────────────┐ ┌───────────────────────┐  │
│  │WebSocket │ │   데이터 관리     │ │    의존성 주입        │  │
│  └──────────┘ └───────────────────┘ └───────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────┘
                           │  aiosqlite (비동기)
┌──────────────────────────▼─────────────────────────────────────┐
│  SQLite 데이터베이스 (WAL 모드)                                  │
│  Task · TaskClosure · TaskFTS · Blob · Attachment · UndoLog    │
│  FTS5 트리거 · 외래 키 · 스키마 마이그레이션 (v3)               │
└────────────────────────────────────────────────────────────────┘
```

### 기술 스택

| 계층 | 기술 |
|------|------|
| **언어** | Python 3.10+ |
| **웹 프레임워크** | FastAPI 0.104+ |
| **ASGI 서버** | Uvicorn 0.24+ |
| **유효성 검사** | Pydantic v2 |
| **데이터베이스** | SQLite (aiosqlite 비동기) |
| **검색** | SQLite FTS5 (전문 검색) |
| **계층 구조** | 클로저 테이블 패턴 |
| **프론트엔드** | 바닐라 JavaScript (ES6+), HTML5, CSS3 |
| **렌더링** | Marked.js, KaTeX, Highlight.js |
| **아이콘** | Lucide |
| **폰트** | Bricolage Grotesque, Plus Jakarta Sans, IBM Plex Mono |

### 데이터베이스 스키마

데이터베이스는 무한 계층 구조를 위한 클로저 테이블 모델, 검색을 위한 FTS5, 첨부 파일을 위한 콘텐츠 주소 지정 블롭 스토리지를 사용합니다:

| 테이블 | 용도 |
|--------|------|
| `Task` | 핵심 작업 데이터 (제목, 설명, 상태, 우선순위, 날짜) |
| `TaskClosure` | 깊이와 정렬 순서를 포함한 조상-후손 쌍 |
| `TaskFTS` | 트리거를 통해 동기화되는 FTS5 가상 테이블 |
| `Blob` | SHA-256 키 기반 중복 제거된 파일 콘텐츠 메타데이터 |
| `Attachment` | 원본 파일명과 함께 블롭을 작업에 연결 |
| `UndoLog` | 실행 취소/다시 실행을 위한 JSON-Patch 작업 이력 |

스키마 버전 관리는 `SCHEMA_VERSION`을 통해 점진적 마이그레이션으로 관리됩니다.

---

## 요구사항

| 요구사항 | 최소 사양 |
|----------|----------|
| **운영체제** | Windows 10/11, macOS, Linux |
| **Python** | 3.10 이상 |
| **디스크** | ~100 MB (앱 + 의존성) |
| **RAM** | 256 MB (512 MB 권장) |

### 런타임 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| FastAPI | >= 0.104.0 | 비동기 웹 프레임워크 |
| Uvicorn | >= 0.24.0 | ASGI 서버 |
| Pydantic | >= 2.5.0 | 데이터 유효성 검사 및 직렬화 |
| aiosqlite | >= 0.19.0 | 비동기 SQLite 드라이버 |
| python-multipart | >= 0.0.6 | 멀티파트 폼 / 파일 업로드 처리 |
| python-dateutil | >= 2.8.0 | 유연한 날짜 파싱 |

---

## 설치

### 저장소 복제

```bash
git clone https://github.com/Soluna-Angelito/local-first-todo.git
cd local-first-todo
```

### Windows

포함된 설치 스크립트를 실행하여 가상 환경을 생성하고 모든 의존성을 설치합니다:

```
"0 setup_venv.bat"
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 오프라인 / 에어갭 설치

인터넷에 연결된 머신에서 패키지를 미리 다운로드합니다:

```bash
pip download -r requirements.txt -d ./offline_packages
```

전체 프로젝트 디렉터리를 대상 머신으로 전송한 후 실행합니다:

```
"0 setup_venv_offline.bat"
```

### 개발 환경 설치

```bash
pip install -r requirements-dev.txt
```

또는 `pyproject.toml` extras를 통해:

```bash
pip install -e ".[dev]"
```

---

## 빠른 시작

**Windows:**

```batch
"0 setup_venv.bat"
"1 run_server.bat"
```

**Linux / macOS:**

```bash
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
python -m local_first_todo.main
```

그런 다음 브라우저에서 **http://127.0.0.1:8765**를 엽니다.

---

## 사용법

### 서버 관리 (Windows)

| 스크립트 | 설명 |
|----------|------|
| `1 run_server.bat` | 콘솔 출력과 함께 서버 시작 |
| `1 run_server - without console.bat` | 최소화 상태로 서버 시작 |
| `1 run_server - without console.vbs` | 숨김 상태로 서버 시작 (백그라운드) |
| `2 stop_server.bat` | 실행 중인 서버 중지 |

### 키보드 단축키

언제든지 <kbd>?</kbd>를 눌러 단축키 모달을 확인할 수 있습니다.

#### 탐색

| 키 | 동작 |
|----|------|
| <kbd>/</kbd> | 검색에 포커스 |
| <kbd>↑</kbd> <kbd>↓</kbd> | 작업 목록 탐색 |
| <kbd>←</kbd> <kbd>→</kbd> | 노드 축소 / 확장 |
| <kbd>Enter</kbd> | 작업 상세 열기 |
| <kbd>Esc</kbd> | 닫기 / 취소 |

#### 동작

| 키 | 동작 |
|----|------|
| <kbd>N</kbd> | 새 작업 생성 |
| <kbd>+</kbd> | 선택한 작업에 하위 작업 추가 |
| <kbd>Space</kbd> | 완료 상태 토글 |
| <kbd>Delete</kbd> | 작업 삭제 |
| <kbd>E</kbd> | 모두 확장 |
| <kbd>C</kbd> | 모두 축소 |

#### 편집

| 키 | 동작 |
|----|------|
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | 실행 취소 |
| <kbd>Ctrl</kbd>+<kbd>Y</kbd> | 다시 실행 |

---

## API 레퍼런스

모든 엔드포인트는 `/api/v1/` 하위에 버전 관리됩니다. 대화형 API 문서는 다음에서 확인할 수 있습니다:

- **Swagger UI** — `http://127.0.0.1:8765/api/docs`
- **ReDoc** — `http://127.0.0.1:8765/api/redoc`

### 작업 — `/api/v1/tasks`

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| `GET` | `/` | 모든 작업 목록 조회 |
| `GET` | `/root` | 최상위 작업 목록 조회 |
| `GET` | `/tree` | 전체 작업 트리 (단일 최적화 요청) |
| `GET` | `/{id}` | ID로 작업 조회 |
| `GET` | `/uuid/{uuid}` | UUID로 작업 조회 |
| `GET` | `/status/{status}` | 상태별 작업 필터링 |
| `POST` | `/` | 새 작업 생성 |
| `PUT` | `/{id}` | 작업 수정 |
| `DELETE` | `/{id}` | 소프트 삭제 (또는 `?hard_delete=true`로 하드 삭제) |
| `POST` | `/{id}/restore` | 소프트 삭제된 작업 복원 |
| `GET` | `/{id}/children` | 직속 하위 작업 |
| `GET` | `/{id}/descendants` | 모든 하위 항목 |
| `GET` | `/{id}/ancestors` | 모든 상위 항목 |
| `PUT` | `/{id}/move` | 새 상위로 작업 이동 |
| `POST` | `/{parent_id}/reorder` | 하위 항목 재정렬 |
| `POST` | `/{id}/complete-tree` | 작업 및 모든 하위 항목 완료 |
| `POST` | `/bulk` | 일괄 작업 |

### 첨부 파일 — `/api/v1/attachments`

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| `POST` | `/upload/{task_id}` | 파일 첨부 업로드 |
| `GET` | `/download/{attachment_id}` | 파일 다운로드 |
| `GET` | `/task/{task_id}` | 작업의 첨부 파일 목록 조회 |
| `DELETE` | `/{attachment_id}` | 첨부 파일 삭제 |
| `GET` | `/stats` | 첨부 파일 스토리지 통계 |
| `GET` | `/quota` | 현재 용량 사용량 |

### 검색 — `/api/v1/search`

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| `POST` | `/` | 전문 검색 |
| `GET` | `/dashboard` | 대시보드 집계 |
| `GET` | `/suggestions` | 검색 자동 완성 |
| `GET` | `/stats` | 검색 통계 |

### 실행 취소 / 다시 실행 — `/api/v1/undo-redo`

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| `POST` | `/undo` | 마지막 작업 실행 취소 |
| `POST` | `/redo` | 마지막으로 취소된 작업 다시 실행 |
| `GET` | `/status` | 현재 실행 취소/다시 실행 스택 상태 |

### 데이터 관리 — `/api/v1/data`

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| `GET` | `/sync` | 지정된 리비전 이후의 델타 변경사항 조회 |
| `GET` | `/integrity` | 데이터베이스 무결성 검사 실행 |
| `POST` | `/export` | 데이터 아카이브 내보내기 *(계획 중)* |
| `POST` | `/import` | 데이터 아카이브 가져오기 *(계획 중)* |

### WebSocket — `/api/v1/ws`

다중 탭 동기화를 위한 실시간 이벤트 스트림입니다. 작업의 생성, 수정, 삭제, 이동, 재정렬 시 이벤트가 브로드캐스트됩니다.

### 기타 엔드포인트

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| `GET` | `/` | SPA 서빙 |
| `GET` | `/health` | 상태 확인 (버전 및 DB 상태 반환) |

---

## 개발

### 프로젝트 구조

```
local-first-todo/
├── src/local_first_todo/        # 애플리케이션 패키지
│   ├── main.py                  # FastAPI 앱 팩토리 및 진입점
│   ├── dependencies.py          # 의존성 주입 컨테이너
│   ├── api/                     # 라우트 핸들러
│   │   ├── tasks.py             # 작업 CRUD 및 계층 구조 엔드포인트
│   │   ├── attachments.py       # 파일 첨부 엔드포인트
│   │   ├── search.py            # FTS5 검색 및 대시보드 엔드포인트
│   │   ├── undo_redo.py         # 실행 취소/다시 실행 엔드포인트
│   │   ├── data.py              # 내보내기, 가져오기, 동기화, 무결성
│   │   └── websocket.py         # WebSocket 핸들러 및 상태 확인
│   ├── database/                # 데이터 계층
│   │   ├── manager.py           # 연결 풀 및 초기화
│   │   ├── schema.py            # DDL, 마이그레이션, 프라그마, FTS 트리거
│   │   ├── models.py            # 데이터클래스 모델 및 열거형
│   │   └── crud.py              # 리포지토리 패턴 CRUD 작업
│   └── services/                # 비즈니스 로직
│       ├── attachment_service.py # CAS 스토리지, 중복 제거, 보안, 용량 제한
│       ├── search_service.py    # FTS5 쿼리 빌딩 및 대시보드
│       └── undo_redo_service.py # JSON-Patch 기반 실행 취소/다시 실행 엔진
├── static/                      # 프론트엔드 SPA 에셋
│   ├── index.html               # 싱글 페이지 애플리케이션 셸
│   ├── css/app.css              # 오로라 다크 테마 스타일
│   ├── js/app.js                # 클라이언트 사이드 애플리케이션 로직
│   ├── js/vendor/               # 벤더 라이브러리 (오프라인 대응)
│   └── fonts/                   # 자체 호스팅 웹 폰트
├── tests/                       # 테스트 스위트
│   ├── conftest.py              # 픽스처 및 커스텀 테스트 리포팅
│   └── test_comprehensive.py    # 통합 테스트 스위트
├── scripts/                     # 유틸리티 스크립트
│   ├── clean_db.py              # 데이터베이스 정리 유틸리티
│   ├── run_all_tests.py         # 테스트 러너 헬퍼
│   └── run_comprehensive_tests.py
├── pyproject.toml               # 패키지 메타데이터, 도구 설정
├── requirements.txt             # 런타임 의존성
├── requirements-dev.txt         # 개발 의존성
├── noxfile.py                   # Nox 자동화 세션
├── LICENSE                      # MIT 라이선스
└── *.bat / *.vbs                # Windows 편의 스크립트
```

### 테스트 실행

```bash
# 가상 환경 활성화
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate.bat       # Windows

# 전체 테스트 스위트 실행
python -m pytest

# 커버리지 리포트와 함께 실행
python -m pytest --cov=local_first_todo --cov-report=html

# 느린 테스트 건너뛰기
python -m pytest -m "not slow"

# 성능 테스트만
python -m pytest -m perf
```

#### Nox 세션

```bash
nox -s lint         # Ruff + mypy
nox -s test         # 커버리지 포함 전체 스위트 (85% 임계값)
nox -s test_fast    # 빠른 테스트만 (slow/perf/fuzz/browser 제외)
nox -s test_perf    # 성능 벤치마크
nox -s safety       # 의존성 취약점 감사
nox -s clean        # 빌드 아티팩트 및 캐시 제거
```

#### Windows 배치 스크립트

| 스크립트 | 설명 |
|----------|------|
| `3 run_tests.bat` | pytest 실행 |
| `3 run_phase_tests.bat` | 페이즈 통합 테스트 실행 |
| `6 run_comprehensive_tests.bat` | 전체 종합 테스트 스위트 |
| `6a run_fast_tests.bat` | 빠른 테스트만 |
| `6b run_single_test.bat` | 이름으로 단일 테스트 실행 |
| `6c run_tests_with_coverage.bat` | HTML 커버리지 리포트와 함께 테스트 |

### 코드 품질

| 도구 | 용도 | 설정 |
|------|------|------|
| [Ruff](https://docs.astral.sh/ruff/) | 린팅 및 포매팅 | `pyproject.toml` — `[tool.ruff]` |
| [mypy](https://mypy-lang.org/) | 정적 타입 검사 (strict 모드) | `pyproject.toml` — `[tool.mypy]` |
| [pytest](https://pytest.org/) | 테스팅 프레임워크 (async 모드) | `pyproject.toml` — `[tool.pytest]` |
| [Coverage.py](https://coverage.readthedocs.io/) | 코드 커버리지 (85% 임계값) | `pyproject.toml` — `[tool.coverage]` |
| [Nox](https://nox.thea.codes/) | 세션 자동화 | `noxfile.py` |

적용되는 Ruff 규칙: `E`, `W`, `F`, `I`, `B`, `C4`, `UP`, `SIM` — pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade, simplify를 포괄합니다.

---

## 설정

### 서버 기본값

| 매개변수 | 기본값 | 설명 |
|----------|--------|------|
| Host | `0.0.0.0` | 리슨 주소 |
| Port | `8765` | 리슨 포트 |
| Database | `./app.db` | SQLite 데이터베이스 파일 (CWD 상대 경로) |
| Attachments | `./attachments/` | 블롭 스토리지 디렉터리 |

### 첨부 파일 보안

기본값은 로컬 우선 / 에어갭 환경에 최적화되어 있습니다:

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `DEFAULT_MAX_ATTACHMENT_SIZE` | 500 MB | 단일 파일 최대 크기 |
| `ALLOW_ALL_EXTENSIONS` | `True` | 모든 파일 확장자 허용 |
| `BLOCK_EXECUTABLES` | `False` | `.exe`, `.bat`, `.vbs` 등 차단 |
| `SKIP_SIGNATURE_VALIDATION` | `True` | 매직 바이트 검증 건너뛰기 |

이 값들은 `src/local_first_todo/services/attachment_service.py`에서 조정할 수 있습니다.

### 데이터베이스 프라그마

성능과 안전성을 위해 모든 연결에 적용됩니다:

```
PRAGMA foreign_keys = ON
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA temp_store = MEMORY
PRAGMA cache_size = -64000        -- 64 MB
```

---

## 보안

### 설계 원칙

1. **설계상 로컬 전용** — 외부 네트워크 호출 없음; CORS는 `localhost`로 제한
2. **데이터 주권** — 모든 데이터는 사용자가 관리하는 단일 SQLite 파일에 저장
3. **콘텐츠 주소 지정 스토리지** — 첨부 파일을 SHA-256 해시로 저장
4. **충돌 안전성** — WAL 저널링, 2단계 실행 취소 로그, 외래 키 제약 조건

### 파일 업로드 보안 강화

- 경로 순회 방지 (`../` 시퀀스 차단)
- Windows 예약 이름 차단 (`CON`, `PRN`, `NUL`, `COM1`–`9`, `LPT1`–`9`)
- 파일명 내 위험 문자 살균
- 설정 가능한 실행 파일 차단 및 확장자 화이트리스트
- 선택적 MIME 타입 / 매직 바이트 서명 검증

### 데이터베이스 보안

- 연결 수준에서 외래 키 제약 조건 적용
- 전체 매개변수화된 쿼리 (SQL 인젝션 방지)
- `CHECK` 제약 조건을 통한 ISO 8601 UTC 타임스탬프 검증
- `revision` 컬럼을 통한 낙관적 동시성 제어

---

## 기여하기

기여를 환영합니다. 다음 워크플로우를 따라주세요:

1. 저장소를 **포크**합니다
2. 기능 브랜치를 **생성**합니다 — `git checkout -b feature/your-feature`
3. 타입 힌트와 테스트를 포함하여 변경사항을 **구현**합니다
4. **검증**합니다 — `python -m pytest && ruff check . --fix`
5. **커밋**합니다 — `git commit -m "Add your feature"`
6. **푸시**합니다 — `git push origin feature/your-feature`
7. Pull Request를 **엽니다**

### 가이드라인

- [PEP 8](https://peps.python.org/pep-0008/) 규약을 따릅니다 (Ruff에 의해 적용됨)
- 모든 공개 함수에 타입 어노테이션을 추가합니다
- 새 기능 및 버그 수정에 대한 테스트를 작성합니다
- 커밋을 원자적이고 설명적으로 유지합니다
- 사용자 대면 변경사항에 대해 문서를 업데이트합니다

---

## 라이선스

이 프로젝트는 **MIT 라이선스**에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 감사의 글

- [FastAPI](https://fastapi.tiangolo.com/) — 고성능 비동기 웹 프레임워크
- [SQLite](https://www.sqlite.org/) — 세계에서 가장 널리 배포된 데이터베이스 엔진
- [Lucide](https://lucide.dev/) — 아름다운 오픈소스 아이콘 라이브러리
- [Marked.js](https://marked.js.org/) — 마크다운 파서 및 렌더러
- [KaTeX](https://katex.org/) — 빠른 LaTeX 수식 렌더링
- [Highlight.js](https://highlightjs.org/) — 코드 블록 구문 강조
- [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque), [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans), [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) — 타이포그래피

---

<div align="center">

프라이버시, 성능, 그리고 아름다운 소프트웨어를 위해 정성을 담아 만들었습니다.

</div>
