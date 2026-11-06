"""Bounded contracts for document clarification and confirmed drafting."""
import json

LEGACY_FIELDS = {
    'core': {'purpose': '專案目標與範圍', 'rules': '固定規則與禁止事項', 'workflow': '協作與確認流程', 'verification': '完成與驗收方式'},
    'memory': {'background': '背景與已確認事實', 'audience': '使用對象與需求', 'preferences': '語氣與工作偏好', 'decisions': '既有決策與待確認事項'},
    'skill': {'trigger': '用途與使用時機', 'inputs': '需要提供的資料', 'steps': '執行步驟', 'output': '輸出格式與驗收'},
    'mcp': {},
}


FIELDS = {kind: {'role': '角色／場景', 'task': '任務／動作', 'ideas': '想法'} for kind in LEGACY_FIELDS}

def bounded_text(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError('AI 問答欄位格式或長度不正確。')
    return value


def context(request):
    if not isinstance(request, dict) or request.get('consent') is not True:
        raise ValueError('請先確認傳送資料。')
    result = {key: bounded_text(request.get(key, ''), size) for key, size in
              {'title': 100, 'tags': 500, 'document_type': 20, 'field_id': 40, 'content': 20000, 'guidance': 2000, 'mode': 20}.items()}
    if not result['title'].strip() or result['document_type'] not in FIELDS or result['mode'] not in {'revise', 'write'}:
        raise ValueError('請填寫標題並選擇文件類型。')
    if request.get('schema_version') == 2:
        from .document_profiles import profile_fields
        result.update(schema_version=2, major=bounded_text(request.get('major', ''), 100),
                      minor=bounded_text(request.get('minor', ''), 100))
        spec = profile_fields(result['document_type'], result['major'], result['minor'])
        result['field_spec'] = spec
    else:
        spec = []
    if result['mode'] == 'revise':
        allowed = set(FIELDS[result['document_type']]) | set(LEGACY_FIELDS[result['document_type']]) | {field['id'] for field in spec}
        if result['field_id'] not in allowed or not result['content'].strip():
            raise ValueError('請先填寫要修正的欄位內容。')
    else:
        result['field_id'] = ''
        result['content'] = ''
    return result


def clarification(value):
    if not isinstance(value, dict):
        raise ValueError('AI 問答格式不正確，請重試。')
    result = {}
    for key, low, high in [('understanding', 1, 5), ('questions', 1, 6)]:
        items = value.get(key)
        if not isinstance(items, list) or not low <= len(items) <= high:
            raise ValueError('AI 未回傳有效的理解重點與問題，請重試。')
        result[key] = [bounded_text(text, 600, True) for text in items]
    return result


def parse_result(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        raise ValueError('AI 回應不是有效的結構化內容，原文未變更，請重試。') from None
