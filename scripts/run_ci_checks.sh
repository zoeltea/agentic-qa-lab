#!/usr/bin/env bash
set -e

echo "=== 🚀 RUNNING LOCAL CI QUALITY CHECKS ==="

# 1. Run full test suite
echo "[1/4] Running pytest suite..."
pytest tests/ -v

# 2. Run Verifier Demo
echo "[2/4] Running Multi-Layer Verifier Demo..."
python -m agent.verifier_demo

# 3. Run Benchmark Suite
echo "[3/4] Running Benchmark & Metrics Suite..."
python -m agent.benchmark_demo

# 4. Generate Demo Artifacts
echo "[4/4] Generating Demo Artifacts..."
python scripts/generate_artifacts.py

echo "=== ✅ ALL CI CHECKS PASSED SUCCESSFULLY! ==="
