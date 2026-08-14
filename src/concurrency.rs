use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;

static COUNTER: AtomicU64 = AtomicU64::new(0);

/// Инкремент из нескольких потоков. Счётчик атомарный, поэтому инкременты не
/// теряются; порядок между ними не важен, отсюда `Relaxed`.
pub fn race_increment(iterations: usize, threads: usize) -> u64 {
    COUNTER.store(0, Ordering::SeqCst);
    thread::scope(|scope| {
        for _ in 0..threads {
            scope.spawn(|| {
                for _ in 0..iterations {
                    COUNTER.fetch_add(1, Ordering::Relaxed);
                }
            });
        }
    });
    COUNTER.load(Ordering::SeqCst)
}

/// Чтение счётчика. Ждать больше нечего: `race_increment` возвращает управление
/// только после join всех потоков, а `SeqCst` гарантирует видимость записей.
pub fn read_after_sleep() -> u64 {
    COUNTER.load(Ordering::SeqCst)
}

/// Сброс счётчика.
pub fn reset_counter() {
    COUNTER.store(0, Ordering::SeqCst);
}
