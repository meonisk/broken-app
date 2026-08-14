//! Входы и имена бенчмарков зафиксированы: criterion сопоставляет замеры по
//! имени, а сравнивать «до» и «после» имеет смысл только на одних данных.

use broken_app::{algo, normalize, sum_even};
use criterion::{BatchSize, Criterion, criterion_group, criterion_main};

fn bench_sum_even(c: &mut Criterion) {
    let data: Vec<i64> = (0..50_000).collect();
    c.bench_function("sum_even_50k", |b| b.iter(|| sum_even(&data)));
}

fn bench_dedup(c: &mut Criterion) {
    let data: Vec<u64> = (0..20_000).flat_map(|n| [n, n]).collect();
    c.bench_function("dedup_20k", |b| {
        b.iter_batched(
            || data.clone(),
            |v| algo::slow_dedup(&v),
            BatchSize::SmallInput,
        )
    });
}

fn bench_fib(c: &mut Criterion) {
    c.bench_function("fib_32", |b| b.iter(|| algo::slow_fib(32)));
}

fn bench_normalize(c: &mut Criterion) {
    let text = " Hello World \t".repeat(50_000);
    c.bench_function("normalize_700k", |b| b.iter(|| normalize(&text)));
}

criterion_group!(
    benches,
    bench_sum_even,
    bench_dedup,
    bench_fib,
    bench_normalize
);
criterion_main!(benches);
