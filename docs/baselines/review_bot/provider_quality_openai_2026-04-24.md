# Review Bot Provider Quality

- provider: `openai`
- status: `failed`
- provider_runtime: `configured_provider=openai, effective_provider=openai, fallback_used=False, configured_model=gpt-5.2, endpoint_base_url=https://api.openai.com/v1, transport_class=default_openai_base_url`
- total_cases: `6`
- passed_cases: `0`
- failed_cases: `6`

## Case Summary

| case_id | status | title_length | line_ok | missing_terms | forbidden_terms |
| --- | --- | --- | --- | --- | --- |
| yaml_ci_remote_script_execution | failed | 32 | True | - | - |
| python_fastapi_untyped_request_body | failed | 21 | True | - | - |
| python_fastapi_blocking_io | failed | 28 | True | blocking | - |
| sql_ordinal_group_by | failed | 26 | True | explicit | - |
| cuda_async_default_stream | failed | 32 | True | - | - |
| cuda_cooperative_groups_grid_sync | failed | 43 | True | - | - |

## Failures

### yaml_ci_remote_script_execution

- suggested_fix length 324 exceeds 260

### python_fastapi_untyped_request_body

- suggested_fix length 721 exceeds 260

### python_fastapi_blocking_io

- suggested_fix length 386 exceeds 260
- missing required terms: blocking

### sql_ordinal_group_by

- missing required terms: explicit

### cuda_async_default_stream

- suggested_fix length 325 exceeds 280

### cuda_cooperative_groups_grid_sync

- suggested_fix length 503 exceeds 280

