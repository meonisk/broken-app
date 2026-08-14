#!/usr/bin/env python3
"""Отчёты в markdown из того, что оставили после себя criterion и профилировщик.

    python scripts/report.py bench     -> artifacts/benchmarks.md
    python scripts/report.py profile   -> artifacts/profile.md

criterion умеет собирать HTML со своими графиками, но это 113 файлов, которые
целиком пересоздаются одной командой; в репозитории достаточно чисел.
"""

import collections
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
CRITERION = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "criterion"

BENCHES = ["sum_even_50k", "dedup_20k", "fib_32", "normalize_700k"]
STAGES = [("fixed", "до оптимизации"), ("after", "после")]


def humanize(ns):
    """Наносекунды в единицы, в которых их печатает сам criterion."""
    for limit, unit, div in ((1e3, "нс", 1), (1e6, "мкс", 1e3), (1e9, "мс", 1e6)):
        if ns < limit:
            return f"{ns / div:.4g} {unit}"
    return f"{ns / 1e9:.4g} с"


def estimates(bench, stage):
    path = CRITERION / bench / stage / "estimates.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def point_estimate(est):
    """Там, где criterion считает наклон, он же и печатает его в своей строке."""
    return (est.get("slope") or est["mean"])["point_estimate"]


# Графики criterion, которые стоит держать в репозитории. Наложение обеих
# выборок (`both/pdf.svg`) не берём: при разнице в сотни раз одна из кривых
# вырождается в линию у нуля, и картинка пустая.
PLOTS = [
    ("pdf.svg", "pdf.svg", "Плотность времени одной итерации после оптимизации: закрашенная область — распределение, вертикальные линии — среднее и границы выбросов."),
    ("regression.svg", "regression.svg", "Суммарное время против числа итераций. Точки должны ложиться на прямую — если нет, замер шумит."),
    ("change/t-test.svg", "t-test.svg", "t-тест против базовой линии: отметка далеко за закрашенной областью означает, что разница не случайна."),
]


def svg_summary(rows, path):
    """Своя сводка: у criterion такой картинки нет, а разница в сотни раз без
    логарифмической шкалы на одну ось не ложится."""
    import math

    values = [v for _, _, b, a in rows for v in (b, a)]
    lo, hi = math.log10(min(values)), math.log10(max(values))
    left, width, row_h = 150, 520, 56
    height = 60 + row_h * len(rows)

    def x_of(ns):
        return left + width * (math.log10(ns) - lo) / (hi - lo)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{left + width + 90}" height="{height}" font-family="sans-serif" font-size="12">',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="12" y="24" font-size="14" fill="#222">Время одной итерации, логарифмическая шкала</text>',
    ]
    for i, (name, _, before, after) in enumerate(rows):
        y = 50 + i * row_h
        out.append(f'<text x="12" y="{y + 16}" fill="#222">{name}</text>')
        for offset, value, color in ((0, before, "#b0413e"), (18, after, "#2f6f9f")):
            out.append(
                f'<rect x="{left}" y="{y + offset}" width="{max(x_of(value) - left, 1):.1f}" '
                f'height="14" fill="{color}"/>'
            )
            out.append(
                f'<text x="{x_of(value) + 6:.1f}" y="{y + offset + 11}" fill="#444">{humanize(value)}</text>'
            )
    out.append(
        f'<rect x="12" y="{height - 22}" width="10" height="10" fill="#b0413e"/>'
        f'<text x="28" y="{height - 13}" fill="#444">до оптимизации</text>'
        f'<rect x="140" y="{height - 22}" width="10" height="10" fill="#2f6f9f"/>'
        f'<text x="156" y="{height - 13}" fill="#444">после</text>'
    )
    out.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def copy_plots(bench):
    """Копирует графики бенчмарка в artifacts/plots и возвращает то, что нашлось."""
    found = []
    for source, name, caption in PLOTS:
        src = CRITERION / bench / "report" / source
        if not src.exists():
            continue
        dst = ARTIFACTS / "plots" / bench / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        found.append((f"plots/{bench}/{name}", caption))
    return found


def change_cell(change):
    if not change:
        return "—"
    ci = change["mean"]["confidence_interval"]
    return (
        f"{change['mean']['point_estimate'] * 100:+.2f}% "
        f"({ci['lower_bound'] * 100:+.2f} … {ci['upper_bound'] * 100:+.2f})"
    )


