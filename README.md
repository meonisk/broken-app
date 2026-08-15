# broken-app

[![CI](https://github.com/meonisk/broken-app/actions/workflows/ci.yml/badge.svg)](https://github.com/meonisk/broken-app/actions/workflows/ci.yml)

Проектная работа модуля 5. В исходном коде посажены девять дефектов — от UB до
квадратичных алгоритмов. Они найдены динамическим анализом, исправлены, закрыты
регрессионными тестами; горячие участки спрофилированы и переписаны.

Эталон поведения — [reference-app](https://github.com/meonisk/reference-app),
коммит `f6d62a0`. Не изменялся, зависимостью не подключён. `cargo run --bin demo`
в обоих проектах даёт одинаковый вывод.

Текст README написан Claude (Opus 5) по выводу инструментов.

## Быстрый старт

```bash
cargo build --workspace
```

```bash
cargo test
```

15 тестов: 6 исходных, 8 регрессионных, 1 на утечку.

```bash
cargo run --bin demo
```

## Структура

```
src/lib.rs            sum_even, leak_buffer, normalize, average_positive, use_after_free
src/algo.rs           slow_dedup, slow_fib
src/concurrency.rs    race_increment, read_after_sleep, reset_counter
src/bin/demo.rs       демонстрация, вывод совпадает с эталоном

tests/integration.rs  исходные тесты из задания
tests/regression.rs   по тесту на каждый дефект
tests/leak.rs         утечка, аллокации считает stats_alloc

benches/criterion.rs  фиксированные входы и имена

artifacts/before/     исходный код
artifacts/fixed/      дефекты исправлены, оптимизаций нет
artifacts/after/      после оптимизаций
artifacts/criterion/  отчёт criterion целиком
```

Имена `slow_dedup` и `slow_fib` оставлены как в задании: criterion сопоставляет
замеры по идентификатору бенчмарка.

Зависимости — `criterion` и `stats_alloc`, обе dev.

## Инструменты и логи

| Инструмент | Измеряет | Файл |
|---|---|---|
| gdb | кадр падения | `artifacts/*/gdb.txt` |
| Miri | UB: выход за границы, use-after-free, гонки | `artifacts/*/miri.txt` |
| Valgrind memcheck | утечки | `artifacts/*/valgrind.txt` |
| ASan / TSan | то же на настоящем железе | `artifacts/*/asan.txt`, `tsan.txt` |
| criterion 0.5 | время, доверительные интервалы, графики | `artifacts/criterion/` |
| critcmp | сравнение базовых линий | `artifacts/critcmp.txt` |
| callgrind | инструкции | `artifacts/*/callgrind.txt` |
| DHAT | аллокации и обращения к куче | `artifacts/*/dhat.txt` |
| perf + inferno | флеймграфы | `artifacts/*/flamegraph*.svg` |

Всё считается в CI: [`analysis.yml`](.github/workflows/analysis.yml) —
корректность, [`bench.yml`](.github/workflows/bench.yml) — замеры.

## Дефекты

| # | Где | Что не так | Чем найдено | Тест |
|---|-----|-----------|-------------|------|
| 1 | `sum_even` | `get_unchecked(idx)` в цикле `0..=len`, чтение за границей | gdb, Miri, ASan | `sum_even_handles_empty_slice`, `sum_even_sums_only_even_values` |
| 2 | `leak_buffer` | `Box::into_raw` без `from_raw` | Valgrind, ASan, Miri | `tests/leak.rs` |
| 3 | `normalize` | удалялся только пробел U+0020 | `cargo test` | `normalize_removes_all_whitespace` |
| 4 | `average_positive` | сумма положительных делилась на длину всего среза | `cargo test` | `average_positive_ignores_non_positive` |
| 5 | `use_after_free` | разыменование указателя после `drop` | gdb, Miri, ASan | `use_after_free_returns_the_boxed_value` |
| 6 | `slow_dedup` | линейный поиск и сортировка на каждой вставке, O(n² log n) | criterion, callgrind | `dedup_returns_sorted_unique_values` |
| 7 | `slow_fib` | экспоненциальная рекурсия | criterion | `fib_matches_known_values` |
| 8 | `race_increment` | `static mut` без синхронизации | Miri, TSan | `counter_keeps_every_increment_and_is_visible_after_join` |
| 9 | `read_after_sleep` | `sleep` вместо синхронизации, тот же `static mut` | Miri, TSan | тот же тест |

Гонка воспроизводится: четыре потока по 10 000 инкрементов дали 30 488 вместо
40 000.

Дефект 5 gdb показывает значением: вместо 84 из освобождённой памяти читается
`3215183`. Дефект 1 — [`before/gdb.txt`](artifacts/before/gdb.txt):

```
Thread 2 "sum_even_handle" received signal SIGABRT, Aborted.
#13 core::slice::index::{impl#2}::get_unchecked::precondition_check (this=0, len=0)
#16 broken_app::sum_even (values=...) at src/lib.rs:11
#17 regression::sum_even_handles_empty_slice () at tests/regression.rs:9
```

## Прогоны

| | before | fixed | after |
|---|---|---|---|
| `cargo test` | 6 / 9 | 15 / 0 | 15 / 0 |
| Miri | UB в 10 тестах из 15 | чисто | чисто |
| Valgrind | 6 и 5 байт `definitely lost` в двух бинарниках | 0 | 0 |
| ASan | 6 / 9 | 15 / 0 | 15 / 0 |
| TSan | 6 / 9 | 14 / 1 | 15 / 0 |

Каждый тест запускается отдельным процессом: дефект 1 даёт non-unwinding panic и
роняет бинарник целиком, иначе в логе видна только первая находка.

Единица в колонке fixed — тест на утечку под TSan. Аллокации тогда считал
самописный `GlobalAlloc`, он видел и аллокации санитайзера; Valgrind на том же
коммите дал `definitely lost: 0`. Счётчик заменён на `stats_alloc`.

## Оптимизации

Мерилось от стадии fixed: пока `sum_even` читает за границей среза, мерить
нечего.

Алгоритмические:

- `slow_dedup` — линейный поиск по накопленному вектору и сортировка целиком
  после каждой вставки, O(n² log n). Стало: `HashSet` и одна сортировка в конце,
  O(n + k log k).
- `slow_fib` — двойная рекурсия, каждое число считается многократно. Стало:
  итеративный проход снизу вверх.

Микро:

- `normalize` — три прохода и две промежуточные строки
  (`split_whitespace().collect()`, затем `to_lowercase()`). Стало: один проход в
  предвыделенный буфер, отдельная ветка для ASCII без юникодных таблиц.
- `leak_buffer` — копия входа в кучу ради подсчёта байтов. Стало: подсчёт по
  срезу, аллокаций нет.

## Замеры

Один прогон [`bench.yml`](.github/workflows/bench.yml): на одной машине снимается
базовая линия на `src/` стадии fixed, затем `src/` подменяется на текущий и замер
повторяется против этой линии. Бенчмарки и входы не меняются.

### Время

`cargo bench -- --baseline fixed`, [`after/criterion.txt`](artifacts/after/criterion.txt):

| Бенчмарк | fixed | after | Раз | Изменение, 95 % ДИ | p |
|---|---|---|---|---|---|
| `dedup_20k` | 284,19 мс | 911,07 мкс | 312 | −99,684 … −99,675 % | 0,00 |
| `fib_32` | 6,1653 мс | 5,5406 нс | 1 110 000 | −100,000 % | 0,00 |
| `normalize_700k` | 1,3697 мс | 1,0788 мс | 1,27 | −22,086 … −19,863 % | 0,00 |
| `sum_even_50k` | 13,648 мкс | 13,614 мкс | 1,00 | −1,62 … +0,59 % | 0,52 |

`sum_even` между стадиями не менялся ни на строку — контрольная строка, p = 0,52
означает отсутствие разницы.

Те же выборки в виде отношений — [`critcmp.txt`](artifacts/critcmp.txt).

### Инструкции

Время на общем раннере плавает, счётчик инструкций — нет. `callgrind`, режим
`--bench --test`, каждый бенчмарк ровно один раз:

| | Ir |
|---|---|
| fixed | 3 492 735 821 |
| after | 28 543 182 |

В 122 раза меньше, число повторяется от прогона к прогону.

### Память

`valgrind --tool=dhat`, [`fixed`](artifacts/fixed/dhat.txt) и
[`after`](artifacts/after/dhat.txt):

| | fixed | after |
|---|---|---|
| выделено | 4 055 509 Б / 895 блоков | 3 432 525 Б / 866 |
| пик | 1 759 452 Б / 137 блоков | 1 435 164 Б / 136 |
| прочитано из кучи | 4 804 672 549 Б | 7 612 237 Б |
| записано в кучу | 3 896 300 Б | 6 566 300 Б |

Чтений в 631 раз меньше — это линейный поиск, перечитывавший весь накопленный
вектор на каждой вставке. Записей больше: `HashSet` раскладывает значения по
корзинам, сортировка почти упорядоченного вектора только читала.

## Профиль

### callgrind

Инструкции по функциям, [`fixed/callgrind.txt`](artifacts/fixed/callgrind.txt):

| Доля | Ir | Кадр |
|---|---|---|
| 28,63 % | 1 000 028 970 | `ipnsort` — сортировка из `slow_dedup` |
| 22,91 % | 800 040 001 | `slow_dedup`, разыменование при линейном поиске |
| 11,46 % | 400 180 002 | `slow_dedup`, итератор по срезу |
| 11,45 % | 400 080 022 | `slow_dedup`, `src/algo.rs` |
| 11,45 % | 400 000 190 | `slow_dedup`, сравнения |
| 2,04 % | 71 323 483 | `slow_fib` |

`slow_dedup` вместе с вызываемой из него сортировкой — 86 % инструкций.
Переписан первым.

После ([`after/callgrind.txt`](artifacts/after/callgrind.txt)) наверху
`normalize` — 54 % от в 122 раза меньшего числа, дальше раскладка `HashSet` по
корзинам, 12,33 %. `slow_dedup` из верхних строк ушёл, `slow_fib` не виден.

### Флеймграфы

`perf` + `inferno`, режим `--bench --test`: каждый бенчмарк прогоняется по разу,
ширина кадра равна доле работы. Бинарник собран с `-C force-frame-pointers=yes`,
без них perf терял половину стеков.

| Картинка | Что на ней |
|---|---|
| [fixed](artifacts/fixed/flamegraph.svg) | `slow_dedup` — 94,4 % ширины, внутри него сортировка на 31,5 % |
| [after](artifacts/after/flamegraph.svg) | `slow_dedup` 45 %, `normalize` 24 %; общий объём работы меньше в 122 раза |
| [fixed, только `fib_32`](artifacts/fixed/flamegraph-fib.svg) | 26 вложенных кадров `slow_fib`, верхний — 74,8 % |

`slow_fib` вынесен отдельной картинкой: в общем профиле он занимает 3,2 % и
рекурсия в такой ширине неразличима. Он в 45 раз дешевле `slow_dedup`.

После оптимизации `fib` не профилировался: 5,5 нс на вызов, процесс стартует
дольше.

SVG открываются в браузере — работает поиск по кадрам и клик для зума. Рядом
лежат `.png`.

## Графики criterion

Отчёт сохранён целиком:
[`artifacts/criterion/report/index.html`](artifacts/criterion/report/index.html).

| Бенчмарк | Плотность | Регрессия | t-тест против базовой линии |
|---|---|---|---|
| `dedup_20k` | [pdf](artifacts/criterion/dedup_20k/report/pdf.svg) | [regression](artifacts/criterion/dedup_20k/report/regression.svg) | [t-test](artifacts/criterion/dedup_20k/report/change/t-test.svg) |
| `fib_32` | [pdf](artifacts/criterion/fib_32/report/pdf.svg) | [regression](artifacts/criterion/fib_32/report/regression.svg) | [t-test](artifacts/criterion/fib_32/report/change/t-test.svg) |
| `normalize_700k` | [pdf](artifacts/criterion/normalize_700k/report/pdf.svg) | [regression](artifacts/criterion/normalize_700k/report/regression.svg) | [t-test](artifacts/criterion/normalize_700k/report/change/t-test.svg) |
| `sum_even_50k` | [pdf](artifacts/criterion/sum_even_50k/report/pdf.svg) | [regression](artifacts/criterion/sum_even_50k/report/regression.svg) | [t-test](artifacts/criterion/sum_even_50k/report/change/t-test.svg) |

Наложение обеих выборок (`report/both/pdf.svg`) при разнице в 312 раз
вырождается в линию у нуля.

## Воспроизведение

Работа велась на Windows: Valgrind под него не существует, TSan не поддерживается
для `x86_64-pc-windows-msvc`. Анализ и замеры гоняются на Linux в CI.

Анализ — workflow принимает коммит и имя набора логов:

```bash
gh workflow run analysis.yml -f ref=$(git rev-parse HEAD) -f stage=after
```

Локально:

```bash
cargo +nightly miri test
```

```bash
valgrind --leak-check=full ./target/debug/deps/regression-<hash>
```

Замеры — обе стадии на одной машине:

```bash
gh workflow run bench.yml -f base=8c42bd8
```

Локально — на коде стадии fixed и на текущем:

```bash
cargo bench -- --save-baseline fixed
```

```bash
cargo bench -- --baseline fixed
```

```bash
critcmp fixed new
```

Аргументы бенчмарков закрыты `black_box`: без него `fib(32)` сворачивается в
константу и бенчмарк меряет чтение из памяти.

## Окружение

```
rustc 1.97.1 stable            сборка, тесты, бенчмарки
nightly + miri                 динамический анализ
criterion 0.5, stats_alloc 0.1
valgrind 3.22                  memcheck, callgrind, dhat
edition 2024
цель: x86_64-unknown-linux-gnu (замеры и логи), x86_64-pc-windows-msvc (разработка)
```
