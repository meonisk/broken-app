# broken-app — поиск ошибок и оптимизация

[![CI](https://github.com/meonisk/broken-app/actions/workflows/ci.yml/badge.svg)](https://github.com/meonisk/broken-app/actions/workflows/ci.yml)

> Текст этого README написан Claude (Anthropic, модель Opus 5).

Проектная работа модуля 5. В исходном коде посажены дефекты — от undefined
behavior до квадратичных алгоритмов. Их надо найти динамическим анализом,
исправить, закрыть тестами, спрофилировать горячий путь и оптимизировать,
подтвердив результат замерами на одинаковых входах.

Эталон поведения — <https://github.com/meonisk/reference-app>, неизменённый
исходник из задания. Он не копировался сюда и не подключён зависимостью:
по нему сверялось ожидаемое поведение, а результат зафиксирован тестами.
Вывод `cargo run --bin demo` в обоих проектах совпадает построчно.

## Что нашлось

| # | Где | Что не так | Чем найдено | Тест |
|---|-----|-----------|-------------|------|
| 1 | `sum_even` | `get_unchecked(idx)` в цикле `0..=len` — чтение за границей среза | Miri, ASan, проверка предусловий в debug | `sum_even_handles_empty_slice`, `sum_even_sums_only_even_values` |
| 2 | `leak_buffer` | `Box::into_raw` без парного `from_raw` — утечка на каждый вызов | Valgrind (`5 bytes definitely lost`), ASan, Miri | `tests/leak.rs` |
| 3 | `normalize` | удалялся только пробел U+0020, табуляции и переводы строк оставались | `cargo test` | `normalize_removes_all_whitespace` |
| 4 | `average_positive` | сумма положительных делилась на длину всего среза | `cargo test` | `average_positive_ignores_non_positive` |
| 5 | `use_after_free` | разыменование указателя после `drop` | Miri, ASan (`heap-use-after-free`) | `use_after_free_returns_the_boxed_value` |
| 6 | `slow_dedup` | линейный поиск и сортировка на каждой вставке, O(n² log n) | профиль: 57,6% выборок | `dedup_returns_sorted_unique_values` + бенчмарк |
| 7 | `slow_fib` | экспоненциальная рекурсия | профиль: 28,4% выборок | `fib_matches_known_values` + бенчмарк |
| 8 | `race_increment` | `static mut` без синхронизации — гонка данных | Miri, TSan | `counter_keeps_every_increment_and_is_visible_after_join` |
| 9 | `read_after_sleep` | `sleep` вместо синхронизации, чтение того же `static mut` | Miri, TSan | тот же тест |

Гонка не теоретическая: четыре потока по 10 000 инкрементов давали **31 199**
вместо 40 000 — терялась четверть записей.

Дефект 1 стоит отдельного слова. В debug он ловится проверкой предусловий
`get_unchecked` и роняет процесс целиком (`non-unwinding panic`), поэтому и
`cargo test`, и Miri, и санитайзеры в CI запускают **каждый тест отдельным
процессом** — иначе в логе была бы видна только первая находка.

## Состояние до и после

| Прогон | До исправлений | После исправлений | После оптимизации |
|---|---|---|---|
| `cargo test` | 6 ок, 9 с ошибкой | 15 / 0 | 15 / 0 |
| Miri | 10 тестов из 15 с UB | чисто | чисто |
| Valgrind | 5 байт `definitely lost` | 0 | 0 |
| ASan | 5 ок, 10 с ошибкой | 15 / 0 | 15 / 0 |
| TSan | 6 ок, 9 с ошибкой | 15 / 0 | 15 / 0 |

Valgrind в чистых прогонах показывает 48 байт `possibly lost` — это
`std::thread::current::init_current`, структура потока из стандартной
библиотеки, живущая до конца процесса и доступная только через TLS. К коду
проекта отношения не имеет, `definitely lost` везде ноль.

## Оптимизации

Профиль снимался после исправлений, на корректном коде: пока `sum_even` читает
за границей среза, мерить нечего. Два кадра занимали 86% выборок — их и
переписывали.

| Бенчмарк | До | После | Изменение |
|---|---|---|---|
| `dedup_20k` | 235,03 мс | 967,71 мкс | **243×** |
| `fib_32` | 6,6314 мс | 8,1972 нс | **~800 000×** |
| `normalize_700k` | 1,4530 мс | 1,2635 мс | −13,9% |
| `sum_even_50k` | 17,595 мкс | 16,654 мкс | код не менялся, это разброс |

Аллокации на вызов (`benches/baseline.rs`, свой счётчик в `GlobalAlloc`):

| Функция | До | После |
|---|---|---|
| `slow_dedup` 20k | 14 | 2 |
| `normalize` 700k | 18 | 1 |

**Алгоритмические.** `slow_dedup` собирал уникальные значения линейным поиском
по накопленному вектору и после каждой вставки сортировал его целиком —
O(n² log n). Теперь это `HashSet` и одна сортировка в конце, O(n + k log k).
`slow_fib` пересчитывал одни и те же числа в двух ветках рекурсии; итеративный
проход считает каждое один раз.

**Микро.** `normalize` делал три прохода и две промежуточные строки
(`split_whitespace().collect()`, затем `to_lowercase()`); стало — один проход в
заранее выделенный буфер, с отдельной веткой для ASCII, где регистр меняется
без разбора юникодных таблиц. `leak_buffer` копировал вход в кучу, чтобы просто
посчитать байты, — копия убрана, функция больше не аллоцирует вовсе.

После оптимизации профиль перестроился: `slow_dedup` опустился с 57,6% до
24,0%, `slow_fib` из верхних кадров исчез, а главным стал `normalize` (40,7%),
хотя в абсолютном времени он тоже быстрее. Выборок во втором профиле вчетверо
меньше — та же нагрузка отрабатывает заметно быстрее.

## Структура

```
src/lib.rs            sum_even, leak_buffer, normalize, average_positive, use_after_free
src/algo.rs           slow_dedup, slow_fib
src/concurrency.rs    race_increment, read_after_sleep, reset_counter
src/bin/demo.rs       демонстрация, вывод совпадает с эталоном

tests/integration.rs  исходные тесты из задания
tests/regression.rs   по тесту на каждый дефект
tests/leak.rs         утечка: считает аллокации своим GlobalAlloc

benches/criterion.rs  criterion, фиксированные входы и имена
benches/baseline.rs   время и число аллокаций на вызов

scripts/report.py     сводит логи criterion и профиля в markdown

artifacts/before/     анализ на исходном коде
artifacts/fixed/      анализ, профиль и базовая линия после исправлений
artifacts/after/      то же после оптимизации
artifacts/benchmarks.md  сводка замеров и аллокаций
artifacts/profile.md     верхние кадры профиля до и после
```

В каждом каталоге `artifacts/` лежат логи `cargo test`, Miri, Valgrind, ASan и
TSan, а в `fixed/` и `after/` — ещё `criterion.txt`, `baseline.txt` и профиль:
`flamegraph.svg` (интерактивный, с поиском) и `flamegraph.png` (тот же кадр
картинкой).

Готовые выводы собраны в двух отчётах: [`artifacts/benchmarks.md`](artifacts/benchmarks.md)
— сводный график, время и число аллокаций до и после, доверительные интервалы и
по три графика criterion на каждый бенчмарк, и
[`artifacts/profile.md`](artifacts/profile.md) — оба флеймграфа с таблицами
верхних кадров. Генерируются `scripts/report.py` (нужен Python 3) из
json-данных criterion и самих svg, картинки складываются в `artifacts/plots/`.

Наложение обеих выборок на один график criterion рисует, но при разнице в
240 раз одна кривая вырождается в линию у нуля — вместо него в сводке своя
диаграмма в логарифмической шкале. Полный HTML-отчёт criterion со всеми
пятьюдесятью графиками на бенчмарк никуда не делся, он просто не хранится в
git: `$CARGO_TARGET_DIR/criterion/report/index.html`.

Имена `slow_dedup` и `slow_fib` оставлены как в задании: переименование
потянуло бы за собой тесты, бенчмарки и demo, а идентификаторы бенчмарков
должны совпадать между прогонами, иначе criterion не сопоставит замеры.

## Как воспроизвести

```bash
cargo build --workspace
```

```bash
cargo test
```

Ожидается 15 тестов: 6 исходных, 8 регрессионных и 1 на утечку.

```bash
cargo run --bin demo
```

### Динамический анализ

Miri, Valgrind, ASan и TSan гоняются на Linux в GitHub Actions — workflow
[`analysis.yml`](.github/workflows/analysis.yml) запускается вручную и
принимает коммит и имя набора логов:

```bash
gh workflow run analysis.yml -f ref=$(git rev-parse HEAD) -f stage=after
```

Работа велась на Windows, где Valgrind не существует, а TSan не поддерживается
для `x86_64-pc-windows-msvc`. Ставить WSL ради двух инструментов смысла было
меньше, чем прогонять их на настоящем Linux в CI: там же ставится nightly с
Miri, и логи выкладываются артефактом прогона. Локально то же самое можно
запустить руками:

```bash
cargo +nightly miri test
```

```bash
valgrind --leak-check=full ./target/debug/deps/regression-<hash>
```

Отладчиком (`rust-gdb`, на Windows — отладчик Visual Studio) удобно смотреть
дефекты 1 и 5: сборка bench-профиля собирается с `debug = true`, так что
символы на месте.

### Бенчмарки и профиль

Входы фиксированы, имена бенчмарков не меняются — «до» и «после» считаются на
одних данных, иначе сравнение базовых линий бессмысленно. Аргументы спрятаны за
`black_box`: без этого `fib(32)` сворачивался компилятором в константу и
бенчмарк мерил чтение из памяти.

```bash
./scripts/compare.sh fixed
```

```bash
./scripts/compare.sh after
```

```bash
./scripts/profile.sh after
```

Профилируется бенчмарк `baseline`, а не `demo`: demo отрабатывает за единицы
миллисекунд, выборок на нём не набирается. Замеры делались локально, а не в CI:
на общих раннерах время плавает слишком сильно, чтобы сравнивать проценты.

## Окружение

```
rustc 1.97.1 (stable)          сборка, тесты, бенчмарки
nightly + miri                 динамический анализ
criterion 0.5
edition 2024
цель: x86_64-pc-windows-msvc (локально), x86_64-unknown-linux-gnu (CI)
```
