# broken-app

[![CI](https://github.com/meonisk/broken-app/actions/workflows/ci.yml/badge.svg)](https://github.com/meonisk/broken-app/actions/workflows/ci.yml)

Проектная работа модуля 5. В коде посажены дефекты — от UB до квадратичных
алгоритмов. Надо найти их динамическим анализом, закрыть тестами,
спрофилировать и оптимизировать.

Эталон поведения — [reference-app](https://github.com/meonisk/reference-app),
коммит `f6d62a0`. Сюда не копировался и зависимостью не подключён; по нему
сверялось, что должно получаться. `cargo run --bin demo` в обоих проектах даёт
одно и то же.

Текст README написан Claude (Opus 5) по выводу инструментов.

## Инструменты

Своего кода для отчётов тут нет — ни генераторов, ни самописных счётчиков. Всё
считают готовые программы, и считают в CI.

| Инструмент | Что даёт | Логи |
|---|---|---|
| gdb | кадр падения | `artifacts/*/gdb.txt` |
| Miri | UB: выход за границы, use-after-free, гонки | `artifacts/*/miri.txt` |
| Valgrind memcheck | утечки | `artifacts/*/valgrind.txt` |
| ASan / TSan | то же на настоящем железе | `artifacts/*/asan.txt`, `tsan.txt` |
| criterion 0.5 | время, доверительные интервалы, графики | `artifacts/criterion/` |
| critcmp | сравнение базовых линий | `artifacts/critcmp.txt` |
| callgrind | инструкции, детерминированно | `artifacts/*/callgrind.txt` |
| DHAT | аллокации и обращения к куче | `artifacts/*/dhat.txt` |
| perf + inferno | флеймграфы | `artifacts/*/flamegraph*.svg` |

Два workflow: [`analysis.yml`](.github/workflows/analysis.yml) — корректность,
[`bench.yml`](.github/workflows/bench.yml) — замеры.

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

Гонка не теоретическая: четыре потока по 10 000 инкрементов дали **30 488**
вместо 40 000.

Дефект 1 роняет процесс целиком — проверка предусловий `get_unchecked` даёт
non-unwinding panic. Поэтому в CI каждый тест запускается отдельным процессом,
иначе в логе видна только первая находка.

### Отладчик

[`artifacts/before/gdb.txt`](artifacts/before/gdb.txt):

```
Thread 2 "sum_even_handle" received signal SIGABRT, Aborted.
#13 core::slice::index::{impl#2}::get_unchecked::precondition_check (this=0, len=0)
#16 broken_app::sum_even (values=...) at src/lib.rs:11
#17 regression::sum_even_handles_empty_slice () at tests/regression.rs:9
```

Дефект 5 gdb показывает значением: вместо 84 из освобождённой памяти читается
`3215183`.

## Прогоны

| | До исправлений | После | После оптимизации |
|---|---|---|---|
| `cargo test` | 6 ок, 9 с ошибкой | 15 / 0 | 15 / 0 |
| Miri | UB в 10 тестах из 15 | чисто | чисто |
| Valgrind | 5 байт `definitely lost` | 0 | 0 |
| ASan | 6 ок, 9 с ошибкой | 15 / 0 | 15 / 0 |
| TSan | 6 ок, 9 с ошибкой | 14 / 1 | 15 / 0 |

Единственная единица в таблице — тест на утечку под TSan на промежуточной
стадии. Ложное срабатывание: аллокации тогда считал самописный `GlobalAlloc`, а
он видел ещё и аллокации самого санитайзера. Valgrind на том же коммите —
`definitely lost: 0`. Потом счётчик заменили на `stats_alloc`.

## Оптимизации

Мерили на исправленном коде: пока `sum_even` читает за границей среза, мерить
нечего.

**Алгоритмические.** `slow_dedup` искал дубликаты линейным поиском по
накопленному вектору и после каждой вставки сортировал его целиком —
O(n² log n). Стало: `HashSet` и одна сортировка в конце, O(n + k log k).
`slow_fib` пересчитывал одни и те же числа в двух ветках рекурсии; итеративный
проход считает каждое один раз.

**Микро.** `normalize` делал три прохода и две промежуточные строки
(`split_whitespace().collect()`, потом `to_lowercase()`). Стало: один проход в
заранее выделенный буфер, с отдельной веткой для ASCII, где регистр меняется без
юникодных таблиц. `leak_buffer` копировал вход в кучу, чтобы посчитать байты, —
копию убрали, аллокаций больше нет вообще.

## Замеры

Один прогон [`bench.yml`](.github/workflows/bench.yml): на одной машине
снимается базовая линия на старом `src/`, потом `src/` подменяется на текущий и
замер повторяется против этой линии. Бенчмарки и входы не меняются.

### Время

`cargo bench -- --baseline fixed`, [`after/criterion.txt`](artifacts/after/criterion.txt):

| Бенчмарк | До | После | Изменение, 95% ДИ | p |
|---|---|---|---|---|
| `dedup_20k` | 284,2 мс | 911,07 мкс | **−99,681%** | 0,00 |
| `fib_32` | 6,2 мс | 5,5406 нс | **−100,000%** | 0,00 |
| `normalize_700k` | 1373,7 мкс | 1,0788 мс | **−21,021%** | 0,00 |
| `sum_even_50k` | 13,7 мкс | 13,614 мкс | −0,449% | 0,52 |

`sum_even` между стадиями не менялся ни на строку — это контрольная строка.
p = 0,52 значит «разницы нет», что и должно было получиться.

То же от critcmp, [`critcmp.txt`](artifacts/critcmp.txt) — левое число говорит,
во сколько раз колонка медленнее быстрейшей в строке:

```
group             fixed                                       new
-----             -----                                       ---
dedup_20k         313.09   284.2±4.00ms                       1.00   907.7±69.08µs
fib_32            1108295.69     6.2±0.08ms                   1.00      5.6±0.17ns
normalize_700k    1.27  1373.7±63.74µs                        1.00  1084.9±57.63µs
sum_even_50k      1.00     13.7±0.60µs                        1.00     13.6±0.50µs
```

### Инструкции

Время на общем раннере плавает, счётчик инструкций — нет. `callgrind`, режим
`--bench --test`, каждый бенчмарк ровно один раз:

| | Ir |
|---|---|
| до | 3 492 735 821 |
| после | 28 543 182 |

**В 122 раза меньше**, и число повторяется от прогона к прогону.

### Память

`valgrind --tool=dhat`, [`fixed`](artifacts/fixed/dhat.txt) и
[`after`](artifacts/after/dhat.txt):

| | До | После |
|---|---|---|
| выделено | 4 055 509 Б / 895 блоков | 3 432 525 Б / 866 |
| пик | 1 759 452 Б / 137 блоков | 1 435 164 Б / 136 |
| прочитано из кучи | 4 804 672 549 Б | 7 612 237 Б |
| записано в кучу | 3 896 300 Б | 6 566 300 Б |

Чтений в **631 раз** меньше — это и есть тот линейный поиск, который на каждой
вставке перечитывал весь накопленный вектор. Записей стало больше: `HashSet`
раскладывает значения по корзинам, а сортировка почти упорядоченного вектора
только читала.

## Профиль

### callgrind

Точные инструкции по функциям,
[`fixed/callgrind.txt`](artifacts/fixed/callgrind.txt):

| Доля | Ir | Кадр |
|---|---|---|
| 28,63% | 1 000 028 970 | `ipnsort` — сортировка из `slow_dedup` |
| 22,91% | 800 040 001 | `slow_dedup`, разыменование при линейном поиске |
| 11,46% | 400 180 002 | `slow_dedup`, итератор по срезу |
| 11,45% | 400 080 022 | `slow_dedup`, `src/algo.rs` |
| 11,45% | 400 000 190 | `slow_dedup`, сравнения |
| 2,04% | 71 323 483 | `slow_fib` |

`slow_dedup` вместе с сортировкой, которую сам же и вызывает, — 86% всех
инструкций. Его и переписывали первым.

После ([`after/callgrind.txt`](artifacts/after/callgrind.txt)) наверху
`normalize` (~54% от уже в 122 раза меньшего числа) и раскладка `HashSet` по
корзинам (12,33%). `slow_dedup` из верхних строк ушёл, `slow_fib` не виден
вовсе.

### Флеймграфы

`perf` + `inferno`, режим `--bench --test`: каждый бенчмарк прогоняется по разу,
поэтому ширина кадра равна настоящей доле работы. Бинарник для профиля собран с
`-C force-frame-pointers=yes` — без них perf терял половину стеков.

| Картинка | Что видно |
|---|---|
| [до оптимизации](artifacts/fixed/flamegraph.svg) | `slow_dedup` — **94,4%** ширины, внутри него сортировка на 31,5%. Всё остальное по краям щепками |
| [после](artifacts/after/flamegraph.svg) | того плато нет: `slow_dedup` 45%, `normalize` 24%, и всё это от в 122 раза меньшего объёма работы |
| [только `fib_32`, до](artifacts/fixed/flamegraph-fib.svg) | лестница из 26 `slow_fib` друг в друге, верхняя ступень — 74,8% |

`slow_fib` пришлось выносить отдельной картинкой: в общем профиле он занимает
3,2%, и рекурсию в такой щели не разглядеть. Он честно в 45 раз дешевле
`slow_dedup` — просто оба плохие.

После оптимизации профилировать `fib` нечего: 5,5 нс на вызов, процесс стартует
дольше.

SVG открываются в браузере — там работает поиск по кадрам и клик для зума.
Рядом лежат `.png`.

## Графики criterion

Отчёт сохранён целиком:
[`artifacts/criterion/report/index.html`](artifacts/criterion/report/index.html),
около пятидесяти графиков на бенчмарк. Основные:

| Бенчмарк | Плотность | Регрессия | t-тест против базовой линии |
|---|---|---|---|
| `dedup_20k` | [pdf](artifacts/criterion/dedup_20k/report/pdf.svg) | [regression](artifacts/criterion/dedup_20k/report/regression.svg) | [t-test](artifacts/criterion/dedup_20k/report/change/t-test.svg) |
| `fib_32` | [pdf](artifacts/criterion/fib_32/report/pdf.svg) | [regression](artifacts/criterion/fib_32/report/regression.svg) | [t-test](artifacts/criterion/fib_32/report/change/t-test.svg) |
| `normalize_700k` | [pdf](artifacts/criterion/normalize_700k/report/pdf.svg) | [regression](artifacts/criterion/normalize_700k/report/regression.svg) | [t-test](artifacts/criterion/normalize_700k/report/change/t-test.svg) |
| `sum_even_50k` | [pdf](artifacts/criterion/sum_even_50k/report/pdf.svg) | [regression](artifacts/criterion/sum_even_50k/report/regression.svg) | [t-test](artifacts/criterion/sum_even_50k/report/change/t-test.svg) |

Наложение обеих выборок criterion тоже рисует (`report/both/pdf.svg`), но при
разнице в 313 раз одна кривая вырождается в линию у нуля.

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

artifacts/before/     анализ на исходном коде
artifacts/fixed/      анализ и замеры после исправлений, до оптимизации
artifacts/after/      то же после оптимизации
artifacts/criterion/  отчёт criterion целиком
```

Имена `slow_dedup` и `slow_fib` оставлены как в задании: переименование
потянуло бы за собой тесты, бенчмарки и demo, а идентификаторы бенчмарков должны
совпадать между прогонами, иначе criterion не сопоставит замеры.

Зависимости — только `criterion` и `stats_alloc`, обе dev, в бинарник не
попадают.

## Как воспроизвести

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

### Анализ

Работа велась на Windows, где Valgrind не существует, а TSan не поддерживается
для `x86_64-pc-windows-msvc`. Всё гоняется на Linux в CI — workflow принимает
коммит и имя набора логов:

```bash
gh workflow run analysis.yml -f ref=$(git rev-parse HEAD) -f stage=after
```

Локально то же самое:

```bash
cargo +nightly miri test
```

```bash
valgrind --leak-check=full ./target/debug/deps/regression-<hash>
```

### Замеры

Одна кнопка, обе стадии, одна машина:

```bash
gh workflow run bench.yml -f base=84355fb
```

Локально — три команды, на старом коде и на текущем:

```bash
cargo bench -- --save-baseline fixed
```

```bash
cargo bench -- --baseline fixed
```

```bash
critcmp fixed new
```

Аргументы бенчмарков спрятаны за `black_box`: без этого `fib(32)` сворачивался в
константу и бенчмарк мерил чтение из памяти.

## Окружение

```
rustc 1.97.1 stable            сборка, тесты, бенчмарки
nightly + miri                 динамический анализ
criterion 0.5, stats_alloc 0.1
valgrind 3.22                  memcheck, callgrind, dhat
edition 2024
цель: x86_64-unknown-linux-gnu (замеры и логи), x86_64-pc-windows-msvc (разработка)
```
