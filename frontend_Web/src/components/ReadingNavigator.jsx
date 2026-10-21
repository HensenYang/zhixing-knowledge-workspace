import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import GraphView from './GraphView';
import { CollapsiblePanel, ErrorBox, RELATIONS } from './shared';
import { write } from '../services/api';

const TRAIL_KEY = 'workspace:reading-trail';
const PREFS_KEY = 'workspace:reading-preferences';
function read(key, fallback) {
  try { return JSON.parse(sessionStorage.getItem(key)) || fallback; } catch { return fallback; }
}
function store(key, value) {
  try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* Navigation works without storage. */ }
}
const meanings = {
  depends_on: ['前置知识／基座', '依赖当前的后续内容'],
  uses: ['采用的技术／资料', '使用当前的模型／方法'],
  implements: ['实现的理论／方法', '当前方法的实现'],
  evaluates: ['评测对象', '对当前的评测'],
  supports: ['支撑的内容', '当前的支持证据'],
  questions: ['提出疑问的对象', '针对当前的研究问题'],
  compares_with: ['横向比较', '横向比较'],
  related_to: ['相关知识', '相关知识']
};
export default function ReadingNavigator({ id, title, objects, relations, refresh, onEditRelation, onAddRelation }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false), [savingTrail,setSavingTrail]=useState(false), [trailError,setTrailError]=useState('');
  useEffect(() => {
    if (!expanded) return;
    const close = event => { if (event.key === 'Escape') setExpanded(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [expanded]);
  const [trail, setTrail] = useState(() => {
    const saved = read(TRAIL_KEY, []);
    return Array.isArray(saved) ? saved.filter(item => typeof item?.id === 'string').slice(-40) : [];
  });
  const [prefs, setPrefs] = useState(() => ({ relation: '', direction: 'both', depth: 1, ...read(PREFS_KEY, {}) }));
  useEffect(() => {
    setTrail(previous => {
      const next = previous.at(-1)?.id === id ? previous.map((item, i) => i === previous.length - 1 ? {...item, title} : item)
        : [...previous, {id, title}].slice(-40);
      store(TRAIL_KEY, next);
      return next;
    });
  }, [id, title]);
  function change(key, value) {
    setPrefs(previous => {
      const next = {...previous, [key]: value};
      store(PREFS_KEY, next);
      return next;
    });
  }
  const byId = Object.fromEntries(objects.map(object => [object.id, object]));
  const visitedIds = trail.map(item => item.id);
  const trailPairs = trail.slice(1).map((item, i) => [trail[i].id, item.id]);
  const groups = {};
  async function saveTrail() {
    if (!trail.length) return;
    setSavingTrail(true); setTrailError('');
    try {
      const created=await write('/learning-paths',{
        title:`阅读路径：${trail[0].title || title}`,
        objective_md:'沿本次访问顺序回顾知识，并补充每一步的理解目标。',
        description_md:'由当前浏览器标签页的阅读轨迹生成，可继续编辑、排序和发布。',
        completion_criteria_md:'',
        steps:trail.map(item=>({
          object_id:byId[item.id]?.id || null,
          title:byId[item.id]?.title || item.title || '已不可用的知识对象',
          guidance_md:'回顾这一步为什么出现在路径中，并记录它与前后步骤的联系。',
          completion_criteria_md:'',
          estimated_minutes:null
        }))
      });
      navigate(`/paths/${created.id}`);
    } catch (error) { setTrailError(error.message); }
    finally { setSavingTrail(false); }
  }
  for (const relation of relations) {
    if (relation.source_id !== id && relation.target_id !== id) continue;
    const symmetric = ['related_to', 'compares_with'].includes(relation.relation_type);
    const outgoing = relation.source_id === id;
    if (prefs.relation && relation.relation_type !== prefs.relation) continue;
    if (!symmetric && prefs.direction !== 'both' && outgoing !== (prefs.direction === 'outgoing')) continue;
    const target = byId[outgoing ? relation.target_id : relation.source_id];
    if (!target) continue;
    const label = (meanings[relation.relation_type] || ['关联', '关联'])[outgoing ? 0 : 1];
    (groups[label] ||= []).push({relation, target, outgoing, symmetric});
  }
  return <CollapsiblePanel title="沿关系阅读" className="reading-navigator" actions={<button type="button" className="ghost" onClick={onAddRelation}>添加关系</button>}>
    <p className="reading-position"><span>当前位置</span><strong>{title}</strong></p>
    <div className="reading-filters">
      <label>关系类型<select aria-label="阅读关系类型" value={prefs.relation} onChange={e => change('relation', e.target.value)}><option value="">全部关系</option>{Object.entries(RELATIONS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
      <label>连接方向<select aria-label="阅读连接方向" value={prefs.direction} onChange={e => change('direction', e.target.value)}><option value="both">双向查看</option><option value="outgoing">当前指向其他</option><option value="incoming">其他指向当前</option></select></label>
    </div>
    <div className="reading-graph-heading"><strong>跟随当前位置的局部图</strong><select aria-label="阅读图谱深度" value={prefs.depth} onChange={e => change('depth', Number(e.target.value))}><option value={1}>一层</option><option value={2}>两层</option></select><button className="ghost" onClick={() => setExpanded(true)}>展开</button></div>
    <GraphView center={id} depth={prefs.depth} relationType={prefs.relation} direction={prefs.direction} visitedIds={visitedIds} trailPairs={trailPairs} refresh={refresh} compact onNode={nodeId => nodeId !== id && navigate(`/knowledge/${nodeId}`)} onEdge={onEditRelation} />
    <p className="reading-legend">◎ 当前节点 · 金色圈：访问过 · 金色线：走过的关系<br />点击节点继续阅读；点击连线修改关系。</p>
    <div className="reading-neighbors">{Object.entries(groups).map(([label, rows]) => <section key={label}><h4>{label}</h4>{rows.map(({relation, target, outgoing, symmetric}) => <div className="reading-neighbor" key={relation.id}>
      <Link to={`/knowledge/${target.id}`}><small>{symmetric ? '↔' : outgoing ? '→' : '←'} {RELATIONS[relation.relation_type]}{visitedIds.includes(target.id) ? ' · 访问过' : ''}</small><strong>{target.title}</strong>{relation.description && <span>{relation.description}</span>}</Link>
      <button className="ghost" aria-label={`修改关系：${target.title}`} onClick={() => onEditRelation(relation.id)}>修改</button>
    </div>)}</section>)}{!Object.keys(groups).length && <p className="muted">当前筛选下没有相邻节点。可切换关系类型、方向或添加关系。</p>}</div>
    <details className="reading-trail" open><summary>本次阅读路径（最近40次访问）</summary><ol>{trail.map((item, index) => <li key={`${item.id}-${index}`}>{index === trail.length - 1 ? <strong aria-current="page">{byId[item.id]?.title || item.title} · 当前</strong> : byId[item.id] ? <Link to={`/knowledge/${item.id}`}>{byId[item.id].title}</Link> : <span>{item.title}（已不可用）</span>}</li>)}</ol><div className="actions"><button className="ghost" onClick={saveTrail} disabled={savingTrail}>{savingTrail?'保存中…':'保存为学习路径'}</button><button className="ghost" onClick={() => { const next = [{id, title}]; store(TRAIL_KEY, next); setTrail(next); }}>重新开始路径</button></div><ErrorBox message={trailError}/></details>
    <p className="muted">访问记录暂存在当前标签页；保存为学习路径后可继续编辑、排序和发布。</p>
    {expanded && <div className="modal-backdrop" onClick={event => { if (event.target === event.currentTarget) setExpanded(false); }}><section className="panel reading-graph-dialog" role="dialog" aria-modal="true" aria-label="展开局部图谱"><div className="section-heading"><h3>{title} · 局部图谱</h3><button autoFocus className="ghost" onClick={() => setExpanded(false)}>关闭图谱</button></div><p className="muted">{RELATIONS[prefs.relation] || '全部关系'} · {prefs.depth}层关联 · 点击节点继续阅读</p><GraphView center={id} depth={prefs.depth} relationType={prefs.relation} direction={prefs.direction} visitedIds={visitedIds} trailPairs={trailPairs} refresh={refresh} compact onNode={nodeId => { if (nodeId !== id) navigate(`/knowledge/${nodeId}`); }} onEdge={edgeId => { setExpanded(false); onEditRelation(edgeId); }} /></section></div>}
  </CollapsiblePanel>;
}
