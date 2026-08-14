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
| 6 | `slow_dedup` | линейный поиск и сортировка на каждой вставке, O(n² log n) | бенчмарк: 235 мс, профиль | `dedup_returns_sorted_unique_values` + бенчмарк |
| 7 | `slow_fib` | экспоненциальная рекурсия | бенчмарк: 6,6 мс, профиль | `fib_matches_known_values` + бенчмарк |
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

Мерили после исправлений, на корректном коде: пока `sum_even` читает за границей
среза, мерить нечего. Кого переписывать, видно уже из первых замеров — 235 мс и
6,6 мс против 17 мкс у соседей; профиль подтвердил, что это время действительно
внутри наших функций, а не в обвязке.

| Бенчмарк | До | После | Изменение |
|---|---|---|---|
| `dedup_20k` | 235,03 мс | 967,71 мкс | **243×** |
| `fib_32` | 6,6314 мс | 8,1972 нс | **~800 000×** |
| `normalize_700k` | 1,4530 мс | 1,2635 мс | −13,9% |
| `sum_even_50k` | 17,595 мкс | 16,654 мкс | код не менялся, это разброс |

Куча по данным DHAT (`valgrind --tool=dhat`, тот же бенчмарк в режиме
`--bench --test`):

| Показатель | До | После |
|---|---|---|
| всего выделено | 4 055 575 байт в 895 блоках | 3 432 591 байт в 866 блоках |
| прочитано из кучи | 4 804 672 945 байт | 7 612 041 байт |

Чтений из кучи стало в 631 раз меньше — это линейный поиск в `slow_dedup`,
который на каждой вставке перечитывал весь накопленный вектор.

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

После оптимизации `slow_fib` из профиля исчез совсем — восемь наносекунд на
вызов не попадают в картинку, — а `slow_dedup` опустился с 17,0% до 13,1%.
Подробности и оговорку про то, как читать эти проценты, см. в
[`artifacts/profile.md`](artifacts/profile.md).

## Чем всё измерено

Своего инструментария в репозитории нет — ни генераторов отчётов, ни самописных
счётчиков (единственное исключение оговорено ниже). Числа и картинки — вывод
готовых программ, отчёты в markdown написаны по этому выводу руками.

| Инструмент | Что делает | Где результат |
|---|---|---|
| criterion 0.5 | замеры, доверительные интервалы, все графики | `artifacts/criterion/` |
| critcmp | сравнение базовых линий и их выгрузка в json | `artifacts/critcmp.txt`, `baseline-*.json` |
| cargo-flamegraph | профиль, флеймграф | `artifacts/*/flamegraph.svg` |
| Valgrind DHAT | аллокации | `artifacts/*/dhat.txt`, `dhat.json` |
| Miri, Valgrind, ASan, TSan | поиск UB, утечек и гонок | `artifacts/*/` |

```bash
cargo install critcmp flamegraph
```

## Структура

```
src/lib.rs            sum_even, leak_buffer, normalize, average_positive, use_after_free
src/algo.rs           slow_dedup, slow_fib
src/concurrency.rs    race_increment, read_after_sleep, reset_counter
src/bin/demo.rs       демонстрация, вывод совпадает с эталоном

tests/integration.rs  исходные тесты из задания
tests/regression.rs   по тесту на каждый дефект
tests/leak.rs         утечка: аллокации считает GlobalAlloc-обёртка

benches/criterion.rs  criterion, фиксированные входы и имена

artifacts/before/     анализ на исходном коде
artifacts/fixed/      анализ, профиль и базовая линия после исправлений
artifacts/after/      то же после оптимизации
artifacts/criterion/  отчёт criterion целиком, как он его собрал
artifacts/critcmp.txt сравнение базовых линий
artifacts/benchmarks.md  замеры, аллокации и графики
artifacts/profile.md     флеймграфы до и после
```

В каждом каталоге `artifacts/` лежат логи `cargo test`, Miri, Valgrind, ASan и
TSan, а в `fixed/` и `after/` — ещё `criterion.txt`, вывод DHAT и профиль:
`flamegraph.svg` (интерактивный, с поиском) и `flamegraph.png` (тот же кадр
картинкой).

Отчёт criterion со всеми графиками лежит целиком, как он его собрал:
[`artifacts/criterion/report/index.html`](artifacts/criterion/report/index.html).
Ключевые графики вынесены в [`artifacts/benchmarks.md`](artifacts/benchmarks.md),
чтобы читались прямо на GitHub.

Единственное место, где инструментирование пришлось написать самому, —
`tests/leak.rs`: это регрессионный тест на утечку, а тест по заданию положено
писать. Ту же утечку независимо ловят Valgrind и DHAT в CI.

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

Базовая линия снимается на коде до оптимизации:

```bash
cargo bench -- --save-baseline fixed
```

Потом, уже на оптимизированном коде, — сравнение с ней:

```bash
cargo bench -- --baseline fixed
```

```bash
critcmp fixed new
```

Профиль снимается с того же бенчмарка в режиме criterion `--profile-time`: он
гоняет каждый бенчмарк заданное время без анализа, специально для профилировщика.

```bash
cargo flamegraph --bench criterion --output artifacts/after/flamegraph.svg -- --bench --profile-time 5
```

Замеры делались локально, а не в CI: на общих раннерах время плавает слишком
сильно, чтобы сравнивать проценты.

## Окружение

```
rustc 1.97.1 (stable)          сборка, тесты, бенчмарки
nightly + miri                 динамический анализ
criterion 0.5
edition 2024
цель: x86_64-pc-windows-msvc (локально), x86_64-unknown-linux-gnu (CI)
```
