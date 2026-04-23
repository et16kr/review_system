#[tokio::main]
async fn main() {
    let _task = tokio::spawn(async move {
        do_work().await;
    });

    let (_tx, _rx) = tokio::sync::mpsc::unbounded_channel::<String>();
    std::thread::sleep(std::time::Duration::from_secs(1));
}
