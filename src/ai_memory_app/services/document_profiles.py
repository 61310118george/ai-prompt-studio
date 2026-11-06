"""Shared, local question bank for desktop forms and AI request schemas."""
import json
from functools import lru_cache

from .agent_catalog import application_root


@lru_cache(maxsize=1)
def load_document_profiles():
    path = application_root() / 'resources' / 'document_profiles.json'
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def profile_fields(kind, major='', minor=''):
    catalog = load_document_profiles()
    if kind == 'mcp':
        return catalog['mcp']
    profiles = catalog['profiles']
    key = f'{major}/{minor}' if minor else major
    if key not in profiles or kind not in profiles[key]:
        raise ValueError('文件分類不正確，請重新選擇標籤。')
    return profiles[key][kind]
