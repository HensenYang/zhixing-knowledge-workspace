import { useState } from 'react';
import { write } from '../services/api';
import { Field, RELATIONS, ErrorBox } from './shared';
import { DeleteButton } from './RecordActions';
export default function RelationEditor({
  objects,
  initial,
  source,
  onDone,
  showTitle = true
}) {
  const [form, setForm] = useState(initial || {
    source_id: source || objects[0]?.id || '',
    target_id: objects.find(o => o.id !== (source || objects[0]?.id))?.id || '',
    relation_type: 'related_to',
    description: '',
    evidence: []
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const change = (key, value) => setForm({
    ...form,
    [key]: key === 'evidence' ? [...value, ...form.evidence.slice(1)] : value
  });
  const evidence = form.evidence?.[0] || {};
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const payload = {
        ...form,
        evidence: form.evidence.filter(item => item.evidence_object_id || item.source_url)
      };
      await write(initial ? `/relations/${initial.id}` : '/relations', payload, initial ? 'PATCH' : 'POST');
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <form className="relation-form" onSubmit={save}>{showTitle && <h3>{initial ? '编辑关系' : '建立知识关系'}</h3>}<Field label="起点"><select value={form.source_id} onChange={e => change('source_id', e.target.value)}>{objects.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}</select></Field><Field label="关系"><select value={form.relation_type} onChange={e => change('relation_type', e.target.value)}>{Object.entries(RELATIONS).map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></Field><Field label="终点"><select value={form.target_id} onChange={e => change('target_id', e.target.value)}>{objects.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}</select></Field><Field label="为什么建立这条关系？"><textarea value={form.description} onChange={e => change('description', e.target.value)} rows={3} /></Field><details><summary>添加证据与定位</summary><Field label="证据对象"><select value={evidence.evidence_object_id || ''} onChange={e => change('evidence', [{
          ...evidence,
          evidence_object_id: e.target.value || null
        }])}><option value="">不选择</option>{objects.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}</select></Field><Field label="来源地址"><input value={evidence.source_url || ''} onChange={e => change('evidence', [{
          ...evidence,
          source_url: e.target.value || null
        }])} /></Field><Field label="页码／章节／代码行"><input value={evidence.locator || ''} onChange={e => change('evidence', [{
          ...evidence,
          locator: e.target.value
        }])} /></Field></details><ErrorBox message={error} /><div className="actions"><button disabled={busy || !form.source_id || !form.target_id}>保存关系</button>{initial && <DeleteButton kind="relation" id={initial.id} title="知识关系" label="删除关系" onDeleted={onDone} />}<button type="button" className="ghost" onClick={onDone}>关闭</button></div></form>;
}
