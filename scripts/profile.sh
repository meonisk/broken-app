#!/usr/bin/env bash
# Профиль горячего пути: perf на Linux, ETW на Windows — оболочка одна и та же.
# Нагрузка — бенчмарк baseline: demo отрабатывает за единицы миллисекунд, и
# выборок на нём не набирается.
#
#   ./scripts/profile.sh before
set -euo pipefail
cd "$(dirname "$0")/.."

stage="${1:-after}"
mkdir -p "artifacts/$stage"

cargo flamegraph --bench baseline --output "artifacts/$stage/flamegraph.svg"
