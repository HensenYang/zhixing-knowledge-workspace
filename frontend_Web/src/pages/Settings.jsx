import { useEffect, useState } from 'react';
import { Download, Upload, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { announceChange } from '../components/RecordActions';
import { PageTitle, ErrorBox } from '../components/shared';
export default function Settings() {
  const [health, setHealth] = useState(null),
    [file, setFile] = useState(null),
    [preview, setPreview] = useState(null),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false),
    [job, setJob] = useState(null);
  const check = () => api('/health').then(setHealth).catch(e => setError(e.message));
  useEffect(() => {
    check();
    // Pick up a restore that is still running (for example after navigating away and back).
    api('/jobs?kind=import&limit=1').then(([latest]) => {
      if (latest && ['queued', 'running'].includes(latest.status)) setJob(latest);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    const timer = setTimeout(() => api(`/jobs/${job.id}`).then(next => {
      setJob(next);
      if (next.status === 'succeeded') {
        setMessage('恢复完成，知识内容、关系、画布、日志与附件已写入。');
        announceChange();
      }
      if (next.status === 'failed') setError(next.error || '恢复失败，现有数据未被修改。');
    }).catch(e => setError(e.message)), 800);
    return () => clearTimeout(timer);
  }, [job]);
  async function inspect(file) {
    setFile(file);
    setPreview(null);
    setMessage('');
    setError('');
    if (!file) return;
    const data = new FormData();
    data.append('file', file);
    try {
      setPreview(await api('/import?dry_run=true', {
        method: 'POST',
        body: data
      }));
    } catch (e) {
      setError(e.message);
    }
  }
  async function restore() {
    setBusy(true);
    try {
      const data = new FormData();
      data.append('file', file);
      const started = await api('/import?dry_run=false', {
        method: 'POST',
        body: data
      });
      setJob({ id: started.job_id, status: 'queued', progress: 0, message: '排队中' });
      setMessage('');
      setPreview(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <><PageTitle eyebrow="LOCAL WORKSPACE" title="环境与备份">你的知识保存在本机 PostgreSQL，附件保存在研究目录。</PageTitle><ErrorBox message={error} />{message && <div className="success-box">{message}</div>}{job && ['queued', 'running'].includes(job.status) && <div className="panel job-progress" role="status" aria-live="polite"><div className="job-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress}><i style={{ width: `${job.progress}%` }} /></div><span>正在恢复备份：{job.message || '处理中'} · {job.progress}%。可以离开此页，恢复会在后台继续。</span></div>}<div className="settings-grid"><section className="panel"><div className="section-heading"><h2>运行环境</h2><button className="ghost" onClick={check}><RefreshCw size={14} />重新检查</button></div><dl className="environment-list"><div><dt>访问方式</dt><dd>本地浏览器 · 个人使用</dd></div><div><dt>后端服务</dt><dd>{health?.service === 'ready' ? '已运行' : '检查中'}</dd></div><div><dt>PostgreSQL</dt><dd>{health?.database === 'ready' ? '已连接' : '尚未连接'}</dd></div><div><dt>数据结构版本</dt><dd>{health?.schema_version || '—'}</dd></div><div><dt>实验方式</dt><dd>RTX 4090 · 本机与仿真</dd></div><div><dt>学习节奏</dt><dd>按阶段完成条件推进</dd></div></dl>{health?.message && <div className="info-note">{health.message}</div>}<p className="muted">正式数据库初始化：在本机 PowerShell 运行 scripts/setup_database.ps1，密码只在本机输入。</p></section><section className="panel"><h2>完整备份</h2><p>导出包含所有知识对象、关系及证据、画布布局、修订、学习记录、实验配置与资料附件。</p><a className="button" href="/api/export"><Download size={16} />下载备份 ZIP</a><div className="info-note">模型权重、数据集和外部实验产物只导出路径与版本清单。请另外备份这些大型文件。</div><h3 className="mt-6">恢复备份</h3><p className="muted">先检查内容与 ID 冲突，再写入。已有记录不会被覆盖。</p><label className="file-upload"><Upload size={18} /><span>{file?.name || '选择备份 ZIP'}</span><input type="file" accept=".zip" onChange={e => inspect(e.target.files[0])} /></label>{preview && <div className="import-preview"><h3>备份检查结果</h3><p>知识对象 {preview.counts.objects} · 关系 {preview.counts.relations} · 画布 {preview.counts.canvases} · 日志 {preview.counts.learning_sessions} · 附件 {preview.counts.attachments}</p>{Object.keys(preview.conflicts).length ? <ErrorBox message={`存在 ID 冲突：${Object.entries(preview.conflicts).map(([k, v]) => `${k} ${v}`).join('，')}。请使用空数据库恢复。`} /> : <button onClick={restore} disabled={busy}>{busy ? '恢复中…' : '恢复已检查的备份'}</button>}</div>}</section></div></>;
}
