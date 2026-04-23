select * from {{ ref('events') }};
{{ run_query("vacuum analytics.events") }}
