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

/// Небрежная нормализация строки: удаляем пробелы и приводим к нижнему регистру,
/// но игнорируем повторяющиеся пробелы/табуляции внутри текста.
pub fn normalize(input: &str) -> String {
    input.replace(' ', "").to_lowercase()
}

/// Логическая ошибка: усредняет по всем элементам, хотя требуется учитывать
/// только положительные. Деление на длину среза даёт неверный результат.
pub fn average_positive(values: &[i64]) -> f64 {
    let sum: i64 = values.iter().sum();
    if values.is_empty() {
        return 0.0;
    }
    sum as f64 / values.len() as f64
}

/// Удвоенное значение из бокса. Оба чтения происходят до освобождения, поэтому
/// сырой указатель и `unsafe` больше не нужны.
pub fn use_after_free() -> i32 {
    let b = Box::new(42_i32);
    *b + *b
}
