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


def bench_report():
    if not CRITERION.exists():
        sys.exit(f"нет данных criterion в {CRITERION}, сначала ./scripts/compare.sh")

    rows = []
    for bench in BENCHES:
        before, after = estimates(bench, "fixed"), estimates(bench, "new")
        change = estimates(bench, "change")
        if not (before and after):
            continue
        cell = "—"
        if change:
            point = change["mean"]["point_estimate"] * 100
            ci = change["mean"]["confidence_interval"]
            cell = (
                f"{point:+.2f}% "
                f"({ci['lower_bound'] * 100:+.2f} … {ci['upper_bound'] * 100:+.2f})"
            )
        rows.append(
            (bench, humanize(point_estimate(before)), humanize(point_estimate(after)), cell)
        )

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
        "| Бенчмарк | До оптимизации | После | Изменение среднего, 95% ДИ |",
        "|---|---|---|---|",
    ]
    out += [f"| `{n}` | {b} | {a} | {c} |" for n, b, a, c in rows]

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

    out += ["", "Собрано `python scripts/report.py bench`.", ""]
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
        out += [
            f"## {title.capitalize()} (`artifacts/{stage}/flamegraph.svg`)",
            "",
            f"Всего выборок: {total}.",
            "",
            "| Доля | Выборок | Кадр |",
            "|---|---|---|",
        ]
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
