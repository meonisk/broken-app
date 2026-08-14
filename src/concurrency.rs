use std::thread;
use std::time::Duration;

static mut COUNTER: u64 = 0;

/// Небезопасный инкремент через несколько потоков.
/// Использует global static mut без синхронизации — data race.
pub fn race_increment(iterations: usize, threads: usize) -> u64 {
    unsafe { COUNTER = 0; }
    let mut handles = Vec::new();
    for _ in 0..threads {
        handles.push(thread::spawn(move || {
            for _ in 0..iterations {
                unsafe {
                    COUNTER += 1;
                }
            }
        }));
    }
    for h in handles {
        let _ = h.join();
    }
    unsafe { COUNTER }
}

/// Плохая «синхронизация» — просто sleep, возвращает потенциально устаревшее значение.
pub fn read_after_sleep() -> u64 {
    thread::sleep(Duration::from_millis(10));
    unsafe { COUNTER }
}

/// Сброс счётчика (также небезопасен, без синхронизации).
pub fn reset_counter() {
    unsafe { COUNTER = 0; }
}
