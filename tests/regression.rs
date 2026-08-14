//! По тесту на каждый найденный дефект. Сейчас они падают — это и есть
//! фиксация находок; после исправлений должны стать зелёными.

use broken_app::{algo, average_positive, concurrency, normalize, sum_even, use_after_free};

/// Пустой срез: реализация читает элемент за концом, до сложения дело не доходит.
#[test]
fn sum_even_handles_empty_slice() {
    assert_eq!(sum_even(&[]), 0);
}

/// Нечётная длина — лишний элемент за границей меняет ответ.
#[test]
fn sum_even_sums_only_even_values() {
    assert_eq!(sum_even(&[1, 2, 3, 4, 5]), 6);
}

/// Пробел — не единственный пробельный символ, табуляции и переводы строк тоже.
#[test]
fn normalize_removes_all_whitespace() {
    assert_eq!(normalize(" Hello\tBig\nWorld "), "hellobigworld");
}

/// Среднее считается по положительным, а не по всем элементам.
#[test]
fn average_positive_ignores_non_positive() {
    assert!((average_positive(&[-5, 5, 15]) - 10.0).abs() < f64::EPSILON);
    assert_eq!(average_positive(&[-3, -1]), 0.0);
}

/// Значение должно читаться до освобождения бокса, а не после.
#[test]
fn use_after_free_returns_the_boxed_value() {
    assert_eq!(unsafe { use_after_free() }, 84);
}

/// Дубликаты убираются, порядок — по возрастанию.
#[test]
fn dedup_returns_sorted_unique_values() {
    assert_eq!(algo::slow_dedup(&[5, 5, 1, 2, 2, 3]), vec![1, 2, 3, 5]);
    assert_eq!(algo::slow_dedup(&[]), Vec::<u64>::new());
}

#[test]
fn fib_matches_known_values() {
    let expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55];
    for (n, want) in expected.iter().enumerate() {
        assert_eq!(algo::slow_fib(n as u64), *want);
    }
}

/// Оба потоковых дефекта в одном тесте: счётчик теряет инкременты, а чтение
/// после sleep не гарантирует, что видно итоговое значение.
#[test]
fn counter_keeps_every_increment_and_is_visible_after_join() {
    concurrency::reset_counter();
    let total = concurrency::race_increment(10_000, 4);
    assert_eq!(total, 40_000);
    assert_eq!(concurrency::read_after_sleep(), 40_000);
}
