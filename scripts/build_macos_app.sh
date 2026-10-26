#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
RELEASE_VERSION="V1.0"

# A running PyInstaller process retains offsets into the original executable.
# Replacing it makes later lazy imports read unrelated compressed bytes.
assert_app_closed() {
  local processes executable
  processes="$(ps -axo comm=)" || { echo "無法確認 App 是否已關閉，停止打包。" >&2; return 1; }
  while IFS= read -r executable; do
    case "$executable" in
      "$ROOT_DIR/dist/AI Prompt Studio Next.app/Contents/MacOS/AI Prompt Studio Next"|"$ROOT_DIR/dist/AI Prompt Studio Next/AI Prompt Studio Next")
        echo "請先儲存內容並完全結束 AI Prompt Studio Next，再重新打包；不可覆蓋執行中的 App。" >&2
        return 1 ;;
    esac
  done <<< "$processes"
}
assert_app_closed

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install pyinstaller

if [ ! -f resources/tokenizers/o200k_base.json ] || [ ! -f resources/tokenizers/cl100k_base.json ]; then
  .venv/bin/python scripts/prepare_tokenizers.py
fi

mkdir -p .pyinstaller-cache

# Some managed Python runtimes load an extra CA policy file beside ssl.py.
SSL_POLICY="$(.venv/bin/python -c 'import ssl; from pathlib import Path; print(Path(ssl.__file__).with_name("codex-rejected-cas.pem"))')"
SSL_DATA=()
if [ -f "$SSL_POLICY" ]; then
  SSL_DATA+=(--add-data "$SSL_POLICY:.")
fi

assert_app_closed
PYINSTALLER_CONFIG_DIR=.pyinstaller-cache PYTHONPATH=src .venv/bin/pyinstaller \
  --noconfirm \
  --windowed \
  --name "AI Prompt Studio Next" \
  --osx-bundle-identifier "local.promptstudio.next" \
  --collect-all tiktoken \
  --collect-all keyring \
  --paths src \
  --add-data "web-ui:web-ui" \
  --add-data "resources:resources" \
  "${SSL_DATA[@]}" \
  run_app.py

# Sign outside file-provider folders, which can reattach Finder metadata.
STAGING_DIR="$(mktemp -d /private/tmp/prompt-studio-sign.XXXXXX)"
trap 'rm -rf "$STAGING_DIR"' EXIT
STAGED_APP="$STAGING_DIR/AI Prompt Studio Next.app"
ditto --norsrc --noextattr "dist/AI Prompt Studio Next.app" "$STAGED_APP"
xattr -cr "$STAGED_APP"
codesign --force --deep --sign - "$STAGED_APP"
codesign --verify --deep --strict "$STAGED_APP"
"$STAGED_APP/Contents/MacOS/AI Prompt Studio Next" --self-test
assert_app_closed
ditto --norsrc --noextattr "$STAGED_APP" "dist/AI Prompt Studio Next.app"

mkdir -p release
ditto -c -k --sequesterRsrc --keepParent \
  "$STAGED_APP" \
  "release/AI Prompt Studio Next ${RELEASE_VERSION} macOS Apple Silicon.zip"

echo "Built: $ROOT_DIR/dist/AI Prompt Studio Next.app"
echo "Packaged: $ROOT_DIR/release/AI Prompt Studio Next ${RELEASE_VERSION} macOS Apple Silicon.zip"
