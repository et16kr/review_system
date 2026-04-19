# Review Platform

사내 bare Git 저장소와 PR 메타데이터를 관리하는 최소 PR 리뷰 플랫폼입니다.

현재 구현 범위:

- 저장소 생성 및 조회
- bare repo 경로 관리
- PR 생성 및 조회
- base/head diff 조회
- 댓글 저장
- 상태 저장

개발 서버 실행:

```bash
uv run --project . uvicorn app.api.main:app --reload --port 18080
```
