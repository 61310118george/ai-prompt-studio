import csv
import io

import pytest

from ai_memory_app.data.database import connect, initialize_database
from ai_memory_app.data.prompt_library import PromptLibrary
from ai_memory_app.services.csv_import import CsvImport


@pytest.fixture
def service(tmp_path):
    path = tmp_path / 'test.db'
    initialize_database(path)
    return CsvImport(path)


def test_preview_then_commit_bom_multiline_and_reopen(service):
    preview = service.preview(service.example('prompts').encode(), 'prompts', 'personal')
    assert len(preview['rows']) == 1 and not preview['rows'][0]['errors']
    library = PromptLibrary(service.db_path)
    assert library.list('personal') == []
    result = service.commit(preview['preview_id'], 'personal', [0])
    assert result == {'created': 1, 'updated': 0, 'skipped': 0}
    assert '\n' in library.list('personal')[0]['content']
    assert library.groups('personal')[0]['name'] == '行銷'
    with pytest.raises(ValueError):
        service.commit(preview['preview_id'], 'personal', [0])


def test_scope_duplicates_and_revisions(service):
    raw = service.example('prompts').encode()
    first = service.preview(raw, 'prompts', 'a')
    with pytest.raises(ValueError, match='範本庫'):
        service.commit(first['preview_id'], 'b', [0])
    service.commit(first['preview_id'], 'a', [0])
    second = service.preview(raw, 'prompts', 'a')
    assert second['rows'][0]['duplicate']
    assert service.commit(second['preview_id'], 'a', [0])['skipped'] == 1
    third = service.preview(raw.replace('繁體'.encode(), '正體'.encode()), 'prompts', 'a')
    assert service.commit(third['preview_id'], 'a', [0], True)['updated'] == 1
    library = PromptLibrary(service.db_path)
    item = library.list('a')[0]
    assert item['version'] == 2 and len(library.history('a', item['id'])) == 2
    assert library.list('b') == []


def test_templates_overlay_persist_and_require_no_rebuild(service):
    raw = 'tag,role,task,requirements,output,acceptance\n寫作,編輯,文章改寫,保留事實,正文,可查證\n'
    preview = service.preview(raw.encode(), 'templates', 'personal')
    assert preview['rows'][0]['duplicate']
    service.commit(preview['preview_id'], 'personal', [0], True)
    assert next(row for row in CsvImport(service.db_path).catalog() if row['tag'] == '寫作')['task'] == '文章改寫'


def test_invalid_rows_and_batch_rollback(service):
    raw = 'title,content,group,tags\n有效,內容,一般,\n' + '長'*21 + ',內容,一般,\n'
    preview = service.preview(raw.encode(), 'prompts', 'a')
    assert preview['rows'][1]['line'] == 3
    with pytest.raises(ValueError):
        service.commit(preview['preview_id'], 'a', [0, 1])
    assert PromptLibrary(service.db_path).list('a') == []
    assert service.commit(preview['preview_id'], 'a', [0])['created'] == 1
    # A runtime conflict after the first INSERT must roll back that INSERT too.
    library = PromptLibrary(service.db_path)
    for _ in range(2):
        library.save('a', {'title': '重複', 'content': '原文', 'category': '一般'})
    p = service.preview('title,content\n新項目,新文\n重複,更新\n'.encode(), 'prompts', 'a')
    with pytest.raises(ValueError, match='多筆'):
        service.commit(p['preview_id'], 'a', [0, 1], True)
    assert not library.list('a', '新項目')


@pytest.mark.parametrize('raw', [b'bad,headers\na,b', b'\xff', b'title,content\na,"unterminated', b'title,title,content\na,b,c', b'title,content\n'])
def test_bad_csv_rejected(service, raw):
    with pytest.raises(ValueError):
        service.preview(raw, 'prompts', 'a')


def test_quoted_commas_missing_fields_and_internal_duplicates(service):
    p = service.preview(b'title,content\nA,"hello, world\nnext line"\nA,duplicate\nB\n', 'prompts', 'a')
    assert p['rows'][0]['data']['content'] == 'hello, world\nnext line'
    assert p['rows'][0]['line'] == 3
    assert p['rows'][1]['errors'] and p['rows'][2]['errors']


def test_preview_expiry(service, monkeypatch):
    p = service.preview(service.example('prompts').encode(), 'prompts', 'a')
    import ai_memory_app.services.csv_import as module
    now = module.time.monotonic()
    monkeypatch.setattr(module.time, 'monotonic', lambda: now + 901)
    with pytest.raises(ValueError, match='過期'):
        service.commit(p['preview_id'], 'a', [0])
