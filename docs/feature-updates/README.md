# Feature Updates

이 디렉터리는 프로젝트의 공식 업데이트 이력을 관리합니다.

## 작성 방식

- 파일 형식: `docs/feature-updates/YYYY-MM-DD.md`
- 같은 날짜에 완료한 기능, 문서, 운영 개선을 한 파일에 누적 기록합니다.
- README에는 최신 업데이트 요약만 반영합니다.

## 생성 예시

```bash
python scripts/log_feature_update.py ^
  --title "대시보드 실행 흐름 정리" ^
  --change "시작 스크립트와 의존성 복구 흐름을 정리" ^
  --change "대시보드 UI 변경과 필터 동작을 문서화" ^
  --change "README 최신 업데이트 요약을 동기화"
```

기존 `scripts/log_release_note.py`는 같은 `feature-updates` 디렉터리를 기록하는 호환용 진입점으로 유지합니다.
