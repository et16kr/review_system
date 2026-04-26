#include <mutex>
void demo(std::mutex& m) { m.lock(); m.unlock(); }
