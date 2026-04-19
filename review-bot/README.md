# Review Bot

`review-platform`의 PR diff를 읽고 `review-engine` 규칙 검색 결과를 바탕으로
자동 리뷰 코멘트를 게시하는 최소 봇 서비스입니다.

현재 구현 범위:

- PR 열림/업데이트 이벤트 수신
- 플랫폼 diff 조회
- 엔진 diff 리뷰 호출
- finding dedupe
- 상위 5개 게시
- 수동 다음 배치 게시

개발 서버 실행:

```bash
uv run --project . uvicorn app.api.main:app --reload --port 18081
```
