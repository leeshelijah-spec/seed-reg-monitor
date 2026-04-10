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
- 네이버 뉴스 기반 산업 트렌드 수집, 중복 제거, 분석
- 기사 피드백, 키워드 관리, 운영 로그 확인
- 미검토 규제/기사 목록을 칼럼별 체크박스 필터로 바로 좁혀서 확인
- 상단 팝업에서 동기화 상태를 확인하고 분석 화면은 분리 유지

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

- 최신 업데이트: [2026-04-10](docs/feature-updates/2026-04-10.md)
- 피드백 재사용 시 `키워드+제목` 완전일치보다 `original/naver 링크` 일치를 우선 적용하도록 확장했습니다.
- `/refinelogic` 워크플로우 서비스를 추가해 오늘 잡음 판정을 오늘 수집 기사에 반영하고, 뉴스 동기화 1회 후 다시 반영하도록 했습니다.
- `refinelogic.cmd/.sh` 실행기와 PowerShell 프로필 등록 스크립트를 추가해 `/refinelogic` 명령을 바로 사용할 수 있게 했습니다.
- 링크 기반 피드백 재사용과 refinelogic 잡음 전파에 대한 회귀 테스트를 추가했습니다.
- wrapup 관련 스크립트/스킬 문구를 `changelog` 기준에서 `feature-update` 기준으로 정렬했습니다.

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

권장 로컬 실행 방법은 Windows와 Git Bash에서 모두 다음과 같습니다.

```bash
./start_dashboard.sh
```

Windows에서는 아래처럼 실행해도 됩니다.

```bash
start_dashboard.cmd
```

실행기를 거치지 않고 직접 서버를 띄우고 싶다면 아래처럼 `uvicorn`을 실행할 수 있습니다.

```bash
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

- 대시보드: [http://127.0.0.1:8010/](http://127.0.0.1:8010/)
- 헬스 체크: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health)

## 편집 모드

동기화, 리뷰, 키워드 관리, 기사 피드백 같은 수정 기능을 함께 쓰려면 아래 실행기를 사용하세요.

1. Git Bash에서 대시보드를 실행합니다.

```bash
./start_dashboard.sh
```

Windows 사용자는 저장소 루트의 `start_dashboard.cmd`를 실행해도 됩니다.

`.venv`가 없거나 깨져 있으면 실행기가 사용 가능한 base Python을 찾아 가상환경을 다시 만들고 `requirements.txt`를 재설치한 뒤 앱을 시작합니다.

앱 시작 후 `app.manual_sync`를 실행하기 전 최근 동기화 이력을 확인합니다.

- 규제 startup sync는 최근 12시간 내 성공 이력이 있으면 건너뜁니다.
- 뉴스 startup sync는 최근 3시간 내 성공 이력이 있으면 건너뜁니다.

## 수동 동기화

전체 수동 동기화:

```bash
.venv\Scripts\python -m app.manual_sync
```

샘플 뉴스 데이터 주입:

```bash
.venv\Scripts\python scripts/seed_sample_news.py
```

`/refinelogic` 워크플로우 실행(오늘 잡음 피드백을 오늘 수집 기사에 반영한 뒤 뉴스 동기화 1회 실행):

```bash
refinelogic.cmd
```

PowerShell에서 `/refinelogic`를 그대로 입력해 실행하려면 1회 등록:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_refinelogic_command.ps1
```

테스트 실행:

```bash
.venv\Scripts\python -m unittest discover -s tests
```

## 뉴스 모듈 구성

- `app/services/naver_news.py`: 네이버 News API 호출
- `app/services/news_ingestion.py`: 수집, 정제, 중복 병합, 로그 적재
- `app/services/news_analysis.py`: 주제, 영향도, 긴급도, 권장 대응 분석
- `app/services/news_dashboard.py`: KPI, 필터, 차트, 경영 요약 집계
- `app/services/news_keywords.py`: 시드 키워드 및 관리자용 키워드 관리

자세한 구조는 [docs/news-dashboard-architecture.md](docs/news-dashboard-architecture.md)를 참고하세요.

feature update 운영 방식은 [docs/feature-updates/README.md](docs/feature-updates/README.md)를 참고하세요.

## 샘플 데이터

- 샘플 API 응답: `docs/samples/naver-news-sample.json`
- 샘플 적재 스크립트: `scripts/seed_sample_news.py`

## 주의사항

- `.env`, `.env.local`, `config/news-keywords.json`, `data/*.db`는 Git에 올리지 않도록 `.gitignore`에 포함되어 있습니다.
- 뉴스 기사 중복은 `originallink` 기준 해시로 제거하며, 동일 기사가 다른 키워드로 잡히면 `matched_keywords`에 병합됩니다.

## 감사의 말

이 프로젝트는 [@chrisryugj](https://github.com/chrisryugj)의 [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp)에서 아이디어와 구현 방향의 도움을 받았습니다.

한국 법령 데이터 접근을 더 쉽게 탐색하고 연동할 수 있도록 공개해주신 점에 감사드립니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.
