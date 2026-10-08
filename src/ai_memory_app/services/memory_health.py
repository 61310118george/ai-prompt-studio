from __future__ import annotations

import re
import hashlib
from collections import defaultdict
from pathlib import Path

from .agent_catalog import get_agent
from .project_scanner import classify_markdown, scan_project


SECRET_PATTERNS = [
    ("OpenAI API Key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("私密金鑰", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("密碼欄位", re.compile(r"(?i)(?:password|passwd|密碼)\s*[:=]\s*\S+")),
    ("存取憑證", re.compile(r'(?i)(?:api[_ -]?key|access[_ -]?token|secret)\s*[=:]\s*["\x27]?[A-Za-z0-9_/-]{12,}')),
]

# Indicators for review, not a semantic security guarantee. See OWASP source in docs.
ATTACK_PATTERNS = [
    ("指令覆寫", re.compile(r'(?i)(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|rules)|忽略.{0,8}(?:之前|先前|所有|系統).{0,5}(?:指令|規則)')),
    ("索取內部提示詞", re.compile(r'(?i)(?:reveal|print|show|leak).{0,35}(?:system prompt|hidden instructions)|(?:洩漏|顯示|輸出).{0,12}(?:系統提示詞|隱藏指令)')),
    ("繞過安全限制", re.compile(r'(?i)(?:bypass|disable).{0,20}(?:safety|security|guardrail)|(?:繞過|停用|無視).{0,8}(?:安全|權限|限制)')),
    ("敏感資料外傳", re.compile(r'(?i)(?:send|upload|exfiltrate).{0,60}(?:password|secret|token|credentials)|(?:上傳|傳送|外傳).{0,30}(?:密碼|金鑰|憑證)|https?://\S+[?&](?:token|password|secret|data)=')),
    ("遠端指令執行", re.compile(r'(?i)curl\s+.{0,160}\|\s*(?:bash|sh)|wget\s+.{0,160}\|\s*(?:bash|sh)|rm\s+-rf\s+(?:/|~|\$HOME)')),
    ("隱藏文字", re.compile('[\u200b-\u200d\u202a-\u202e\u2066-\u2069]')),
]


def _issue(level: str, code: str, title: str, detail: str, path: str = "") -> dict:
    return {"level": level, "code": code, "title": title, "detail": detail, "path": path}


def _effective_files(project: Path, agent_id: str, working_directory: Path | None = None) -> list[dict]:
    working = (working_directory or project).resolve()
    paths: list[dict] = []
    agent = get_agent(agent_id)
    candidates: list[Path] = []
    if agent_id in {"codex", "claude", "gemini"}:
        current = project.resolve()
        target = working if working.is_relative_to(current) else current
        while True:
            candidates.append(current)
            if current == target:
                break
            relative_parts = target.relative_to(current).parts
            if not relative_parts:
                break
            current = current / relative_parts[0]
    else:
        candidates = [project.resolve()]

    for directory in candidates:
        for file_type in agent["files"]:
            candidate = directory / file_type["path"]
            if candidate.exists() and candidate.is_file() and candidate.resolve().is_relative_to(project.resolve()):
                paths.append(
                    {
                        "relative_path": candidate.relative_to(project).as_posix(),
                        "purpose": file_type["purpose"],
                        "scope": "working-directory" if directory == working else "project",
                    }
                )
    if agent_id == "claude":
        rules_dir = project / ".claude" / "rules"
        if rules_dir.exists():
            for rule in sorted(rules_dir.glob("*.md")):
                paths.append({"relative_path": rule.relative_to(project).as_posix(), "purpose": "Claude 模組化規則", "scope": "rule"})
    return paths


def run_memory_health_check(project_path: Path, agent_id: str, working_directory: Path | None = None) -> dict:
    scan = scan_project(project_path)
    agent = get_agent(agent_id)
    issues: list[dict] = []
    all_rules = defaultdict(list)
    fingerprints = defaultdict(list)
    total_chars = 0
    def add(info, level, code, title, detail, line=None, end_line=None):
        issues.append({**_issue(level, code, title, detail, info['relative_path']),
                       'line': line, 'end_line': end_line or line,
                       'group': info['group'], 'modified_at': info['modified_at']})

    for file_info in scan["files"]:
        path = project_path / file_info["relative_path"]
        if file_info['size'] > 2_000_000:
            add(file_info, 'warning', 'scan_skipped', '檔案過大，未檢查內容', '超過 2 MB；請拆分後重新掃描。')
            continue
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(project_path.resolve()):
                raise OSError('path changed')
            content = path.read_bytes().decode('utf-8')
        except (UnicodeDecodeError, OSError):
            add(file_info, 'warning', 'scan_skipped', '無法檢查此檔案', '檔案無法讀取、位置變更或不是 UTF-8。')
            continue
        total_chars += len(content)
        lines = content.splitlines()
        if path.name == 'AGENT.md':
            add(file_info, 'error', 'wrong_filename', '可能使用了錯誤檔名 AGENT.md', '共同指令檔名通常是 AGENTS.md。')
        if len(content) > 24_000:
            add(file_info, 'warning', 'large_file', '文件偏長，建議檢查是否需要全部載入', f'{len(content):,} 字元；24,000 為本 App 提醒門檻，並非平台限制。', 1, len(lines))
        if not content.strip():
            add(file_info, 'info', 'empty_file', '空白文件', '確認是否為待填範本；由你決定是否保留。')
        else:
            fingerprints[hashlib.sha256(content.encode()).hexdigest()].append(file_info)
        fenced = False
        for number, line in enumerate(lines, 1):
            for title, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    add(file_info, 'error', 'possible_secret', f'疑似{title}', '可能是示範值；請人工確認。檢查報告不複製敏感值。', number)
            for title, pattern in ATTACK_PATTERNS:
                if pattern.search(line):
                    add(file_info, 'warning', 'prompt_injection', f'疑似{title}', '此為攻擊指標，也可能是引用或安全教材；請確認來源與用途，勿直接執行。', number)
            if re.match(r'^\s*(```|~~~)', line):
                fenced = not fenced
            normalized = re.sub(r'^\s*[-*+]\s*', '', line).strip().lower()
            if not fenced and len(normalized) >= 12 and not normalized.startswith(('#', '<!--')):
                all_rules[normalized].append((file_info, number))
            if re.fullmatch(r'\s*(?:TODO|TBD|待補|待填)\s*[:：]?\s*', line, re.I):
                add(file_info, 'info', 'placeholder', '尚未補完的內容', '請填寫具體要求或確認是否可以移除。', number)
        # Catch instruction overrides split across a line break without copying text into reports.
        for title, pattern in ATTACK_PATTERNS[:3]:
            for match in pattern.finditer(content):
                number = content.count('\n', 0, match.start()) + 1
                end = content.count('\n', 0, match.end()) + 1
                if end != number:
                    add(file_info, 'warning', 'prompt_injection', f'疑似{title}', '跨行攻擊指標，請人工確認。', number, end)

    for occurrences in all_rules.values():
        if len(occurrences) > 1:
            for info, number in occurrences:
                add(info, 'info', 'duplicate_rule', '重複段落／規則', '同一文字出現多次，可能是必要共用內容；請人工確認。', number)
    for files in fingerprints.values():
        if len(files) > 1:
            for info in files:
                add(info, 'info', 'duplicate_file', '內容完全相同的文件', '另見：' + '、'.join(f['relative_path'] for f in files if f != info))

    effective = _effective_files(project_path, agent_id, working_directory)
    return {
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "issues": issues,
        "files": [{**info, 'issues': [issue for issue in issues if issue['path'] == info['relative_path']]} for info in scan['files'] if any(issue['path'] == info['relative_path'] for issue in issues)],
        "scan_warnings": scan['warnings'],
        "scope_note": '僅掃描所選專案的 Markdown（含 SKILL.md）；排除 .git、依賴、建置與 symlink。規則式檢查可能誤報或漏報，無法判定所有語意衝突與不必要內容。',
        "summary": {
            "errors": sum(item["level"] == "error" for item in issues),
            "warnings": sum(item["level"] == "warning" for item in issues),
            "info": sum(item["level"] == "info" for item in issues),
            "characters": total_chars,
            "estimated_tokens": round(total_chars / 4),
            "scanned_files": len(scan['files']),
        },
        "effective_files": effective,
        "load_behavior": agent["load_behavior"],
    }
