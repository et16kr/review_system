unsafe fn read_raw(ptr: *const i32) -> i32 {
    dbg!(ptr);
    unsafe { *ptr }
}
