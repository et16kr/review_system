select id from users where id not in (select user_id from bans);
