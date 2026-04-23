drop table legacy_users;
alter table accounts drop column legacy_flag;
alter table orders alter column status set not null;
create index idx_orders_created_at on orders(created_at);
