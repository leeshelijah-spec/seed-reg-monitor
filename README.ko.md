# Seed Regulation Monitor

[Read this README in English](README.md)

Seed Regulation Monitor는 종자 산업 관련 규제 변화와 네이버 뉴스 기반 산업 트렌드를 함께 수집, 분석, 검토할 수 있도록 만든 FastAPI 기반 대시보드입니다.

## 제작자

- Lee, Seunghwan

## 주요 기능

- 공포 법령 및 행정규칙 수집
- 입법예고 후보 수집
- 중요도, 카테고리, 관련 부서 자동 분류
- 상세 페이지에서 제개정 이유 확인
- 조치 여부 및 검토 메모 저장
- 네이버 뉴스 기반 산업 트렌드 수집/중복제거/분석
- 기사 피드백, 키워드 관리, 운영 로그 확인
- 미검토 규제/기사 목록을 칼럼별 체크박스 필터로 바로 좁혀서 확인
- 뉴스 운영 현황을 상단 버튼의 모달 팝업으로 열어 분석 화면과 분리
- 날짜별 feature update 기반 업데이트 이력 관리

## 기술 스택

- FastAPI
- Jinja2
- Chart.js
- SQLite
- APScheduler

## 프로젝트 구조

```text
app/
  main.py
  routes/
  services/
  templates/
  static/
config/
data/
docs/
scripts/
tests/
```

## 최신 업데이트

- 최신 업데이트: [2026-04-06](docs/feature-updates/2026-04-06.md)
- 읽기 전용/ngrok 공유 기능을 제거하고 수정 가능한 단일 대시보드 모드로 정리
- 읽기 전용 분기와 쓰기 차단 미들웨어를 제거해 화면과 요청 흐름을 단순화
- 시작 스크립트가 실행 가능한 base Python을 찾아 `.venv`를 재생성하고 의존성을 다시 설치할 수 있도록 보강
- 시작 직후 1회 자동 동기화, KPI hover 툴팁, 운영현황 모달, 칼럼별 체크박스 필터는 유지

## 빠른 시작

### 1. 가상환경 생성

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. 의존성 설치

Windows:

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux:

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
copy .env.example .env
copy .env.example .env.local
```

기본 설정은 `.env`, 개인별 비밀값은 `.env.local`에 두는 것을 권장합니다.

최소 확인 항목:

- `KOREAN_LAW_MCP_DIR`
- `DB_PATH`
- `ENABLE_SCHEDULER`

뉴스 수집에 필요한 항목:

- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `NEWS_KEYWORDS_PATH`
- `NEWS_SCHEDULER_HOUR`
- `NEWS_SCHEDULER_MINUTE`

네이버 API 키는 저장소에 포함하지 말고 각자 [네이버 개발자 센터](https://developers.naver.com/products/intro/plan/plan.md)에서 발급받아 입력하세요.

키워드 파일이 필요하면 `config/news-keywords.example.json`을 복사해 `config/news-keywords.json`으로 사용할 수 있습니다.

알림 발송을 사용하려면 `config/alert-recipients.example.json`을 복사해 `config/alert-recipients.json`을 만들어 사용하세요.

### 4. 앱 실행

Windows:

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

macOS / Linux:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

가상환경을 activate 하지 않은 상태라면 `uvicorn` 대신 항상 `.venv\Scripts\python -m uvicorn ...` 형식을 사용하세요.

- 대시보드: [http://127.0.0.1:8010/](http://127.0.0.1:8010/)
- 헬스 체크: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health)

## 편집 모드

동기화, 리뷰, 키워드 관리, 기사 피드백 같은 수정 기능을 함께 쓰려면 아래 실행기를 사용하세요.

1. 대시보드를 실행합니다.

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
```

Windows 사용자는 저장소 루트의 `start_dashboard.cmd`를 더블 클릭해서 실행할 수도 있습니다.

`.venv`가 없거나 깨져 있으면 시작 스크립트가 실행 가능한 base Python을 찾아 가상환경을 다시 만들고 `requirements.txt`를 재설치한 뒤 앱 시작을 다시 시도합니다.

Python 재설치 후에도 PowerShell에서 Python을 찾지 못하면 실행 세션에서 `PYTHON_EXE`를 직접 지정해 시작할 수 있습니다.

```powershell
$env:PYTHON_EXE = "C:\Path\To\python.exe"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dashboard.ps1
```

앱이 `Application startup complete` 상태에 도달하면 `app.manual_sync`가 한 번 실행되어 규제 동기화와 네이버 뉴스 수집이 각각 1회 자동 수행됩니다.

## 수동 동기화

전체 수동 동기화:

```bash
.venv\Scripts\python -m app.manual_sync
```

샘플 뉴스 데이터 주입:

```bash
.venv\Scripts\python scripts/seed_sample_news.py
```

테스트 실행:

```bash
.venv\Scripts\python -m unittest discover -s tests
```

## 뉴스 모듈 구성

- `app/services/naver_news.py`: 네이버 News API 호출
- `app/services/news_ingestion.py`: 수집, 정제, 중복 병합, 로그 적재
- `app/services/news_analysis.py`: 주제/영향도/긴급도/권장 대응 분석
- `app/services/news_dashboard.py`: KPI, 필터, 차트, 경영 요약 집계
- `app/services/news_keywords.py`: 시드 키워드 및 관리자용 키워드 관리

자세한 구조는 [docs/news-dashboard-architecture.md](docs/news-dashboard-architecture.md)를 참고하세요.

feature update 운영 방식은 [docs/feature-updates/README.md](docs/feature-updates/README.md)를 참고하세요.

## 샘플 데이터

- 샘플 API 응답: `docs/samples/naver-news-sample.json`
- 샘플 적재 스크립트: `scripts/seed_sample_news.py`

## 주의사항

- `.env`, `.env.local`, `config/news-keywords.json`, `data/*.db`는 Git에 올리지 않도록 `.gitignore`에 포함되어 있습니다.
- 네이버 인증값은 절대 예제 파일이나 커밋에 직접 넣지 마세요.
- 뉴스 기사 중복은 `originallink` 기준 해시로 제거하며, 동일 기사가 다른 키워드로 잡히면 `matched_keywords`에 병합됩니다.

## 감사의 말

이 프로젝트는 [@chrisryugj](https://github.com/chrisryugj)의 [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp)에서 아이디어와 구현 방향의 도움을 받았습니다.

한국 법령 데이터 접근을 더 쉽게 탐색하고 연동할 수 있도록 공개해주신 점에 감사드립니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.
