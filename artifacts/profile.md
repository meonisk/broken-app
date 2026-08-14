# Профиль

Нагрузка — `benches/baseline.rs`: `demo` отрабатывает за единицы миллисекунд,
и выборок на нём не набирается. Доли считаются от всех выборок прогона.

## До оптимизации

Всего выборок: 800.

[![флеймграф](fixed/flamegraph.png)](fixed/flamegraph.svg)

*Картинка кликается — рядом лежит `fixed/flamegraph.svg`, в нём работает поиск по кадрам.*

| Доля | Выборок | Кадр |
|---|---|---|
| 57.62% | 461 | `broken_app::algo::slow_dedup` |
| 28.38% | 227 | `broken_app::algo::slow_fib` |
| 24.25% | 194 | `core::slice::iter::impl$171::next` |
| 24.25% | 194 | `core::ptr::non_null::impl$15::eq` |
| 23.12% | 185 | `alloc::vec::impl$10::deref_mut` |
| 23.12% | 185 | `core::slice::sort::unstable::sort` |
| 23.12% | 185 | `core::slice::sort::unstable::ipnsort<u64,bool` |
| 23.00% | 184 | `core::slice::sort::shared::find_existing_run` |
| 10.88% | 87 | `core::ops::function::FnMut::call_mut` |
| 10.88% | 87 | `core::cmp::impls::impl$66::lt` |

## После

Всего выборок: 204.

[![флеймграф](after/flamegraph.png)](after/flamegraph.svg)

*Картинка кликается — рядом лежит `after/flamegraph.svg`, в нём работает поиск по кадрам.*

| Доля | Выборок | Кадр |
|---|---|---|
| 40.69% | 83 | `broken_app::normalize` |
| 26.96% | 55 | `alloc::string::String::push` |
| 24.02% | 49 | `broken_app::algo::slow_dedup` |
| 13.73% | 28 | `core::iter::adapters::copied::impl$1::fold` |
| 13.73% | 28 | `core::slice::iter::impl$171::fold` |
| 13.73% | 28 | `core::iter::traits::iterator::Iterator::collect` |
| 13.73% | 28 | `std::collections::hash::set::impl$9::from_iter` |
| 13.73% | 28 | `std::collections::hash::set::impl$11::extend` |
| 13.73% | 28 | `hashbrown::set::impl$10::extend` |
| 13.73% | 28 | `hashbrown::map::impl$82::extend` |

Собрано `python scripts/report.py profile`.
