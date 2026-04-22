select *
from users
where id not in (select user_id from disabled_users)
order by 1;
