import json
from pathlib import Path
import shutil
import subprocess

import pytest

from ai_memory_app.services.document_profiles import load_document_profiles, profile_fields
from ai_memory_app.services.document_assistance import context
from ai_memory_app.services.document_project import validate_document_state


def test_catalog_covers_all_topics_and_document_specific_sections():
    catalog = load_document_profiles()
    assert {field['id'] for field in catalog['mcp']} == {
        'purpose', 'host', 'tools', 'resources', 'prompts', 'connection',
        'dependencies', 'security', 'verification'}
    assert profile_fields('mcp') == catalog['mcp']
    assert len(catalog['profiles']) == 13
    for key, variants in catalog['profiles'].items():
        assert set(variants) == {'core', 'memory', 'skill'}
        section_sets = []
        for kind, fields in variants.items():
            assert len({f['id'] for f in fields}) == len(fields)
            assert {f['group'] for f in fields} == {'角色／場景', '任務／動作', '想法'}
            assert all(f['question'] and f['example'] and f['section'] for f in fields)
            section_sets.append(tuple(dict.fromkeys(f['section'] for f in fields)))
        assert len(set(section_sets)) == 3
    leaves = {key: value for key, value in catalog['profiles'].items() if '/' in key}
    assert len(leaves) == 8
    for kind in ('core', 'memory', 'skill'):
        questions = [tuple(f['question'] for f in value[kind]) for value in leaves.values()]
        assert len(set(questions)) == 8
    assert 'CTA' in str(leaves['推廣行銷/撰寫文案'])
    assert '競品' in str(leaves['推廣行銷/分析市場'])


def test_profiles_are_server_owned_and_category_is_validated():
    request = dict(consent=True, mode='write', title='網頁', document_type='skill',
                   schema_version=2, major='開發程式', minor='寫網頁', field_spec=[{'id':'injected'}])
    result = context(request)
    assert result['field_spec'] == profile_fields('skill', '開發程式', '寫網頁')
    with pytest.raises(ValueError):
        context({**request, 'minor':'撰寫文案'})


def test_topic_drafts_roundtrip_and_reject_invalid_nested_fields():
    docs = {'core': {'fields': {'role':'網站工程師'}, 'content':'# 原稿'}}
    value = {'mode':'core', 'documents':{}, 'topicDrafts': {'開發程式/寫網頁':docs}}
    assert validate_document_state(json.dumps(value))['topicDrafts']['開發程式/寫網頁'] == docs
    with pytest.raises(ValueError):
        validate_document_state({'mode':'core','topicDrafts':{'bad':{'core':{'fields':{'role':42}}}}})


def test_compiler_maps_answers_without_copying_examples():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the shared frontend compiler test')
    root = Path(__file__).resolve().parents[1]
    script = r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {configureDocumentProfiles,compileDocument} from './web-ui/document-catalog.js';
const data=JSON.parse(fs.readFileSync('resources/document_profiles.json','utf8'));
configureDocumentProfiles(data);
for(const [key,types] of Object.entries(data.profiles)){
 for(const [kind,schema] of Object.entries(types)){
  const answers=Object.fromEntries(schema.map(f=>[f.id,`ANSWER_${kind}_${f.id}`]));
  const tags=key.includes('/')?`${key.split('/')[0]},${key}`:key;
  const md=compileDocument(kind,'測試',answers,tags,'test-workflow');
  assert.ok(md.includes('# 測試'));
  for(const f of schema){
   assert.ok(md.includes(`## ${f.section}`));
   assert.ok(md.includes(`### ${f.label}\n\n${answers[f.id]}`));
   assert.ok(!md.includes(f.example));
  }
  if(kind==='skill')assert.ok(md.includes('description: "ANSWER_skill_trigger"'));
 }
}
const partial=compileDocument('core','未完成',{role:'工程師'},'');
assert.ok(partial.includes('[待確認]'));
const mcp=compileDocument('mcp','社群資料 MCP',{purpose:'讀取成效',tools:'查詢貼文',connection:'本機 stdio',security:'禁止個資',verification:'Inspector 測試'},'推廣行銷,推廣行銷/分析市場');
assert.ok(mcp.includes('MCP Server 的實作藍圖'));
assert.ok(mcp.includes('## Tools（AI 可執行的動作）'));
assert.ok(mcp.includes('### 可執行的動作\n\n查詢貼文'));
assert.throws(()=>compileDocument('skill','未完成',{task:'執行'},''));
const old=compileDocument('core','舊稿',{purpose:'舊版不可遺失內容',role:'工程師'},'');
assert.ok(old.includes('舊版不可遺失內容'));
'''
    subprocess.run([node, '--input-type=module', '--eval', script], cwd=root, check=True, capture_output=True, text=True)
