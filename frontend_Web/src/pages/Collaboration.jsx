import { useEffect,useState } from 'react';
import { Plus,Users } from 'lucide-react';
import { api,write } from '../services/api';
import { DateText,ErrorBox,Field,PageTitle } from '../components/shared';
import { useAuth } from '../contexts/AuthContext';

const roleName={owner:'所有者',editor:'编辑者',reviewer:'审核者',viewer:'查看者'};
export default function Collaboration() {
  const {workspace,user,refresh}=useAuth();
  const [members,setMembers]=useState([]),[events,setEvents]=useState([]),[email,setEmail]=useState(''),[role,setRole]=useState('viewer'),[name,setName]=useState(''),[error,setError]=useState('');
  const load=()=>Promise.all([api(`/workspaces/${workspace.id}/members`),api('/activity')]).then(([m,a])=>{setMembers(m);setEvents(a);setError('')}).catch(e=>setError(e.message));
  useEffect(()=>{if(workspace)load()},[workspace?.id]);
  async function add(e){e.preventDefault();try{await write(`/workspaces/${workspace.id}/members`,{email,role});setEmail('');await load()}catch(e){setError(e.message)}}
  async function create(e){e.preventDefault();try{const w=await write('/workspaces',{name});await refresh();localStorage.setItem('knowledge-workspace-id',w.id);window.location.reload()}catch(e){setError(e.message)}}
  return <><PageTitle eyebrow="TEAM WORKSPACE" title="多人协作"><span>{workspace?.name} · 我的角色：{roleName[workspace?.role]}</span></PageTitle><ErrorBox message={error}/><div className="settings-grid"><section className="panel"><div className="section-heading"><h2><Users size={18}/>成员</h2><span className="status-pill">{members.length} 人</span></div>{members.map(m=><div className="member-row" key={m.id}><span className="avatar">{m.display_name.slice(0,1)}</span><div><strong>{m.display_name}</strong><small>{m.email}</small></div>{workspace?.role==='owner'&&m.id!==user.id?<select value={m.role} onChange={async e=>{await write(`/workspaces/${workspace.id}/members/${m.id}`,{role:e.target.value},'PATCH');load()}}>{Object.entries(roleName).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select>:<span className="status-pill">{roleName[m.role]}</span>}</div>)}{workspace?.role==='owner'&&<form onSubmit={add}><h3>添加已注册成员</h3><Field label="成员邮箱"><input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></Field><Field label="角色"><select value={role} onChange={e=>setRole(e.target.value)}>{Object.entries(roleName).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></Field><button><Plus size={14}/>添加成员</button></form>}</section><section className="panel"><h2>创建新工作区</h2><form onSubmit={create}><Field label="工作区名称"><input required value={name} onChange={e=>setName(e.target.value)} placeholder="例如：机器人学习小组"/></Field><button>创建并切换</button></form><hr/><h2>最近活动</h2><div className="activity-list">{events.map(e=><div key={e.id}><strong>{e.display_name||'已删除用户'}</strong><span>{e.action}</span><DateText value={e.created_at}/></div>)}{!events.length&&<p className="muted">团队操作会记录在这里。</p>}</div></section></div></>;
}
