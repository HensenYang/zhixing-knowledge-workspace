import { useState } from 'react';
import { t, useLanguage } from '../i18n';
import { ErrorBox, Field } from './shared';
import { useAuth } from '../contexts/AuthContext';

export default function AuthScreen() {
  useLanguage();
  const {authenticate}=useAuth();
  const [mode,setMode]=useState('login');
  const [form,setForm]=useState({email:'',display_name:'',password:''});
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('');
    try { await authenticate(mode,form); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <main className="auth-shell"><section className="panel auth-card">
    <span className="eyebrow">{t('KNOWLEDGE IN MOTION')}</span><h1>{t('知行协作空间')}</h1>
    <p>{mode==='login'?t('登录后继续团队研究。'):t('创建首个账号时会接管当前本地知识空间。')}</p>
    <ErrorBox message={error}/><form onSubmit={submit}>
      {mode==='register'&&<Field label={t('显示名称')}><input required value={form.display_name} onChange={e=>setForm({...form,display_name:e.target.value})}/></Field>}
      <Field label={t('邮箱')}><input type="email" required autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></Field>
      <Field label={t('密码（至少 8 位）')}><input type="password" required minLength="8" autoComplete={mode==='login'?'current-password':'new-password'} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></Field>
      <button disabled={busy}>{busy?t('处理中…'):mode==='login'?t('登录'):t('创建账号')}</button>
      <button type="button" className="ghost" onClick={()=>{setMode(mode==='login'?'register':'login');setError('')}}>{mode==='login'?t('首次使用？创建账号'):t('已有账号？登录')}</button>
    </form>
  </section></main>;
}
