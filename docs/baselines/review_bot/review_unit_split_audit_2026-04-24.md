# Review Unit Split Audit

- generated_at: `2026-04-24T02:05:24Z`
- max_lines_per_review_unit: `80`
- total_cases: `4`
- selected_language_count: `2`
- selected_languages: `python`, `typescript`

## Selection Rule

현재 fixed-line hunk split이 하나의 logical block을 여러 review unit으로 자르더라도, 후속 unit 시작선이 safe boundary에 맞으면 그대로 두고, indentation/tree 구조 언어에서 mid-block unit start가 남을 때만 `prioritize_syntax_aware_split`로 분류한다.

## Case Summary

| case_id | language | structure | review_units | split_blocks | safe_boundary_starts | mid_block_starts | recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| python_fastapi_long_handler | python | indentation | 2 | 1 | 0 | 1 | prioritize_syntax_aware_split |
| typescript_react_long_component | typescript | jsx_tree | 2 | 1 | 0 | 1 | prioritize_syntax_aware_split |
| yaml_k8s_long_container_env | yaml | yaml_tree | 2 | 1 | 1 | 0 | current_hunk_split_ok |
| go_http_long_handler | go | brace_block | 2 | 1 | 0 | 1 | monitor_current_hunk_split |

## Priority Languages

- `python`: Python handler body가 indentation으로만 경계를 표현하므로 fixed-line split이 mid-block unit을 만들면 anchor와 summary 문맥이 급격히 약해진다.
- `typescript`: TSX component는 JSX tree 단위가 review 문맥인데 fixed-line split이 tree 중간에서 끊기면 component intent와 위험 위치를 함께 보기 어렵다.

## Monitor Only

- `go`: Go long handler도 logical block이 둘로 갈리지만 brace delimiter가 남아 있어 우선순위는 syntax-aware 도입보다 monitor 쪽에 둔다.

## Detailed Findings

### python_fastapi_long_handler

- file_path: `app/api/audit.py`
- recommendation: `prioritize_syntax_aware_split`
- review_unit_count: `2`
- logical_block_ids_split: create_audit_handler
- safe_boundary_unit_starts: `0`
- mid_block_unit_starts: `1`
- rationale: Python handler body가 indentation으로만 경계를 표현하므로 fixed-line split이 mid-block unit을 만들면 anchor와 summary 문맥이 급격히 약해진다.

### typescript_react_long_component

- file_path: `ui/ReviewAuditPanel.tsx`
- recommendation: `prioritize_syntax_aware_split`
- review_unit_count: `2`
- logical_block_ids_split: review_audit_panel_component
- safe_boundary_unit_starts: `0`
- mid_block_unit_starts: `1`
- rationale: TSX component는 JSX tree 단위가 review 문맥인데 fixed-line split이 tree 중간에서 끊기면 component intent와 위험 위치를 함께 보기 어렵다.

### yaml_k8s_long_container_env

- file_path: `deploy/review-audit.yaml`
- recommendation: `current_hunk_split_ok`
- review_unit_count: `2`
- logical_block_ids_split: deployment_container_block
- safe_boundary_unit_starts: `1`
- mid_block_unit_starts: `0`
- rationale: YAML manifest는 indentation tree가 곧 semantic scope라서 container/env block 중간 split은 wrong anchor와 rule explanation drift를 만들기 쉽다.

### go_http_long_handler

- file_path: `handlers/audit.go`
- recommendation: `monitor_current_hunk_split`
- review_unit_count: `2`
- logical_block_ids_split: serve_http_handler
- safe_boundary_unit_starts: `0`
- mid_block_unit_starts: `1`
- rationale: Go long handler도 logical block이 둘로 갈리지만 brace delimiter가 남아 있어 우선순위는 syntax-aware 도입보다 monitor 쪽에 둔다.

