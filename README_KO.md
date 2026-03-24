# Local-First To-Do (Soy Lunita)

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0--dev-blue" alt="버전">
  <img src="https://img.shields.io/badge/python-3.10%2B-brightgreen" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT 라이선스">
  <img src="https://img.shields.io/badge/status-Alpha-orange" alt="알파 상태">
</p>

<p align="center">
  <strong>🌙 무한 계층 트리 구조를 지원하는 아름다운 로컬 우선 작업 관리 애플리케이션</strong>
</p>

<p align="center">
  에어갭 환경 및 데이터 주권을 중시하는 사용자를 위해 설계되었습니다.
</p>

---

## 목차

- [개요](#개요)
- [기능](#기능)
- [스크린샷](#스크린샷)
- [시스템 요구사항](#시스템-요구사항)
- [설치](#설치)
- [빠른 시작](#빠른-시작)
- [사용법](#사용법)
  - [서버 실행](#서버-실행)
  - [애플리케이션 접속](#애플리케이션-접속)
  - [키보드 단축키](#키보드-단축키)
- [아키텍처](#아키텍처)
  - [기술 스택](#기술-스택)
  - [데이터베이스 스키마](#데이터베이스-스키마)
  - [API 엔드포인트](#api-엔드포인트)
- [개발](#개발)
  - [프로젝트 구조](#프로젝트-구조)
  - [테스트 실행](#테스트-실행)
  - [코드 품질](#코드-품질)
- [설정](#설정)
- [보안](#보안)
- [기여하기](#기여하기)
- [라이선스](#라이선스)
- [감사의 글](#감사의-글)

---

## 개요

**Local-First To-Do (Soy Lunita)**는 완전히 로컬 머신에서 실행되는 단일 사용자용 로컬 우선 작업 관리 애플리케이션입니다. 클라우드 기반 작업 관리자와 달리, 사용자의 데이터는 절대 컴퓨터 외부로 나가지 않으므로 다음과 같은 환경에 적합합니다:

- **에어갭 환경**: 인터넷 연결 없이도 완벽하게 오프라인으로 작동
- **프라이버시 중시 사용자**: 외부 의존성 없이 완전한 데이터 주권 보장
- **보안이 중요한 워크플로우**: 기밀 또는 민감한 작업 관리에 이상적
- **파워 유저**: 풍부한 키보드 단축키와 무한 계층 구조 작업 지원

이 애플리케이션은 시차 효과가 있는 별 배경과 함께 오로라에서 영감을 받은 멋진 다크 UI를 특징으로 하며, 기능성과 미학을 모두 제공합니다.

---

## 기능

### 핵심 기능

- **🌳 무한 계층 작업 트리**
  - 무제한 중첩 하위 작업 생성
  - 드래그 앤 드롭 재정렬 (추후 지원 예정)
  - 전체 브랜치 확장/축소
  - 상위 작업 간 작업 이동

- **🔍 전문 검색**
  - SQLite FTS5 기반
  - 작업 제목 및 설명 전체 검색
  - 즉각적인 검색 결과

- **📎 파일 첨부**
  - 모든 파일을 작업에 첨부 가능
  - SHA-256 콘텐츠 주소 지정 스토리지
  - 자동 중복 제거 (동일 파일 = 단일 저장)
  - 설정 가능한 파일 크기 제한 (기본값: 500MB)

- **↩️ 실행 취소/다시 실행**
  - 영구 실행 취소/다시 실행 이력
  - 충돌 방지 작업 추적
  - JSON-Patch 기반 작업 로깅

- **⚡ 실시간 업데이트**
  - WebSocket 기반 실시간 동기화
  - 탭 간 즉각적인 UI 업데이트
  - 연결 상태 표시기

### 작업 관리

- **작업 상태**: 대기 중, 진행 중, 완료됨, 보류됨, 삭제됨
- **우선순위 레벨**: 긴급 (1), 높음 (2), 중간 (3), 낮음 (4), 없음
- **마감일**: 캘린더 뷰가 포함된 사용자 정의 날짜 선택기
- **소프트 삭제**: 복구 가능한 작업 삭제
- **일괄 작업**: 전체 작업 트리 완료/미완료 처리

### 사용자 인터페이스

- **🌌 오로라 영감 디자인**: 그라데이션 강조가 있는 아름다운 다크 테마
- **✨ 시차 별 배경**: 애니메이션 별 필드 효과
- **📝 마크다운 지원**: 설명에서 전체 마크다운 렌더링
- **⌨️ 키보드 우선**: 포괄적인 키보드 단축키
- **🔔 토스트 알림**: 방해하지 않는 피드백 메시지
- **📱 반응형 디자인**: 다양한 화면 크기에서 작동

---

## 스크린샷

*준비 중*

---

## 시스템 요구사항

### 시스템 요구사항

- **운영 체제**: Windows 10/11, macOS, Linux
- **Python**: 3.10 이상
- **디스크 공간**: 약 100MB (애플리케이션 + 의존성)
- **RAM**: 최소 256MB, 권장 512MB

### 의존성

모든 의존성은 설치 과정에서 자동으로 설치됩니다:

| 패키지 | 버전 | 용도 |
|--------|------|------|
| FastAPI | ≥0.104.0 | 웹 프레임워크 |
| Uvicorn | ≥0.24.0 | ASGI 서버 |
| Pydantic | ≥2.5.0 | 데이터 유효성 검사 |
| aiosqlite | ≥0.19.0 | 비동기 SQLite |
| python-multipart | ≥0.0.6 | 파일 업로드 |
| python-dateutil | ≥2.8.0 | 날짜 파싱 |

---

## 설치

### Windows (권장)

1. **저장소 복제 또는 다운로드**
   ```
   git clone https://github.com/example/local-first-todo.git
   cd local-first-todo
   ```

2. **설치 스크립트 실행**
   ```
   0 setup_venv.bat
   ```
   
   이 스크립트는 다음을 수행합니다:
   - Python 가상 환경 생성 (`.venv`)
   - pip를 최신 버전으로 업그레이드
   - 필요한 모든 의존성 설치

### Linux/macOS

1. **저장소 복제**
   ```bash
   git clone https://github.com/example/local-first-todo.git
   cd local-first-todo
   ```

2. **가상 환경 생성 및 의존성 설치**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### 오프라인 설치

에어갭 환경의 경우, 오프라인 설치를 사용하세요:

1. 인터넷에 연결된 머신에서 의존성을 다운로드합니다:
   ```bash
   pip download -r requirements.txt -d ./offline_packages
   ```

2. 전체 프로젝트 폴더(`offline_packages` 포함)를 에어갭 머신으로 복사합니다

3. 오프라인 설치 스크립트를 실행합니다:
   ```
   0 setup_venv_offline.bat
   ```

---

## 빠른 시작

### Windows

```batch
:: 1. 설치 (최초 1회만)
"0 setup_venv.bat"

:: 2. 서버 시작
"1 run_server.bat"

:: 3. 브라우저에서 열기
:: http://127.0.0.1:8765로 이동
```

### Linux/macOS

```bash
# 1. 가상 환경 활성화
source .venv/bin/activate

# 2. PYTHONPATH 설정
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

# 3. 서버 실행
python -m local_first_todo.main

# 4. 브라우저에서 열기: http://127.0.0.1:8765
```

---

## 사용법

### 서버 실행

| 스크립트 | 설명 |
|----------|------|
| `1 run_server.bat` | 콘솔 창과 함께 서버 시작 |
| `1 run_server - without console.bat` | 최소화 상태로 서버 시작 |
| `1 run_server - without console.vbs` | 완전히 숨겨진 상태로 서버 시작 |
| `2 stop_server.bat` | 실행 중인 서버 중지 |

서버는 기본적으로 `http://127.0.0.1:8765`에서 실행됩니다.

### 애플리케이션 접속

1. 위의 스크립트 중 하나를 사용하여 서버를 시작합니다
2. 웹 브라우저를 엽니다
3. `http://127.0.0.1:8765`로 이동합니다
4. 작업 관리를 시작하세요!

### 키보드 단축키

언제든지 `?`를 눌러 단축키 모달을 확인할 수 있습니다.

#### 탐색
| 단축키 | 동작 |
|--------|------|
| `/` | 검색에 포커스 |
| `↑` / `↓` | 작업 탐색 |
| `←` / `→` | 축소 / 확장 |
| `Enter` | 작업 상세 열기 |
| `Esc` | 닫기 / 취소 |

#### 동작
| 단축키 | 동작 |
|--------|------|
| `N` | 새 작업 |
| `+` | 선택된 작업에 하위 작업 추가 |
| `Space` | 완료 상태 토글 |
| `Delete` | 작업 삭제 |

#### 편집
| 단축키 | 동작 |
|--------|------|
| `Ctrl+Z` | 실행 취소 |
| `Ctrl+Y` | 다시 실행 |
| `E` | 모두 확장 |
| `C` | 모두 축소 |
| `?` | 도움말 표시 |

---

## 아키텍처

### 기술 스택

```
┌─────────────────────────────────────────────────────────────┐
│                      프론트엔드                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   HTML5     │  │   CSS3      │  │    JavaScript       │  │
│  │   (시맨틱)  │  │   (오로라   │  │    (바닐라 ES6+)    │  │
│  │             │  │    테마)    │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                              │
│  라이브러리: Lucide 아이콘, Marked.js (마크다운)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP REST + WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      백엔드                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    FastAPI                           │    │
│  │  ┌───────────┐ ┌───────────┐ ┌─────────────────┐   │    │
│  │  │   작업    │ │   검색    │ │     첨부파일    │   │    │
│  │  │   API     │ │   API     │ │       API       │   │    │
│  │  └───────────┘ └───────────┘ └─────────────────┘   │    │
│  │  ┌───────────┐ ┌───────────┐ ┌─────────────────┐   │    │
│  │  │실행취소/  │ │ WebSocket │ │  데이터 내보내기/│   │    │
│  │  │다시실행API│ │    API    │ │    가져오기     │   │    │
│  │  └───────────┘ └───────────┘ └─────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  서비스: UndoRedo, Search, Attachment                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ aiosqlite (비동기)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      데이터베이스                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    SQLite                            │    │
│  │  ┌───────────┐ ┌───────────┐ ┌─────────────────┐   │    │
│  │  │   Task    │ │  TaskFTS  │ │   TaskClosure   │   │    │
│  │  │  (메인)   │ │  (검색)   │ │    (계층구조)   │   │    │
│  │  └───────────┘ └───────────┘ └─────────────────┘   │    │
│  │  ┌───────────┐ ┌───────────┐ ┌─────────────────┐   │    │
│  │  │   Blob    │ │Attachment │ │    UndoLog      │   │    │
│  │  │  (파일)   │ │  (링크)   │ │    (이력)       │   │    │
│  │  └───────────┘ └───────────┘ └─────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  특징: WAL 모드, FTS5, 외래 키, 트리거                        │
└─────────────────────────────────────────────────────────────┘
```

### 데이터베이스 스키마

#### Task 테이블
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | 기본 키 |
| uuid | TEXT | 고유 식별자 |
| revision | INTEGER | 버전 번호 |
| title | TEXT | 작업 제목 |
| description | TEXT | 작업 설명 (마크다운) |
| status | TEXT | pending/in_progress/completed/deleted/deferred |
| priority | INTEGER | 1-5 (1=가장 높음) |
| next_due_utc | TEXT | 마감일 (ISO 8601) |
| recurrence_rrule | TEXT | 반복 규칙 (RFC 5545) |
| created_at | TEXT | 생성 타임스탬프 |
| updated_at | TEXT | 최종 수정 타임스탬프 |
| deleted_at | TEXT | 소프트 삭제 타임스탬프 |

#### TaskClosure 테이블 (계층구조)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| ancestor_id | INTEGER | 상위 작업 ID |
| descendant_id | INTEGER | 하위 작업 ID |
| depth | INTEGER | 계층 깊이 |
| sort_order | INTEGER | 표시 순서 |

### API 엔드포인트

#### 작업 (`/api/v1/tasks`)
| 메서드 | 엔드포인트 | 설명 |
|--------|------------|------|
| GET | `/` | 모든 작업 목록 |
| GET | `/root` | 최상위 작업 목록 |
| GET | `/{id}` | ID로 작업 조회 |
| GET | `/uuid/{uuid}` | UUID로 작업 조회 |
| GET | `/status/{status}` | 상태별 작업 조회 |
| POST | `/` | 새 작업 생성 |
| PUT | `/{id}` | 작업 수정 |
| DELETE | `/{id}` | 작업 삭제 |
| POST | `/{id}/restore` | 삭제된 작업 복원 |
| GET | `/{id}/children` | 하위 작업 조회 |
| GET | `/{id}/descendants` | 모든 하위 항목 조회 |
| GET | `/{id}/ancestors` | 모든 상위 항목 조회 |
| PUT | `/{id}/move` | 새 상위로 작업 이동 |
| POST | `/{parent_id}/reorder` | 하위 항목 재정렬 |
| POST | `/{id}/complete-tree` | 작업 및 하위 항목 완료 |
| POST | `/bulk` | 일괄 작업 |

#### 첨부파일 (`/api/v1/attachments`)
| 메서드 | 엔드포인트 | 설명 |
|--------|------------|------|
| GET | `/task/{task_id}` | 작업 첨부파일 조회 |
| POST | `/task/{task_id}` | 첨부파일 업로드 |
| GET | `/{id}/download` | 첨부파일 다운로드 |
| DELETE | `/{id}` | 첨부파일 삭제 |
| GET | `/stats` | 첨부파일 통계 조회 |

#### 검색 (`/api/v1/search`)
| 메서드 | 엔드포인트 | 설명 |
|--------|------------|------|
| POST | `/` | 작업 검색 |
| GET | `/dashboard` | 대시보드 데이터 조회 |
| GET | `/suggestions` | 검색 제안 조회 |
| GET | `/stats` | 검색 통계 조회 |

#### 실행 취소/다시 실행 (`/api/v1/undo`)
| 메서드 | 엔드포인트 | 설명 |
|--------|------------|------|
| POST | `/undo` | 마지막 작업 실행 취소 |
| POST | `/redo` | 마지막 취소된 작업 다시 실행 |
| GET | `/status` | 실행 취소/다시 실행 상태 조회 |

#### WebSocket (`/api/v1/ws`)
| 엔드포인트 | 설명 |
|------------|------|
| `/ws` | 실시간 업데이트 |

#### 데이터 관리 (`/api/v1/data`)
| 메서드 | 엔드포인트 | 설명 |
|--------|------------|------|
| POST | `/export` | 아카이브로 데이터 내보내기 |
| POST | `/import` | 아카이브에서 데이터 가져오기 |
| GET | `/sync` | 델타 변경사항 조회 |
| GET | `/integrity` | 데이터베이스 무결성 검사 |

---

## 개발

### 프로젝트 구조

```
local-first-todo/
├── src/
│   └── local_first_todo/
│       ├── __init__.py           # 패키지 메타데이터
│       ├── main.py               # 애플리케이션 진입점
│       ├── dependencies.py       # 의존성 주입
│       ├── api/
│       │   ├── tasks.py          # 작업 엔드포인트
│       │   ├── attachments.py    # 첨부파일 엔드포인트
│       │   ├── search.py         # 검색 엔드포인트
│       │   ├── undo_redo.py      # 실행 취소/다시 실행 엔드포인트
│       │   ├── data.py           # 데이터 관리 엔드포인트
│       │   └── websocket.py      # WebSocket 핸들러
│       ├── database/
│       │   ├── manager.py        # 데이터베이스 연결 관리
│       │   ├── models.py         # 데이터 모델
│       │   ├── schema.py         # SQL 스키마 정의
│       │   └── crud.py           # CRUD 작업
│       └── services/
│           ├── attachment_service.py  # 파일 처리
│           ├── search_service.py      # 검색 기능
│           └── undo_redo_service.py   # 실행 취소/다시 실행 로직
├── static/
│   ├── index.html                # 메인 애플리케이션 페이지
│   ├── css/
│   │   └── app.css               # 애플리케이션 스타일
│   ├── js/
│   │   ├── app.js                # 애플리케이션 로직
│   │   └── vendor/               # 서드파티 라이브러리
│   └── fonts/                    # 사용자 정의 폰트
├── tests/
│   ├── api/                      # API 테스트
│   ├── database/                 # 데이터베이스 테스트
│   ├── services/                 # 서비스 테스트
│   └── e2e/                      # 엔드 투 엔드 테스트
├── scripts/                      # 유틸리티 스크립트
├── requirements.txt              # 프로덕션 의존성
├── requirements-dev.txt          # 개발 의존성
├── pyproject.toml                # 프로젝트 구성
├── noxfile.py                    # 테스트 자동화
└── *.bat                         # Windows 배치 스크립트
```

### 테스트 실행

```bash
# 가상 환경 활성화
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate.bat  # Windows

# 모든 테스트 실행
python -m pytest

# 커버리지와 함께 실행
python -m pytest --cov=local_first_todo --cov-report=html

# 특정 테스트 카테고리 실행
python -m pytest -m "not slow"  # 느린 테스트 건너뛰기
python -m pytest -m perf        # 성능 테스트만

# nox 사용 (자동화된 테스트 세션)
nox -s test         # 전체 테스트 스위트
nox -s test_fast    # 빠른 테스트만
nox -s lint         # 린팅 검사
```

Windows 사용자는 제공된 배치 스크립트를 사용할 수 있습니다:
```batch
"3 run_tests.bat"         :: pytest 실행
"3 run_phase_tests.bat"   :: 페이즈 통합 테스트 실행
```

### 코드 품질

프로젝트는 코드 품질을 유지하기 위해 여러 도구를 사용합니다:

- **Ruff**: 린팅 및 포매팅
- **MyPy**: 정적 타입 검사
- **pytest**: 테스팅 프레임워크
- **Coverage**: 코드 커버리지 리포팅

구성은 `pyproject.toml`에 있습니다:

```toml
[tool.ruff]
target-version = "py310"
line-length = 88

[tool.mypy]
python_version = "3.10"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 설정

### 환경 변수

애플리케이션은 현재 합리적인 기본값을 사용합니다. 향후 버전에서는 다음을 지원할 예정입니다:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TODO_HOST` | `127.0.0.1` | 서버 호스트 |
| `TODO_PORT` | `8765` | 서버 포트 |
| `TODO_DB_PATH` | `./app.db` | 데이터베이스 위치 |
| `TODO_ATTACHMENTS_DIR` | `./attachments` | 첨부파일 디렉터리 |

### 첨부파일 설정

`src/local_first_todo/services/attachment_service.py`를 편집하세요:

```python
# 최대 첨부파일 크기 (기본값: 500MB)
DEFAULT_MAX_ATTACHMENT_SIZE = 500 * 1024 * 1024

# 모든 파일 확장자 허용 (기본값: True)
ALLOW_ALL_EXTENSIONS = True

# 실행 파일 차단 (기본값: 로컬 사용을 위해 False)
BLOCK_EXECUTABLES = False

# 파일 서명 검증 건너뛰기 (기본값: 에어갭 사용을 위해 True)
SKIP_SIGNATURE_VALIDATION = True
```

---

## 보안

### 설계 원칙

1. **로컬 전용**: 외부 네트워크 연결 불필요
2. **데이터 주권**: 모든 데이터는 SQLite에 로컬 저장
3. **콘텐츠 주소 지정 스토리지**: SHA-256 해시로 파일 저장
4. **소프트 삭제**: 기본적으로 복구 가능한 삭제

### 파일 보안

- 파일명 살균 (경로 순회 방지)
- Windows 예약 이름 차단
- 설정 가능한 실행 파일 차단
- 선택적 파일 서명 검증
- 설정 가능한 확장자 화이트리스트

### 데이터베이스 보안

- 외래 키 제약 조건 적용
- 충돌 안전을 위한 WAL 모드
- 준비된 구문 (SQL 인젝션 방지)
- UTC 타임스탬프 유효성 검사

---

## 기여하기

기여를 환영합니다! 다음 단계를 따라주세요:

1. 저장소 포크
2. 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 작성
4. 테스트 실행 (`python -m pytest`)
5. 린팅 실행 (`ruff check . --fix`)
6. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
7. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
8. Pull Request 열기

### 개발 가이드라인

- PEP 8 스타일 가이드라인 준수
- 모든 함수에 타입 힌트 추가
- 새 기능에 대한 테스트 작성
- 필요에 따라 문서 업데이트
- 커밋을 원자적이고 잘 설명된 상태로 유지

---

## 라이선스

이 프로젝트는 MIT 라이선스에 따라 라이선스가 부여됩니다 - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

```
MIT License

Copyright (c) 2025 Local-First To-Do Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 감사의 글

- **FastAPI**: 우수한 비동기 웹 프레임워크
- **SQLite**: 신뢰할 수 있는 임베디드 데이터베이스
- **Lucide**: 아름다운 아이콘 세트
- **Marked.js**: 마크다운 렌더링
- **Bricolage Grotesque, Plus Jakarta Sans, IBM Plex Mono, Pretendard**: 폰트 패밀리

---

<p align="center">
  Local-First To-Do 팀이 🌙과 함께 만들었습니다
</p>
