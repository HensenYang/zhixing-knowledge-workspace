import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Plus, ArrowUpRight, Save, Archive, RotateCcw, Paperclip } from 'lucide-react';
import { api, write } from '../services/api';
import { Badge, Field, PageTitle, SelectKind, Empty, ErrorBox, Markdown, DateText, RELATIONS } from '../components/shared';
import ReadingNavigator from '../components/ReadingNavigator';
import RelationEditor from '../components/RelationEditor';
import { DeleteButton, useWorkspaceChanges } from '../components/RecordActions';
import useDraft from '../hooks/useDraft';
export function KnowledgeList() {
  const [objects, setObjects] = useState([]),
    [q, setQ] = useState(''),
    [kind, setKind] = useState(''),
    [error, setError] = useState(''),
    [archived, setArchived] = useState(false),
    [refresh, setRefresh] = useState(0);
  const navigate = useNavigate();
  useEffect(() => {
    let alive = true;
    api(`/objects?q=${encodeURIComponent(q)}&kind=${kind}&archived=${archived}`).then(rows => {
      if (alive) {
        setObjects(rows);
        setError('');
      }
    }).catch(e => {
      if (alive) setError(e.message);
    });
    return () => {
      alive = false;
    };
  }, [q, kind, archived, refresh]);
  useWorkspaceChanges(() => setRefresh(v => v + 1));
  async function add() {
    try {
      const obj = await write('/objects', {
        kind: kind || 'concept',
        title: '未命名笔记'
      });
      navigate(`/knowledge/${obj.id}?mode=edit`);
    } catch (e) {
      setError(e.message);
    }
  }
  return <><PageTitle eyebrow="KNOWLEDGE LIBRARY" title="知识与资料" actions={<button onClick={add}><Plus size={16} />新建笔记</button>}>每一份理解，都可以连接到资料、代码和实验。</PageTitle><div className="toolbar"><input aria-label="搜索知识" value={q} onChange={e => setQ(e.target.value)} placeholder="搜索标题、正文或标签…" /><select aria-label="筛选类型" value={kind} onChange={e => setKind(e.target.value)}><option value="">全部类型</option>{['concept', 'resource', 'repository', 'model', 'dataset', 'benchmark', 'experiment', 'question', 'task'].map(k => <option key={k} value={k}>{{
            concept: '概念',
            resource: '资料',
            repository: '代码仓库',
            model: '模型',
            dataset: '数据集',
            benchmark: '评测',
            experiment: '实验',
            question: '问题',
            task: '任务'
          }[k]}</option>)}</select><label className="check"><input type="checkbox" checked={archived} onChange={e => setArchived(e.target.checked)} />包含归档</label></div><ErrorBox message={error} /><div className="knowledge-grid">{objects.map(o => <article key={o.id} className={`knowledge-card ${o.archived_at ? 'archived' : ''}`}><Link className="knowledge-card-content" aria-label={`阅读：${o.title}`} to={`/knowledge/${o.id}`}><div className="flex items-center justify-between"><Badge kind={o.kind} /><ArrowUpRight size={15} /></div><h3>{o.title}</h3><p>{o.summary || o.body_md.slice(0, 95) || '添加你的理解、来源与下一步。'}</p><div className="card-footer"><span>{o.archived_at ? '已归档' : {
              unread: '待处理',
              skimming: '浏览中',
              reading: '精读中',
              organized: '已整理'
            }[o.reading_status]}</span><span>{o.tags.slice(0, 2).map(t => `#${t}`).join(' ')}</span></div></Link><div className="actions"><Link className="button ghost" to={`/knowledge/${o.id}?mode=edit`}>修改笔记</Link><DeleteButton kind="object" id={o.id} title={o.title} /></div></article>)}</div>{!objects.length && !error && <Empty />}</>;
}
function editable(o) {
  return {
    kind: o.kind,
    title: o.title,
    summary: o.summary,
    body_md: o.body_md,
    source_url: o.source_url || '',
    reading_status: o.reading_status,
    mastery_status: o.mastery_status,
    metadata: o.metadata,
    tags: o.tags || [],
    version: o.version,
    archived_at: o.archived_at
  };
}
export function KnowledgeDetail() {
  const {
    id
  } = useParams();
  return <KnowledgeDetailInner key={id} />;
}
function KnowledgeDetailInner() {
  const {
      id
    } = useParams(),
    navigate = useNavigate();
  const [initial, setInitial] = useState(null),
    [objects, setObjects] = useState([]),
    [relations, setRelations] = useState([]),
    [attachments, setAttachments] = useState([]),
    [error, setError] = useState(''),
    [refresh, setRefresh] = useState(0),
    [relation, setRelation] = useState(null),
    [history, setHistory] = useState(null),
    [metaError, setMetaError] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = searchParams.get('mode') === 'edit' ? 'edit' : 'preview';
  const setMode = next => {
    const params = new URLSearchParams(searchParams);
    if (next === 'edit') params.set('mode', 'edit');
    else params.delete('mode');
    setSearchParams(params, { replace: true });
  };
  const goBack = () => {
    if (window.history.state?.idx > 0) navigate(-1);
    else navigate('/knowledge');
  };
  useEffect(() => {
    setInitial(null);
    api(`/objects/${id}`).then(o => setInitial(editable(o))).catch(e => setError(e.message));
  }, [id]);
  useEffect(() => {
    Promise.all([api('/objects?limit=1000&archived=true'), api('/relations'), api(`/objects/${id}/attachments`)]).then(([o, r, a]) => {
      setObjects(o);
      setRelations(r);
      setAttachments(a);
    }).catch(e => setError(e.message));
  }, [id, refresh]);
  const draft = useDraft(`object:${id}`, initial, v => write(`/objects/${id}`, v, 'PATCH').then(editable));
  useWorkspaceChanges(() => setRefresh(v => v + 1));
  const form = draft.value;
  const update = (key, value) => draft.change(v => ({
    ...v,
    [key]: value
  }));
  async function upload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const data = new FormData();
    data.append('file', file);
    try {
      await api(`/objects/${id}/attachments`, {
        method: 'POST',
        body: data
      });
      setRefresh(r => r + 1);
    } catch (e) {
      setError(e.message);
    }
  }
  async function showHistory() {
    try {
      setHistory(await api(`/objects/${id}/revisions`));
    } catch (e) {
      setError(e.message);
    }
  }
  if (!form) return <><ErrorBox message={error} /><div className="empty">加载笔记…</div></>;
  return <><div className="detail-top"><div className="actions detail-navigation"><button className="ghost" onClick={goBack}>← 返回上一页</button><Link to="/knowledge">知识与资料</Link></div><div className="actions"><span className="save-status">{draft.status}</span><button onClick={draft.save}><Save size={15} />保存</button><button className="ghost" onClick={draft.download}>下载草稿</button><DeleteButton kind="object" id={id} title={form.title} label="删除笔记" beforeDelete={draft.save} onDeleted={() => navigate("/knowledge")} /></div></div><ErrorBox message={error || draft.error} />{draft.error && <button className="ghost" onClick={async () => {
      await draft.discard();
      setInitial(editable(await api(`/objects/${id}`)));
    }}>放弃本地草稿并加载服务器版本</button>}<div className="detail-layout"><section className="panel editor-panel"><div className="flex justify-between items-center"><Badge kind={form.kind} /><div className="segmented"><button className={mode === 'edit' ? 'active' : ''} onClick={() => setMode('edit')}>编辑</button><button className={mode === 'preview' ? 'active' : ''} onClick={() => setMode('preview')}>阅读</button></div></div><input className="title-input" aria-label="笔记标题" value={form.title} onChange={e => update('title', e.target.value)} /><input className="summary-input" aria-label="一句话摘要" placeholder="用一句话记录你对它的理解…" value={form.summary} onChange={e => update('summary', e.target.value)} />{mode === 'edit' ? <textarea className="markdown-editor" aria-label="笔记正文" placeholder={'从一个问题开始。\n\n支持 Markdown、代码块和数学公式，例如 $a_t = \\pi(o_t)$。'} value={form.body_md} onChange={e => update('body_md', e.target.value)} /> : <Markdown>{form.body_md}</Markdown>}<div className="editor-footer"><span>Markdown · 公式 · 代码</span><button className="ghost" onClick={showHistory}><RotateCcw size={14} />修订历史</button></div>{history && <div className="history"><h3>修订历史</h3>{history.length ? history.map(r => <div key={r.id} className="history-row"><span>版本 {r.version} · <DateText value={r.created_at} /></span><button className="ghost" onClick={() => {
              draft.change({
                ...r.snapshot,
                version: form.version,
                tags: r.snapshot.tags || []
              });
              setHistory(null);
            }}>恢复到草稿</button></div>) : <p>首次编辑保存后会生成历史。</p>}</div>}</section><aside className="detail-sidebar"><ReadingNavigator id={id} title={form.title} objects={objects} relations={relations} refresh={refresh} onAddRelation={() => setRelation('new')} onEditRelation={edgeId => setRelation(relations.find(r => r.id === edgeId))} />{relation && <section className="panel"><RelationEditor key={relation.id || 'new'} objects={objects} initial={relation === 'new' ? null : relation} source={id} onDone={() => { setRelation(null); setRefresh(r => r + 1); }} /></section>}<section className="panel"><h3>笔记属性</h3><Field label="类型"><SelectKind value={form.kind} onChange={e => update('kind', e.target.value)} /></Field><Field label="阅读进度"><select value={form.reading_status} onChange={e => update('reading_status', e.target.value)}>{Object.entries({
                unread: '待处理',
                skimming: '浏览',
                reading: '精读',
                organized: '已整理'
              }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field><Field label="理解程度"><select value={form.mastery_status} onChange={e => update('mastery_status', e.target.value)}>{Object.entries({
                unknown: '尚未理解',
                explain: '能解释',
                implement: '能实现',
                reproduce: '能复现',
                analyze: '能分析局限'
              }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field><Field label="来源链接"><input value={form.source_url} onChange={e => update('source_url', e.target.value)} placeholder="https://…" /></Field>{/^https?:\/\//.test(form.source_url) && <a className="text-link" href={form.source_url} target="_blank" rel="noreferrer">打开来源 ↗</a>}<Field label="标签（逗号分隔）"><input value={form.tags.join(', ')} onChange={e => update('tags', e.target.value.split(/[,，]/))} /></Field><details><summary>扩展属性 JSON</summary><textarea key={`${id}-${history?.length || ''}`} defaultValue={JSON.stringify(form.metadata, null, 2)} rows={5} onBlur={e => {
              try {
                const val = JSON.parse(e.target.value);
                if (typeof val !== 'object' || Array.isArray(val) || val === null) throw Error();
                update('metadata', val);
                setMetaError('');
              } catch {
                setMetaError('扩展属性必须是有效的 JSON 对象。');
              }
            }} /><ErrorBox message={metaError} /></details><button className="ghost" onClick={() => update('archived_at', form.archived_at ? null : new Date().toISOString())}><Archive size={14} />{form.archived_at ? '恢复归档笔记' : '归档笔记'}</button></section><section className="panel"><div className="section-heading"><h3>资料附件</h3><label className="icon-button" aria-label="上传附件"><Paperclip size={16} /><input type="file" className="hidden" onChange={upload} /></label></div>{attachments.map(a => <div key={a.id}><a className="attachment" href={`/api/attachments/${a.id}`} target="_blank" rel="noreferrer">{a.original_name}<small>{Math.round(a.size_bytes / 1024)} KB</small></a><div className="actions"><button className="ghost" onClick={async () => {
                const name = window.prompt("附件名称", a.original_name);
                if (!name?.trim()) return;
                try {
                  await write(`/attachments/${a.id}`, {
                    original_name: name.trim()
                  }, "PATCH");
                  setRefresh(v => v + 1);
                } catch (e) {
                  setError(e.message);
                }
              }}>重命名</button><DeleteButton kind="attachment" id={a.id} title={a.original_name} /></div></div>)}{!attachments.length && <p className="muted">保存 PDF、图片或小型实验日志。</p>}</section></aside></div></>;
}
