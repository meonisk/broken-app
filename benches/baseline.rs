//! Время и число аллокаций на вызов. criterion считает время со статистикой,
//! но походы в кучу не показывает, а после оптимизации меняются именно они.

use broken_app::{algo, normalize, sum_even};
use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

static ALLOCS: AtomicUsize = AtomicUsize::new(0);

struct Counting;

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }
}

#[global_allocator]
static ALLOCATOR: Counting = Counting;

const RUNS: u32 = 5;

fn measure(label: &str, mut f: impl FnMut()) {
    f();
    let before = ALLOCS.load(Ordering::Relaxed);
    let start = Instant::now();
    for _ in 0..RUNS {
        f();
    }
    let elapsed = start.elapsed() / RUNS;
    let allocs = (ALLOCS.load(Ordering::Relaxed) - before) / RUNS as usize;
    println!("{label}: {elapsed:?}, аллокаций {allocs}");
}

fn main() {
    let numbers: Vec<i64> = (0..50_000).collect();
    let dedup_input: Vec<u64> = (0..20_000).flat_map(|n| [n, n]).collect();
    let text = " Hello World \t".repeat(50_000);

    measure("sum_even 50k", || {
        black_box(sum_even(black_box(&numbers)));
    });
    measure("dedup 20k", || {
        black_box(algo::slow_dedup(black_box(&dedup_input)));
    });
    measure("fib 32", || {
        black_box(algo::slow_fib(black_box(32)));
    });
    measure("normalize 700k", || {
        black_box(normalize(black_box(&text)));
    });
}
