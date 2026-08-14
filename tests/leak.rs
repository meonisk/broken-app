//! Утечку не поймать обычным assert'ом, поэтому считаем аллокации своим
//! аллокатором. Тест вынесен в отдельный файл: счётчики глобальные, и соседние
//! тесты в одном бинарнике сбивали бы их своими аллокациями.

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

static ALLOCS: AtomicUsize = AtomicUsize::new(0);
static DEALLOCS: AtomicUsize = AtomicUsize::new(0);

struct Counting;

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        DEALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.dealloc(ptr, layout) }
    }
}

#[global_allocator]
static ALLOCATOR: Counting = Counting;

#[test]
fn leak_buffer_frees_everything_it_allocates() {
    let data = [1_u8, 0, 2, 3, 0, 4];

    let allocs = ALLOCS.load(Ordering::Relaxed);
    let deallocs = DEALLOCS.load(Ordering::Relaxed);
    assert_eq!(broken_app::leak_buffer(&data), 4);

    let made = ALLOCS.load(Ordering::Relaxed) - allocs;
    let freed = DEALLOCS.load(Ordering::Relaxed) - deallocs;
    assert_eq!(made, freed, "{made} аллокаций, освобождено {freed}");
}
