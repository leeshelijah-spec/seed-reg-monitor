# Seed Regulation Monitor

[Read this README in English](README.md)

Seed Regulation Monitor는 종자 산업 관련 규제 변화를 수집하고, 분류하고, 검토할 수 있도록 만든 FastAPI 기반 대시보드 프로젝트입니다.

## 제작자

- Lee, Seunghwan
- [leesh.elijah@gmail.com](mailto:leesh.elijah@gmail.com)

## 주요 기능

- 공포 법령 및 행정규칙 수집
- 입법예고 후보 수집
- 중요도, 카테고리, 관련 부서 자동 분류
- 상세 페이지에서 제개정 이유 확인
- 조치 여부 및 검토 메모 저장
- Markdown 기반 기능 변경 이력 관리

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
```

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

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
copy .env.example .env
```

`.env`에서 최소한 아래 항목을 확인하세요.

- `KOREAN_LAW_MCP_DIR`
- `DB_PATH`
- `ENABLE_SCHEDULER`

알림 발송을 사용하려면 `config/alert-recipients.example.json`을 복사해 `config/alert-recipients.json`을 만들어 사용하세요.

### 4. 앱 실행

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

- 대시보드: [http://127.0.0.1:8010/](http://127.0.0.1:8010/)
- 헬스 체크: [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health)

## 수동 동기화

```bash
python -m app.manual_sync
```

## 감사의 말

이 프로젝트는 [@chrisryugj](https://github.com/chrisryugj)의 [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp)에서 아이디어와 구현 방향의 도움을 받았습니다.

한국 법령 데이터 접근을 더 쉽게 탐색하고 연동할 수 있도록 공개해주신 점에 감사드립니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.
