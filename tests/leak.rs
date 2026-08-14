//! Утечку обычным assert'ом не поймать, нужен счётчик аллокаций. Своего писать
//! не стали — берём готовый `stats_alloc`. Тест вынесен в отдельный файл:
//! аллокатор глобальный, и соседние тесты сбивали бы счётчики.

use stats_alloc::{INSTRUMENTED_SYSTEM, Region, StatsAlloc};
use std::alloc::System;

#[global_allocator]
static ALLOCATOR: &StatsAlloc<System> = &INSTRUMENTED_SYSTEM;

#[test]
fn leak_buffer_frees_everything_it_allocates() {
    let data = [1_u8, 0, 2, 3, 0, 4];

    let region = Region::new(ALLOCATOR);
    assert_eq!(broken_app::leak_buffer(&data), 4);
    let stats = region.change();

    assert_eq!(
        stats.bytes_allocated, stats.bytes_deallocated,
        "выделено {} байт, освобождено {}",
        stats.bytes_allocated, stats.bytes_deallocated
    );
}
