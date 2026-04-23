select
  user_id,
  date_trunc('day', created_at) as day_bucket,
  count(*) as total_rows
from events
where created_at >= current_date - interval '7 day'
group by 1, 2;
