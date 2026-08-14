use std::collections::HashSet;

/// Уникальные значения по возрастанию. Множество вместо линейного поиска по
/// накопленному вектору и одна сортировка в конце вместо сортировки на каждой
/// вставке: O(n² log n) превращается в O(n + k log k).
pub fn slow_dedup(values: &[u64]) -> Vec<u64> {
    let unique: HashSet<u64> = values.iter().copied().collect();
    let mut out: Vec<u64> = unique.into_iter().collect();
    out.sort_unstable();
    out
}

/// Итеративный проход снизу вверх: каждое число считается один раз, а не
/// пересчитывается заново в двух ветках рекурсии.
pub fn slow_fib(n: u64) -> u64 {
    if n == 0 {
        return 0;
    }
    let (mut prev, mut curr) = (0_u64, 1_u64);
    for _ in 1..n {
        let next = prev + curr;
        prev = curr;
        curr = next;
    }
    curr
}
