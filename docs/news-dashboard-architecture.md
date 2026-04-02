# 네이버 뉴스 트렌드 모듈 아키텍처

## 개요

기존 규제 모니터링 대시보드에 네이버 뉴스 기반 산업 트렌드/대응 분석 모듈을 추가했습니다.

- 규제 모니터링: 한국 법령 수집/분류/검토
- 뉴스 트렌드: 네이버 뉴스 수집/중복제거/분석/운영관리
- 단일 대시보드: KPI, 필터, 기사 리스트, 트렌드 차트, 경영 요약, 키워드 관리

## 계층 분리

### 1. API 호출 계층

- `app/services/naver_news.py`
- 네이버 Search News API 호출
- 헤더 기반 인증
- 재시도와 타임아웃 처리

### 2. 수집/정제 계층

- `app/services/news_ingestion.py`
- `app/services/news_utils.py`
- HTML `<b>` 태그 제거
- `pubDate` 파싱
- `originallink` 정규화 및 `duplicate_hash` 생성
- 키워드별 수집 로그 저장

### 3. 분석 계층

- `app/services/news_analysis.py`
- 규칙 기반 1차 분류
- 카테고리, 영향도, 긴급도, 담당부서, 권장 대응문 자동 생성
- 설명 가능한 `analysis_trace` 저장
- LLM 보정 확장 지점 예약

### 4. 키워드 관리 계층

- `app/services/news_keywords.py`
- 기본 키워드 + 기존 규제 분류 키워드 참조 병합
- 파일 시드 또는 DB 기반 활성/비활성 관리

### 5. UI/집계 계층

- `app/services/news_dashboard.py`
- KPI 집계
- 필터링
- 카테고리/키워드 추세 데이터 생성
- 경영 요약 패널 생성
- 운영 현황 집계

## DB 스키마

### `news_keywords`

- 키워드와 그룹, 활성 여부, 출처를 관리

### `news_articles`

- 요구된 주요 컬럼 전부 포함
- 추가 컬럼
  - `matched_keywords`: 중복 기사에 연결된 키워드 병합 목록
  - `analysis_trace`: 규칙 기반 판단 근거 JSON

### `news_collection_logs`

- 키워드별 수집 실행 이력
- 호출 상태, 재시도, 수집/저장 건수, 오류 메시지 기록

### `news_feedback`

- 중요/잡음/분류오류 피드백 저장

## 백엔드 엔드포인트

### HTML 라우트

- `GET /`
  - 규제 + 뉴스 통합 대시보드
- `POST /sync`
  - 규제 수동 동기화
- `POST /news/sync`
  - 뉴스 수동 수집
- `POST /news/keywords`
  - 키워드 추가
- `POST /news/keywords/{keyword_id}/toggle`
  - 키워드 활성/비활성
- `POST /news/{article_id}/feedback`
  - 기사 피드백 저장

### JSON API

- `GET /api/news/dashboard`
  - 뉴스 KPI, 기사 리스트, 트렌드, 운영 현황 반환
- `GET /api/news/articles`
  - 필터링된 뉴스 기사 리스트 반환

## 스케줄러

- 기존 규제 동기화 스케줄 유지
- 네이버 API 키가 설정된 경우 뉴스 수집 스케줄 추가
- 기본값: 평일 `08:40` Asia/Seoul

## 운영 포인트

- 네이버 인증값은 `.env.local`에 두고 Git에 커밋하지 않음
- 저장소에는 `.env.example`와 `config/news-keywords.example.json`만 포함
- 실제 API 키는 각 사용자가 네이버 개발자 센터에서 직접 발급
- 샘플 데이터는 `docs/samples/naver-news-sample.json`과 `scripts/seed_sample_news.py`로 주입 가능
