import { useEffect,useState } from 'react';
import { MessageSquare,ShieldCheck } from 'lucide-react';
import { msg, t, useLanguage } from '../i18n';
import { api,write } from '../services/api';
import { DateText,ErrorBox } from './shared';
import { useAuth } from '../contexts/AuthContext';

export default function CollaborationPanel({targetType,targetId,version}) {
  useLanguage();
  const {workspace}=useAuth();
  const [comments,setComments]=useState([]),[reviews,setReviews]=useState([]),[body,setBody]=useState(''),[note,setNote]=useState(''),[error,setError]=useState('');
  const load=()=>Promise.all([
    api(`/comments?target_type=${targetType}&target_id=${targetId}`),
    api(`/reviews?target_type=${targetType}&target_id=${targetId}`)
  ]).then(([c,r])=>{setComments(c);setReviews(r);setError('')}).catch(e=>setError(e.message));
  useEffect(()=>{load()},[targetType,targetId,version]);
  async function addComment(e) {
    e.preventDefault();
    try { await write('/comments',{target_type:targetType,target_id:targetId,body}); setBody(''); await load(); }
    catch(e){setError(e.message)}
  }
  async function requestReview() {
    try { await write('/reviews',{target_type:targetType,target_id:targetId,target_version:version,note}); setNote(''); await load(); }
    catch(e){setError(e.message)}
  }
  async function decide(id,status) {
    try { await write(`/reviews/${id}`,{status,note:''},'PATCH'); await load(); }
    catch(e){setError(e.message)}
  }
  const reviewStatus={pending:msg('待审核'),approved:msg('已通过'),changes_requested:msg('需修改')};
  return <section className="panel collaboration-panel"><div className="section-heading"><h3><MessageSquare size={15}/>{t('团队讨论')}</h3><span className="status-pill">{t('{count} 条开放',{count:comments.filter(c=>!c.resolved_at).length})}</span></div>
    <ErrorBox message={error}/><div className="comment-list">{comments.map(c=><article className={c.resolved_at?'resolved':''} key={c.id}><strong>{c.display_name}</strong><DateText value={c.created_at}/><p>{c.body}</p><button className="ghost" onClick={async()=>{await write(`/comments/${c.id}/resolve`,{});load()}}>{c.resolved_at?t('重新打开'):t('标为已解决')}</button></article>)}</div>
    <form onSubmit={addComment}><textarea required rows="3" value={body} onChange={e=>setBody(e.target.value)} placeholder={t('提出问题、补充证据或 @协作者…')}/><button>{t('发表评论')}</button></form>
    <hr/><div className="section-heading"><h3><ShieldCheck size={15}/>{t('版本审核')}</h3></div>
    {reviews.map(r=><article className="review-row" key={r.id}><strong>{t('版本 {version} · {status}',{version:r.target_version,status:t(reviewStatus[r.status])})}</strong><small>{r.requested_by_name} · <DateText value={r.created_at}/></small>{r.note&&<p>{r.note}</p>}{r.status==='pending'&&['owner','reviewer'].includes(workspace?.role)&&<div className="actions"><button onClick={()=>decide(r.id,'approved')}>{t('通过')}</button><button className="ghost" onClick={()=>decide(r.id,'changes_requested')}>{t('要求修改')}</button></div>}</article>)}
    {['owner','editor'].includes(workspace?.role)&&<div className="review-submit"><textarea rows="2" value={note} onChange={e=>setNote(e.target.value)} placeholder={t('给审核者的说明（可选）')}/><button className="ghost" onClick={requestReview}>{t('提交当前版本审核')}</button></div>}
  </section>;
}
