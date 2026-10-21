import {useEffect, useState} from 'react';
import {Link, useNavigate, useParams} from 'react-router-dom';
import {ArrowLeft, ChevronDown, ChevronUp, Clock, Copy, ExternalLink, ListOrdered, Plus, Save, Share2} from 'lucide-react';
import {api, write} from '../services/api';
import {Badge, Empty, ErrorBox, Field, Markdown, PageTitle} from '../components/shared';
import {DeleteButton, announceChange, useWorkspaceChanges} from '../components/RecordActions';

const blankPath = title => ({
  title,
  objective_md: '',
  description_md: '',
  completion_criteria_md: '',
  steps: []
});

export function LearningPathList() {
  const [paths,setPaths]=useState([]), [title,setTitle]=useState(''), [creating,setCreating]=useState(false), [error,setError]=useState('');
  const navigate=useNavigate();
  const load=()=>api('/learning-paths').then(setPaths).catch(e=>setError(e.message));
  useEffect(()=>{load();},[]);
  useWorkspaceChanges(load);
  async function create(event) {
    event.preventDefault();
    if (!title.trim()) return;
    setCreating(true); setError('');
    try {
      const path=await write('/learning-paths',blankPath(title.trim()));
      announceChange();
      navigate(`/paths/${path.id}`);
    } catch (e) { setError(e.message); }
    finally { setCreating(false); }
  }
  return <>
    <PageTitle eyebrow="RESEARCH LEARNING PATHS" title="研究学习路径">
      把知识对象编排为有目标、有顺序、有完成条件的研究讲解路径。
    </PageTitle>
    <form className="toolbar path-create" onSubmit={create}>
      <input aria-label="新学习路径名称" value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：从 VLA 基础到完成一次模型复现" />
      <button disabled={creating || !title.trim()}><Plus size={16}/>{creating?'创建中…':'新建学习路径'}</button>
    </form>
    <ErrorBox message={error}/>
    <div className="knowledge-grid path-grid">{paths.map(path=><article className="knowledge-card" key={path.id}>
      <div className="flex items-center justify-between"><span className={`status-pill ${path.status==='published'?'succeeded':''}`}>{path.status==='published'?'已发布':'草稿'}</span><ListOrdered size={17}/></div>
      <h3>{path.title}</h3>
      <p>{path.objective_md || '尚未填写学习目标。'}</p>
      <div className="card-footer"><span>{path.step_count} 个步骤</span><span>{path.estimated_minutes?`约 ${path.estimated_minutes} 分钟`:'未估算用时'}</span></div>
      <div className="actions"><Link className="button ghost" to={`/paths/${path.id}`}>编辑路径</Link><DeleteButton kind="path" id={path.id} title={path.title}/></div>
    </article>)}</div>
    {!paths.length && !error && <Empty title="创建第一条研究学习路径">从一个明确目标开始，再按顺序加入资料、概念和实验。</Empty>}
  </>;
}

