use broken_app::{algo, sum_even};
use std::time::{Duration, Instant};

fn time_it(label: &str, mut f: impl FnMut()) {
    let start = Instant::now();
    f();
    let elapsed = start.elapsed();
    println!("{label}: {:?}", elapsed);
}

fn main() {
    let data: Vec<i64> = (0..50_000).collect();
    let fib_n = 32;
    let dedup_data: Vec<u64> = (0..5_000).flat_map(|n| [n, n]).collect();

    // Несколько прогонов для устойчивости.
    for _ in 0..3 {
        time_it("sum_even", || {
            let _ = sum_even(&data);
        });

        time_it("slow_fib", || {
            let _ = algo::slow_fib(fib_n);
        });

        time_it("slow_dedup", || {
            let _ = algo::slow_dedup(&dedup_data);
        });
    }
}
