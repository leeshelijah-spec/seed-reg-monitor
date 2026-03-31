# Feature Updates

기능 추가/삭제가 완료될 때마다 같은 날짜의 Markdown 파일에 변경점을 누적 기록합니다.

예시:

```bash
python scripts/log_feature_update.py \
  --title "상세 페이지 개선" \
  --change "기본정보에 제개정 이유를 추가" \
  --change "판단 근거 하단에 조치 여부 저장 폼을 추가"
```

기록 파일은 `docs/feature-updates/YYYY-MM-DD.md` 형식으로 생성되며, 같은 날짜에 여러 번 실행하면 같은 파일에 시간이 붙은 새 섹션이 이어집니다.
