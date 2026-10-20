import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { api, write } from '../services/api';
import { PageTitle, KINDS, COLORS, Badge, RELATIONS, ErrorBox, Field, SelectKind } from '../components/shared';
import { DeleteButton, useWorkspaceChanges, announceChange } from '../components/RecordActions';
import GraphView from '../components/GraphView';
import RelationEditor from '../components/RelationEditor';
function NodeEditor({
  object,
  onDone
}) {
  const [form, setForm] = useState(object),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const change = (key, value) => setForm(v => ({
    ...v,
    [key]: value
  }));
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await write(`/objects/${object.id}`, form, 'PATCH');
      announceChange();
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <form onSubmit={save}><h2>修改知识节点</h2><Field label="节点名称"><input required value={form.title} onChange={e => change('title', e.target.value)} /></Field><Field label="节点类型"><SelectKind value={form.kind} onChange={e => change('kind', e.target.value)} /></Field><Field label="节点摘要"><textarea rows={4} value={form.summary} onChange={e => change('summary', e.target.value)} /></Field><Field label="节点来源"><input value={form.source_url || ''} onChange={e => change('source_url', e.target.value)} /></Field><ErrorBox message={error} /><div className="actions"><button disabled={busy}>保存节点</button><button type="button" className="ghost" onClick={onDone}>取消</button></div><p className="muted">正文、标签和扩展属性可在完整笔记中修改。</p><Link to={`/knowledge/${object.id}`} className="text-link">打开完整笔记 ↗</Link></form>;
}
export default function Graph() {
  const [objects, setObjects] = useState([]),
    [relations, setRelations] = useState([]),
    [filter, setFilter] = useState(''),
    [selectedId, setSelectedId] = useState(null),
    [editing, setEditing] = useState(null),
    [editNode, setEditNode] = useState(false),
    [refresh, setRefresh] = useState(0),
    [error, setError] = useState(''),
    [q, setQ] = useState(''),
    [center, setCenter] = useState(''),
    [depth, setDepth] = useState(2),
    [view, setView] = useState('graph');
  useEffect(() => {
    let alive = true;
    Promise.all([api('/objects?limit=1000'), api('/relations')]).then(([o, r]) => {
      if (!alive) return;
      setObjects(o);
      setRelations(r);
      setError('');
      if (center && !o.some(item => item.id === center)) setCenter('');
    }).catch(e => setError(e.message));
    return () => {
      alive = false;
    };
  }, [refresh]);
  useWorkspaceChanges(() => setRefresh(r => r + 1));
  const selected = objects.find(o => o.id === selectedId);
  const done = () => {
    setEditing(null);
    setEditNode(false);
    setRefresh(r => r + 1);
  };
  const select = id => {
    setSelectedId(id);
    setEditing(null);
    setEditNode(false);
  };
  const filtered = objects.filter(o => (!filter || o.kind === filter) && o.title.toLowerCase().includes(q.toLowerCase()));
  const title = id => objects.find(o => o.id === id)?.title || '未知节点';
  return <><PageTitle eyebrow="CONNECTED KNOWLEDGE" title="知识图谱" actions={<button onClick={() => {
      setEditing('new');
      setEditNode(false);
    }} disabled={objects.length < 2}><Plus size={16} />建立关系</button>}>点击节点或连线进行修改，也可以用列表管理连接。</PageTitle><div className="toolbar"><input aria-label="寻找图谱节点" placeholder="寻找节点…" value={q} onChange={e => setQ(e.target.value)} /><select aria-label="中心节点" value={center} onChange={e => {
        setCenter(e.target.value);
        select(e.target.value);
      }}><option value="">全局网络</option>{filtered.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}</select><select aria-label="关联深度" value={depth} onChange={e => setDepth(Number(e.target.value))}><option value={1}>一层关联</option><option value={2}>两层关联</option><option value={3}>三层关联</option></select><select aria-label="图谱类型" value={filter} onChange={e => setFilter(e.target.value)}><option value="">全部类型</option>{Object.entries(KINDS).map(([k, v]) => <option value={k} key={k}>{v}</option>)}</select><div className="segmented">{[['graph', '图谱'], ['nodes', '节点列表'], ['relations', '关系列表']].map(([key, label]) => <button key={key} className={view === key ? 'active' : ''} onClick={() => setView(key)}>{label}</button>)}</div></div><ErrorBox message={error} /><div className="graph-layout"><section className="panel graph-panel">{view === 'graph' ? <><GraphView center={center || undefined} depth={depth} filter={filter} refresh={refresh} onNode={select} onEdge={id => {
            setEditing(relations.find(r => r.id === id));
            setEditNode(false);
          }} /><div className="graph-legend">{Object.entries(KINDS).map(([k, v]) => <span key={k}><i style={{
                background: COLORS[k]
              }} />{v}</span>)}</div></> : <div className="record-list graph-record-list">{view === 'nodes' ? filtered.map(o => <article className="record-row" key={o.id}><div><Badge kind={o.kind} /><h3>{o.title}</h3></div><div className="actions"><button className="ghost" onClick={() => {
                select(o.id);
                setEditNode(true);
              }}>修改节点</button><DeleteButton kind="object" id={o.id} title={o.title} /></div></article>) : relations.filter(r => filtered.some(o => o.id === r.source_id || o.id === r.target_id)).map(r => <article className="record-row" key={r.id}><div><h3>{title(r.source_id)} → {RELATIONS[r.relation_type]} → {title(r.target_id)}</h3><p>{r.description}</p></div><div className="actions"><button className="ghost" onClick={() => setEditing(r)}>修改关系</button><DeleteButton kind="relation" id={r.id} title={`${title(r.source_id)} → ${title(r.target_id)}`} /></div></article>)}</div>}</section><aside className="panel graph-details">{editing ? <RelationEditor key={editing.id || 'new'} objects={objects} initial={editing === 'new' ? null : editing} onDone={done} /> : selected && editNode ? <NodeEditor key={`${selected.id}-${selected.version}`} object={selected} onDone={done} /> : selected ? <><Badge kind={selected.kind} /><h2>{selected.title}</h2><p>{selected.summary || '尚未添加摘要'}</p><div className="actions"><button onClick={() => setEditNode(true)}>修改节点</button><DeleteButton kind="object" id={selected.id} title={selected.title} /></div><Link className="text-link" to={`/knowledge/${selected.id}`}>打开完整笔记 ↗</Link><h3 className="mt-6">相关连接</h3>{relations.filter(r => r.source_id === selected.id || r.target_id === selected.id).map(r => <button className="relation-row" key={r.id} onClick={() => setEditing(r)}>{RELATIONS[r.relation_type]} · {title(r.source_id === selected.id ? r.target_id : r.source_id)}</button>)}</> : <><span className="eyebrow">EXPLORE</span><h2>从一个节点开始</h2><p className="muted">点击节点查看内容、修改名称或删除。点击连线编辑关系；节点列表和关系列表也提供操作入口。</p><div className="info-note">删除的记录可在回收站恢复。画布引用保留，恢复时连接自动重新显示。</div></>}</aside></div></>;
}
