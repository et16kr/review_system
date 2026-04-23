# Review Bot Wrong-Language Telemetry Operations

## 목적

이 문서는 멀티 랭귀지 운영에서 `wrong-language` 피드백을
detector backlog로 전환하는 최소 운영 루프를 짧게 고정한다.

## Source Of Truth

- source of truth는 `FeedbackEvent.payload`에 저장되는 immutable `wrong-language` 이벤트다.
- 조회 endpoint는 `GET /internal/analytics/wrong-language-feedback`다.
- 운영용 backlog snapshot은 `ops/scripts/build_wrong_language_backlog.py`로 생성한다.

## 권장 실행 순서

1. telemetry snapshot을 수집한다.
2. backlog Markdown을 생성한다.
3. `high` priority pair/path/profile 조합부터 detector blind spot을 수정한다.
4. 수정 후 mixed-language smoke와 telemetry snapshot을 다시 돌려 재발 여부를 확인한다.

## 표준 명령

```bash
curl "http://127.0.0.1:18081/internal/analytics/wrong-language-feedback?window=28d"
python3 /home/et16/work/review_system/ops/scripts/capture_wrong_language_telemetry.py --window 28d
python3 /home/et16/work/review_system/ops/scripts/build_wrong_language_backlog.py --window 28d
```

특정 프로젝트만 보려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/build_wrong_language_backlog.py \
  --project-ref root/review-system-multilang-smoke \
  --window 28d \
  --min-count 1
```

## 우선순위 해석

- `high`: 같은 pair가 반복되거나 특정 `context/profile`에 집중된 경우. registry/detector/prompt routing을 함께 본다.
- `medium`: pair count는 낮지만 framework/profile 경로에 모이는 경우. path/content 신호와 examples를 먼저 보강한다.
- `low`: 단발성 오분류. backlog에 남기되 다음 회귀 묶음에서 함께 처리한다.

## 경로 버킷 해석

- `docs`: `README.md`, `*.mdx`, `docs/**` 같은 문서형 파일. reviewable exclusion과 unreviewable 분류를 먼저 본다.
- `.github/workflows`: GitHub Actions detector와 context selection을 먼저 본다.
- `db`: migration / warehouse / dialect detector를 먼저 본다.
- `src`, `app`, `pages`: framework profile/context detector와 prompt routing을 먼저 본다.
