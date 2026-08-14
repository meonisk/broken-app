#!/usr/bin/env bash
set -euo pipefail

# Пример сравнения бенчмарков (до/после).
cargo bench --bench baseline > artifacts/baseline_before.txt
# После оптимизаций запустите ещё раз и сохраните в baseline_after.txt
