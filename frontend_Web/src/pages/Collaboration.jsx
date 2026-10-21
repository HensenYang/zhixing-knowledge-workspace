import { useEffect, useState } from 'react';
import { Plus, Users } from 'lucide-react';
import { msg, t, useLanguage } from '../i18n';
import { api, write } from '../services/api';
import { DateText, ErrorBox, Field, PageTitle } from '../components/shared';
import { useAuth } from '../contexts/AuthContext';

const roleName={owner:msg('所有者'),editor:msg('编辑者'),reviewer:msg('审核者'),viewer:msg('查看者')};

export default function Collaboration() {
  useLanguage();
  const {workspace,user,refresh}=useAuth();
  const [members,setMembers]=useState([]);
  const [events,setEvents]=useState([]);
  const [email,setEmail]=useState('');
  const [role,setRole]=useState('viewer');
  const [name,setName]=useState('');
  const [error,setError]=useState('');
  const load=()=>Promise.all([
    api(`/workspaces/${workspace.id}/members`),
    api('/activity')
  ]).then(([memberRows,activityRows])=>{
    setMembers(memberRows);
    setEvents(activityRows);
    setError('');
  }).catch(failure=>setError(failure.message));

  useEffect(()=>{if(workspace) load();},[workspace?.id]);

  async function add(event) {
    event.preventDefault();
    try {
      await write(`/workspaces/${workspace.id}/members`,{email,role});
      setEmail('');
      await load();
    } catch (failure) {
      setError(failure.message);
    }
  }

  async function create(event) {
    event.preventDefault();
    try {
      const created=await write('/workspaces',{name});
      await refresh();
      localStorage.setItem('knowledge-workspace-id',created.id);
      window.location.reload();
    } catch (failure) {
      setError(failure.message);
    }
  }

  return <>
    <PageTitle eyebrow={t('TEAM WORKSPACE')} title={t('多人协作')}>
      <span>{t('{workspace} · 我的角色：{role}',{workspace:workspace?.name,role:t(roleName[workspace?.role])})}</span>
    </PageTitle>
    <ErrorBox message={error}/>
    <div className="settings-grid">
      <section className="panel">
        <div className="section-heading"><h2><Users size={18}/>{t('成员')}</h2><span className="status-pill">{t('{count} 人',{count:members.length})}</span></div>
        {members.map(member=><div className="member-row" key={member.id}>
          <span className="avatar">{member.display_name.slice(0,1)}</span>
          <div><strong>{member.display_name}</strong><small>{member.email}</small></div>
          {workspace?.role==='owner'&&member.id!==user.id
            ? <select value={member.role} onChange={async event=>{
                await write(`/workspaces/${workspace.id}/members/${member.id}`,{role:event.target.value},'PATCH');
                load();
              }}>{Object.entries(roleName).map(([id,label])=><option key={id} value={id}>{t(label)}</option>)}</select>
            : <span className="status-pill">{t(roleName[member.role])}</span>}
        </div>)}
        {workspace?.role==='owner'&&<form onSubmit={add}>
          <h3>{t('添加已注册成员')}</h3>
          <Field label={t('成员邮箱')}><input type="email" required value={email} onChange={event=>setEmail(event.target.value)}/></Field>
          <Field label={t('角色')}><select value={role} onChange={event=>setRole(event.target.value)}>{Object.entries(roleName).map(([id,label])=><option key={id} value={id}>{t(label)}</option>)}</select></Field>
          <button><Plus size={14}/>{t('添加成员')}</button>
        </form>}
      </section>
      <section className="panel">
        <h2>{t('创建新工作区')}</h2>
        <form onSubmit={create}><Field label={t('工作区名称')}><input required value={name} onChange={event=>setName(event.target.value)} placeholder={t('例如：机器人学习小组')}/></Field><button>{t('创建并切换')}</button></form>
        <hr/>
        <h2>{t('最近活动')}</h2>
        <div className="activity-list">{events.map(item=><div key={item.id}><strong>{item.display_name||t('已删除用户')}</strong><span>{item.action}</span><DateText value={item.created_at}/></div>)}{!events.length&&<p className="muted">{t('团队操作会记录在这里。')}</p>}</div>
      </section>
    </div>
  </>;
}