def bench_report():
    if not CRITERION.exists():
        sys.exit(f"нет данных criterion в {CRITERION}, сначала ./scripts/compare.sh")

    rows, raw, sections = [], [], []
    for bench in BENCHES:
        before, after = estimates(bench, "fixed"), estimates(bench, "new")
        change = estimates(bench, "change")
        if not (before and after):
            continue
        cell = change_cell(change)
        rows.append(
            (bench, humanize(point_estimate(before)), humanize(point_estimate(after)), cell)
        )
        raw.append((bench, cell, point_estimate(before), point_estimate(after)))
        sections += [
            f"## `{bench}`",
            "",
            "| До оптимизации | После | Изменение среднего, 95% ДИ |",
            "|---|---|---|",
            f"| {humanize(point_estimate(before))} | {humanize(point_estimate(after))} | {cell} |",
            "",
        ]
        for path, caption in copy_plots(bench):
            sections += [f"![{bench}]({path})", "", f"*{caption}*", ""]

    allocs = collections.defaultdict(dict)
    for stage, _ in STAGES:
        log = ARTIFACTS / stage / "baseline.txt"
        if not log.exists():
            continue
        for name, count in re.findall(r"^(.+?): .+?, аллокаций (\d+)$", log.read_text(encoding="utf-8"), re.M):
            allocs[name][stage] = count

    out = [
        "# Бенчмарки",
        "",
        "Замеры criterion на одних и тех же входах: `fixed` — код исправлен, но ещё",
        "не оптимизирован, `after` — после оптимизации. Имена бенчмарков между",
        "прогонами не менялись, иначе criterion не сопоставил бы замеры.",
        "",
        "## Сводка",
        "",
        "![сводка](plots/summary.svg)",
        "",
        "| Бенчмарк | До оптимизации | После | Изменение среднего, 95% ДИ |",
        "|---|---|---|---|",
    ]
    out += [f"| [`{n}`](#{n}) | {b} | {a} | {c} |" for n, b, a, c in rows]

    if allocs:
        out += [
            "",
            "## Аллокации на вызов",
            "",
            "Считает свой `GlobalAlloc` в `benches/baseline.rs` — criterion такого не меряет.",
            "",
            "| Нагрузка | До | После |",
            "|---|---|---|",
        ]
        out += [
            f"| {name} | {v.get('fixed', '—')} | {v.get('after', '—')} |"
            for name, v in allocs.items()
        ]

    svg_summary(raw, ARTIFACTS / "plots" / "summary.svg")
    out += ["", "# По бенчмаркам", ""] + sections
    out += ["Собрано `python scripts/report.py bench`: числа из json-данных criterion,",
            "графики — его же, скопированы в `artifacts/plots/`.", ""]
    write(ARTIFACTS / "benchmarks.md", out)


# Кадры рантайма и обёртки бенчмарка: они есть в любом профиле и ничего не говорят.
SKIP = (
    "lang_start", "catch_unwind", "call_once", "invoke_main", "__scrt",
    "begin_short_backtrace", "baseline::main", "BaseThreadInitThunk",
    "RtlUserThreadStart", "mainCRTStartup",
)
SKIP_EXACT = {"all", "nan", "main", "baseline::time_it", "baseline::measure"}


def top_frames(svg_path, limit=10):
    svg = svg_path.read_text(encoding="utf-8")
    rows = re.findall(r"<title>(.*?) \((\d+) samples, ([\d.]+)%\)</title>", svg)
    total = max(int(s) for _, s, _ in rows)
    agg = collections.defaultdict(int)
    for name, samples, _ in rows:
        name = re.sub(r"\(.*$", "", re.sub(r"^[^`]*`", "", html.unescape(name))).strip()
        if not name or name in SKIP_EXACT or name.startswith("0x"):
            continue
        if any(marker in name for marker in SKIP):
            continue
        agg[name] = max(agg[name], int(samples))
    return total, sorted(agg.items(), key=lambda kv: -kv[1])[:limit]


def profile_report():
    out = [
        "# Профиль",
        "",
        "Нагрузка — `benches/baseline.rs`: `demo` отрабатывает за единицы миллисекунд,",
        "и выборок на нём не набирается. Доли считаются от всех выборок прогона.",
        "",
    ]
    for stage, title in STAGES:
        svg = ARTIFACTS / stage / "flamegraph.svg"
        if not svg.exists():
            continue
        total, frames = top_frames(svg)
        out += [f"## {title.capitalize()}", "", f"Всего выборок: {total}.", ""]
        if (ARTIFACTS / stage / "flamegraph.png").exists():
            out += [
                f"[![флеймграф]({stage}/flamegraph.png)]({stage}/flamegraph.svg)",
                "",
                f"*Картинка кликается — рядом лежит `{stage}/flamegraph.svg`, в нём работает поиск по кадрам.*",
                "",
            ]
        out += ["| Доля | Выборок | Кадр |", "|---|---|---|"]
        out += [f"| {100 * s / total:.2f}% | {s} | `{n}` |" for n, s in frames]
        out.append("")
    out += ["Собрано `python scripts/report.py profile`.", ""]
    write(ARTIFACTS / "profile.md", out)


def write(path, lines):
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"записан {path.relative_to(ROOT)}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "bench":
        bench_report()
    elif command == "profile":
        profile_report()
    else:
        sys.exit("укажите bench или profile")
