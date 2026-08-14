#!/usr/bin/env bash
set -euo pipefail

# Пример профилирования (Linux, perf). Настройте под свою систему.
cargo build --release
perf record -g ./target/release/demo || true
perf report
