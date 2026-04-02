# Release Notes

이 프로젝트의 업데이트 내역은 앞으로 `docs/releases/` 아래의 릴리즈 노트로 관리합니다.

## 작성 방식

- 파일 형식: `docs/releases/YYYY-MM-DD.md`
- 한 번의 배포 또는 완료 단위를 하나의 릴리즈로 기록
- README에는 최신 릴리즈 요약만 반영

## 생성 예시

```bash
python scripts/log_release_note.py ^
  --title "뉴스 대시보드 UI 정리" ^
  --summary "상단 구조를 단순화하고 카드 배치를 2x2로 재정렬" ^
  --summary "필터/키워드 관리를 토글 패널로 통합" ^
  --summary "README를 최신 릴리즈 중심으로 정리"
```
