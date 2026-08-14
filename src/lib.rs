pub mod algo;
pub mod concurrency;

/// Сумма чётных значений.
pub fn sum_even(values: &[i64]) -> i64 {
    values.iter().copied().filter(|v| v % 2 == 0).sum()
}

/// Подсчёт ненулевых байтов. Копия входа теперь обычный `Box` и освобождается
/// сама — сырой указатель здесь ничего не давал, кроме утечки.
pub fn leak_buffer(input: &[u8]) -> usize {
    let boxed = input.to_vec().into_boxed_slice();
    boxed.iter().filter(|&&b| b != 0).count()
}

/// Нормализация строки: убираем любые пробельные символы, а не только пробел
/// U+0020, и приводим к нижнему регистру.
pub fn normalize(input: &str) -> String {
    input.split_whitespace().collect::<String>().to_lowercase()
}

/// Среднее по положительным значениям. Делить надо на их количество, а не на
/// длину всего среза.
pub fn average_positive(values: &[i64]) -> f64 {
    let (sum, count) = values
        .iter()
        .filter(|&&v| v > 0)
        .fold((0_i64, 0_usize), |(sum, count), &v| (sum + v, count + 1));
    if count == 0 {
        return 0.0;
    }
    sum as f64 / count as f64
}

/// Удвоенное значение из бокса. Оба чтения происходят до освобождения, поэтому
/// сырой указатель и `unsafe` больше не нужны.
pub fn use_after_free() -> i32 {
    let b = Box::new(42_i32);
    *b + *b
}
