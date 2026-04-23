dbt warehouse SQL 검토 시 특히 아래를 중요하게 봅니다.

- model contract가 `select *` 나 암묵적 projection drift로 흔들리지 않는지
- Jinja와 run_query가 실제 SQL boundary를 과도하게 숨기지 않는지
- incremental/freshness/unique-key 가정이 코드에서 보이는지
