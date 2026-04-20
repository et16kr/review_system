# Review Bot

`review-platform`의 PR diff를 읽고 `review-engine` 규칙 검색 결과를 바탕으로
자동 리뷰 코멘트를 게시하는 최소 봇 서비스입니다.

현재 구현 범위:

- GitLab MR note webhook 수신
- 리뷰 요청 key 기반 run 생성
- 엔진 diff 리뷰 호출
- inline discussion 게시 및 sync
- feedback 이벤트 수집
- 기본 게시 batch cap `10`

외부 GitLab 기준 트리거:

- MR open/update로는 자동 리뷰하지 않음
- MR 코멘트에 `@review-bot` mention이 있을 때만 리뷰 실행

개발 서버 실행:

```bash
uv run --project . uvicorn review_bot.api.main:app --reload --port 18081
```
