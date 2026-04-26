void demo() { cp_async_bulk_tensor(dst, src); barrier_arrive_tx(bar); process_tile(); }
