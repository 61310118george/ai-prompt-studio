#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install pyinstaller

if [ ! -f resources/tokenizers/o200k_base.json ] || [ ! -f resources/tokenizers/cl100k_base.json ]; then
  .venv/bin/python scripts/prepare_tokenizers.py
fi

mkdir -p .pyinstaller-cache

PYINSTALLER_CONFIG_DIR=.pyinstaller-cache PYTHONPATH=src .venv/bin/pyinstaller \
  --noconfirm \
  --windowed \
  --name "AI Prompt Studio Next" \
  --osx-bundle-identifier "local.promptstudio.next" \
  --collect-all tiktoken \
  --paths src \
  --add-data "web-preview:web-preview" \
  --add-data "resources:resources" \
  run_app.py

# Finder metadata can invalidate an otherwise valid ad-hoc bundle signature.
for attribute in com.apple.FinderInfo com.apple.ResourceFork; do
  xattr -d "$attribute" "dist/AI Prompt Studio Next.app" 2>/dev/null || true
done
codesign --verify --deep --strict "dist/AI Prompt Studio Next.app"
"dist/AI Prompt Studio Next.app/Contents/MacOS/AI Prompt Studio Next" --self-test

echo "Built: $ROOT_DIR/dist/AI Prompt Studio Next.app"
