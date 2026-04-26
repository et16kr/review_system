async fn demo() { tokio::spawn(async move { work().await }); }