export function LearningPathEditor() {
  const {id}=useParams(), navigate=useNavigate();
  const [doc,setDoc]=useState(null), [objects,setObjects]=useState([]), [selectedObject,setSelectedObject]=useState('');
  const [error,setError]=useState(''), [message,setMessage]=useState(''), [busy,setBusy]=useState(false);
  useEffect(()=>{
    Promise.all([api(`/learning-paths/${id}`),api('/objects?limit=1000')]).then(([path,items])=>{
      setDoc(path); setObjects(items); setSelectedObject(items[0]?.id || '');
    }).catch(e=>setError(e.message));
  },[id]);
  const change=(key,value)=>setDoc(current=>({...current,[key]:value}));
  const changeStep=(index,key,value)=>setDoc(current=>({...current,steps:current.steps.map((step,i)=>i===index?{...step,[key]:value}:step)}));
  function addObjectStep() {
    const object=objects.find(item=>item.id===selectedObject);
    if (!object) return;
    setDoc(current=>({...current,steps:[...current.steps,{
      id:crypto.randomUUID(),object_id:object.id,title:object.title,guidance_md:'',completion_criteria_md:'',estimated_minutes:null,
      object_title:object.title,object_summary:object.summary,object_kind:object.kind,object_available:true
    }]}));
  }
  function addIndependentStep() {
    setDoc(current=>({...current,steps:[...current.steps,{
      id:crypto.randomUUID(),object_id:null,title:'新的学习步骤',guidance_md:'',completion_criteria_md:'',estimated_minutes:null,object_available:false
    }]}));
  }
  function move(index,direction) {
    const target=index+direction;
    if (target<0 || target>=doc.steps.length) return;
    const steps=[...doc.steps]; [steps[index],steps[target]]=[steps[target],steps[index]];
    setDoc({...doc,steps});
  }
  function remove(index) { setDoc({...doc,steps:doc.steps.filter((_,i)=>i!==index)}); }
  function payload(path=doc) {
    return {
      title:path.title,objective_md:path.objective_md,description_md:path.description_md,
      completion_criteria_md:path.completion_criteria_md,version:path.version,
      steps:path.steps.map(step=>({
        id:step.id,object_id:step.object_id || null,title:step.title,guidance_md:step.guidance_md,
        completion_criteria_md:step.completion_criteria_md,
        estimated_minutes:step.estimated_minutes==='' || step.estimated_minutes==null?null:Number(step.estimated_minutes)
      }))
    };
  }
  async function save() {
    setBusy(true); setError(''); setMessage('');
    try {
      const saved=await write(`/learning-paths/${id}`,payload(),'PUT');
      setDoc(saved); setMessage('学习路径已保存。'); announceChange();
      return saved;
    } catch (e) { setError(e.message); return null; }
    finally { setBusy(false); }
  }
  async function publish() {
    const saved=await save();
    if (!saved) return;
    setBusy(true); setMessage('');
    try {
      const published=await write(`/learning-paths/${id}/publish`,{});
      setDoc(published); setMessage('路径已发布，可以复制只读分享链接。'); announceChange();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function unpublish() {
    setBusy(true); setError(''); setMessage('');
    try {
      const draft=await write(`/learning-paths/${id}/unpublish`,{});
      setDoc(draft); setMessage('分享已停止，旧链接已经失效。'); announceChange();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function copyShareLink() {
    const url=`${window.location.origin}/shared/paths/${doc.share_token}`;
    try { await navigator.clipboard.writeText(url); setMessage('分享链接已复制。'); }
    catch { window.prompt('复制这个分享链接：',url); }
  }
  if (!doc) return <><ErrorBox message={error}/><div className="empty">正在加载学习路径…</div></>;
  return <>
    <div className="detail-top"><Link to="/paths"><ArrowLeft size={14}/> 返回路径列表</Link><span className={`status-pill ${doc.status==='published'?'succeeded':''}`}>{doc.status==='published'?'已发布':'草稿'}</span></div>
    <PageTitle eyebrow="PATH EDITOR" title="编辑研究学习路径" actions={<div className="actions">
      <button onClick={save} disabled={busy}><Save size={15}/>{busy?'处理中…':'保存路径'}</button>
      {doc.status==='draft'?<button className="ghost" onClick={publish} disabled={busy}><Share2 size={15}/>发布分享</button>:<>
        <button className="ghost" onClick={copyShareLink}><Copy size={15}/>复制分享链接</button>
        <a className="button ghost" href={`/shared/paths/${doc.share_token}`} target="_blank" rel="noreferrer"><ExternalLink size={15}/>预览分享页</a>
        <button className="ghost danger" onClick={unpublish} disabled={busy}>停止分享</button>
      </>}
    </div>}>发布后内容仍会随保存更新；停止分享会使旧链接立即失效。</PageTitle>
    <ErrorBox message={error}/>{message && <div className="success-box">{message}</div>}
    <div className="path-editor-layout">
      <section className="panel path-overview">
        <Field label="路径标题"><input aria-label="路径标题" value={doc.title} onChange={e=>change('title',e.target.value)}/></Field>
        <Field label="学习目标（发布必填）"><textarea aria-label="学习目标" rows={4} value={doc.objective_md} onChange={e=>change('objective_md',e.target.value)} placeholder="完成这条路径后，学习者能够解释、实现或验证什么？"/></Field>
        <Field label="路径说明"><textarea aria-label="路径说明" rows={5} value={doc.description_md} onChange={e=>change('description_md',e.target.value)} placeholder="适用对象、前置知识和使用方式；支持 Markdown。"/></Field>
        <Field label="整条路径的完成条件（发布必填）"><textarea aria-label="路径完成条件" rows={5} value={doc.completion_criteria_md} onChange={e=>change('completion_criteria_md',e.target.value)} placeholder="例如：能够独立讲解关键概念，并完成一次可复现的小实验。"/></Field>
        <DeleteButton kind="path" id={doc.id} title={doc.title} label="删除学习路径" beforeDelete={async()=>true} onDeleted={()=>navigate('/paths')}/>
      </section>
      <section className="path-steps">
        <div className="panel path-step-toolbar"><div><span className="eyebrow">ORDERED STEPS</span><h2>学习步骤</h2></div><div className="path-add-step">
          <select aria-label="选择知识对象" value={selectedObject} onChange={e=>setSelectedObject(e.target.value)}>{objects.map(object=><option value={object.id} key={object.id}>{object.title}</option>)}</select>
          <button type="button" onClick={addObjectStep} disabled={!selectedObject}><Plus size={14}/>加入知识对象</button>
          <button type="button" className="ghost" onClick={addIndependentStep}><Plus size={14}/>独立步骤</button>
        </div></div>
        {doc.steps.map((step,index)=><article className="panel path-step-card" key={step.id || index}>
          <div className="path-step-heading"><span className="path-number">{index+1}</span><div><span className="eyebrow">STEP {index+1}</span><strong>{step.title || '未命名步骤'}</strong></div><div className="actions">
            <button type="button" className="icon-button" aria-label={`上移步骤 ${index+1}`} disabled={index===0} onClick={()=>move(index,-1)}><ChevronUp size={16}/></button>
            <button type="button" className="icon-button" aria-label={`下移步骤 ${index+1}`} disabled={index===doc.steps.length-1} onClick={()=>move(index,1)}><ChevronDown size={16}/></button>
            <button type="button" className="ghost danger" onClick={()=>remove(index)}>移除</button>
          </div></div>
          <div className="form-grid">
            <Field label="步骤标题"><input aria-label={`步骤 ${index+1} 标题`} value={step.title} onChange={e=>changeStep(index,'title',e.target.value)}/></Field>
            <Field label="关联知识（可选）"><select aria-label={`步骤 ${index+1} 关联知识`} value={step.object_id || ''} onChange={e=>changeStep(index,'object_id',e.target.value || null)}><option value="">不关联知识对象</option>{objects.map(object=><option value={object.id} key={object.id}>{object.title}</option>)}</select></Field>
          </div>
          <Field label="讲解与行动提示"><textarea aria-label={`步骤 ${index+1} 讲解提示`} rows={4} value={step.guidance_md} onChange={e=>changeStep(index,'guidance_md',e.target.value)} placeholder="先读什么、关注什么、要完成什么操作；支持 Markdown。"/></Field>
          <div className="form-grid"><Field label="本步骤完成条件（发布必填）"><textarea aria-label={`步骤 ${index+1} 完成条件`} rows={3} value={step.completion_criteria_md} onChange={e=>changeStep(index,'completion_criteria_md',e.target.value)}/></Field>
            <Field label="预计用时（分钟）"><input aria-label={`步骤 ${index+1} 预计用时`} type="number" min="0" value={step.estimated_minutes ?? ''} onChange={e=>changeStep(index,'estimated_minutes',e.target.value)}/></Field></div>
        </article>)}
        {!doc.steps.length && <Empty title="还没有学习步骤">从现有知识库加入资料，或创建一个不依赖知识对象的行动步骤。</Empty>}
      </section>
    </div>
  </>;
}

export function SharedLearningPath() {
  const {token}=useParams();
  const [doc,setDoc]=useState(null), [error,setError]=useState('');
  useEffect(()=>{api(`/shared/learning-paths/${token}`).then(setDoc).catch(e=>setError(e.message));},[token]);
  if (error) return <main className="public-path-shell"><ErrorBox message={error}/><p>请联系分享者确认链接是否仍然有效。</p></main>;
  if (!doc) return <main className="public-path-shell"><p>正在加载学习路径…</p></main>;
  const total=doc.steps.reduce((sum,step)=>sum+(step.estimated_minutes || 0),0);
  return <main className="public-path-shell">
    <header className="public-path-header"><span className="eyebrow">SHARED RESEARCH LEARNING PATH</span><h1>{doc.title}</h1><p>{doc.steps.length} 个步骤{total?` · 预计 ${total} 分钟`:''}</p></header>
    <section className="panel public-path-intro"><h2>学习目标</h2><Markdown>{doc.objective_md}</Markdown>{doc.description_md && <><h2>路径说明</h2><Markdown>{doc.description_md}</Markdown></>}</section>
    <ol className="public-path-steps">{doc.steps.map((step,index)=><li className="panel" key={step.id}>
      <span className="path-number">{index+1}</span><div className="public-step-content"><h2>{step.title}</h2>
      {step.estimated_minutes!=null && <p className="muted"><Clock size={13}/>预计 {step.estimated_minutes} 分钟</p>}
      {step.object_available && <div className="linked-object"><Badge kind={step.object_kind}/><strong>{step.object_title}</strong>{step.object_summary && <p>{step.object_summary}</p>}</div>}
      {step.guidance_md && <><h3>讲解与行动提示</h3><Markdown>{step.guidance_md}</Markdown></>}
      <div className="completion-box"><h3>完成条件</h3><Markdown>{step.completion_criteria_md}</Markdown></div></div>
    </li>)}</ol>
    <section className="panel path-finish"><h2>整条路径的完成条件</h2><Markdown>{doc.completion_criteria_md}</Markdown></section>
    <footer className="public-path-footer">由“知行 · Knowledge in Motion”学习路径生成</footer>
  </main>;
}
