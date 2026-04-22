class WorkerRunner {
    void start() {
        try {
            work();
        } catch (Exception ex) {
            log(ex);
        }
        new Thread(() -> work()).start();
    }

    void work() {}

    void log(Exception ex) {}
}
