Migration SQL 검토 시 특히 아래를 중요하게 봅니다.

- destructive DDL이 staged rollout 없이 바로 들어오지 않는지
- nullability, index, lock impact 같은 운영 가정이 명시적인지
- reader/writer compatibility window를 로컬 diff에서 설명할 수 있는지
