#!/usr/bin/env bash
# Базовая линия criterion и сравнение с ней.
#
#   ./scripts/compare.sh before   # снять базовую линию до оптимизации
#   ./scripts/compare.sh after    # сравнить с ней после
set -euo pipefail
cd "$(dirname "$0")/.."

stage="${1:-after}"
mkdir -p "artifacts/$stage"

if [ "$stage" = fixed ]; then
    cargo bench --bench criterion -- --save-baseline fixed | tee "artifacts/$stage/criterion.txt"
else
    cargo bench --bench criterion -- --baseline fixed | tee "artifacts/$stage/criterion.txt"
fi

# Второй набор — про аллокации, criterion их не считает.
cargo bench --bench baseline | tee "artifacts/$stage/baseline.txt"
