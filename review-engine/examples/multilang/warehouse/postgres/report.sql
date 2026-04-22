execute format(
    'select * from reports order by %s limit $1',
    sort_column
);
