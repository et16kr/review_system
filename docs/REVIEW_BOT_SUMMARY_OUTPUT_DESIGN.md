# Review Bot Summary Output Design

## 목적

현재 성공 기준은 inline discussion lifecycle 복구였다. 이 문서는 다음 단계의 summary/overview 출력을 어떤 역할로 둘지 고정한다.

## 원칙

1. inline discussion이 1차 인터페이스다.
2. summary는 inline을 대체하지 않고 run overview만 제공한다.
3. noisy summary는 금지한다.

## 권장 출력 단위

summary는 thread가 아니라 run 단위로 만든다.

권장 항목:

- 새로 생성된 finding 수
- reopened / updated thread 수
- stale resolve 수
- failed publication 수
- dead-letter 수
- head SHA

## 권장 출력 위치

1순위:

- status/check description

2순위:

- 별도 summary note 또는 MR overview comment

## Collapse 정책

summary는 아래 조건에서만 남긴다.

- 새 finding이 1개 이상일 때
- reopened/resolved 변화가 있을 때
- failed publication 또는 dead-letter가 있을 때

아래 조건이면 summary를 생략한다.

- no-op incremental run
- unchanged open thread만 있었던 run

## 현재 구현 결론

current-state는 inline 중심 운영을 유지한다.

summary output은 다음 차수에서 아래 순서로 추가한다.

1. status/check 문구 확장
2. optional summary note
