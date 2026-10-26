import os
from pathlib import Path
import subprocess
import sys
import zlib

import pytest

from ai_memory_app.app import check_document_ai
from ai_memory_app.services.desktop_api import DesktopApi


def test_packaged_ai_check_is_offline(monkeypatch):
    def forbid(*args, **kwargs):
        pytest.fail('Packaging check must not access real network or credentials')

    monkeypatch.setattr('urllib.request.OpenerDirector.open', forbid)
    monkeypatch.setattr('ai_memory_app.services.credential_store.LocalCredentialStore.load', forbid)
    assert check_document_ai() == 6


def test_corrupt_module_returns_restart_guidance():
    api = DesktopApi.__new__(DesktopApi)

    def fail():
        raise zlib.error('Error -3 while decompressing data: incorrect header check')

    result = api._safe_call(fail)
    assert result['ok'] is False and result['data'] is None
    assert '儲存草稿' in result['error'] and '完全結束' in result['error']


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS build entry point')
def test_macos_build_refuses_running_target_before_changes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    executable = root / 'dist/AI Prompt Studio Next.app/Contents/MacOS/AI Prompt Studio Next'
    # Simulate process inventory; nothing is launched, rebuilt, or overwritten.
    ps = tmp_path / 'ps'
    ps.write_text('#!/bin/sh\nprintf "%s\\n" "$RUNNING_APP"\n')
    ps.chmod(0o755)
    result = subprocess.run(['/bin/bash', str(root / 'scripts/build_macos_app.sh')],
                            env={**os.environ, 'PATH': f'{tmp_path}:/usr/bin:/bin',
                                 'RUNNING_APP': str(executable)}, capture_output=True, text=True)
    assert result.returncode != 0
    assert '不可覆蓋執行中的 App' in result.stderr
    assert 'pip' not in result.stdout
