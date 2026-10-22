import { t, msg, useLanguage, translateMessage } from "../i18n";
import LLMSettings from '../components/LLMSettings';
import { useEffect, useState } from 'react';
import { Download, Upload, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { announceChange } from '../components/RecordActions';
import { PageTitle, ErrorBox } from '../components/shared';
export default function Settings() {
  useLanguage();
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
        setMessage(msg("恢复完成，知识内容、关系、画布、日志与附件已写入。"));
        announceChange();
      }
      if (next.status === 'failed') setError(next.error || msg("恢复失败，现有数据未被修改。"));
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
      setJob({
        id: started.job_id,
        status: 'queued',
        progress: 0,
        message: msg("排队中")
      });
      setMessage('');
      setPreview(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <><PageTitle eyebrow={t("LOCAL WORKSPACE")} title={t("环境与备份")}>{t("你的知识保存在本机 PostgreSQL，附件保存在研究目录。")}</PageTitle><ErrorBox message={error} />{message && <div className="success-box">{translateMessage(message)}</div>}{job && ['queued', 'running'].includes(job.status) && <div className="panel job-progress" role="status" aria-live="polite"><div className="job-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress}><i style={{
          width: `${job.progress}%`
        }} /></div><span>{t('正在恢复备份：{message} · {progress}%。可以离开此页，恢复会在后台继续。',{message:translateMessage(job.message || msg('处理中')),progress:job.progress})}</span></div>}<div className="settings-grid"><section className="panel"><div className="section-heading"><h2>{t("运行环境")}</h2><button className="ghost" onClick={check}><RefreshCw size={14} />{t("重新检查")}</button></div><dl className="environment-list"><div><dt>{t("访问方式")}</dt><dd>{t("本地浏览器 \xB7 个人使用")}</dd></div><div><dt>{t("后端服务")}</dt><dd>{health?.service === 'ready' ? msg("已运行") : msg("检查中")}</dd></div><div><dt>PostgreSQL</dt><dd>{health?.database === 'ready' ? msg("已连接") : msg("尚未连接")}</dd></div><div><dt>{t("数据结构版本")}</dt><dd>{health?.schema_version || '—'}</dd></div><div><dt>{t("实验方式")}</dt><dd>{t("RTX 4090 \xB7 本机与仿真")}</dd></div><div><dt>{t("学习节奏")}</dt><dd>{t("按阶段完成条件推进")}</dd></div></dl>{health?.message && <div className="info-note">{translateMessage(health.message)}</div>}<p className="muted">{t("正式数据库初始化：在本机 PowerShell 运行 scripts/setup_database.ps1，密码只在本机输入。")}</p></section><section className="panel"><h2>{t("完整备份")}</h2><p>{t("导出包含所有知识对象、关系及证据、画布布局、修订、学习记录、实验配置与资料附件。")}</p><a className="button" href="/api/export"><Download size={16} />{t("下载备份 ZIP")}</a><div className="info-note">{t("模型权重、数据集和外部实验产物只导出路径与版本清单。请另外备份这些大型文件。")}</div><h3 className="mt-6">{t("恢复备份")}</h3><p className="muted">{t("先检查内容与 ID 冲突，再写入。已有记录不会被覆盖。")}</p><label className="file-upload"><Upload size={18} /><span>{file?.name || msg("选择备份 ZIP")}</span><input type="file" accept=".zip" onChange={e => inspect(e.target.files[0])} /></label>{preview && <div className="import-preview"><h3>{t("备份检查结果")}</h3><p>{t('知识对象 {objects} · 关系 {relations} · 画布 {canvases} · 日志 {sessions} · 附件 {attachments}',{objects:preview.counts.objects,relations:preview.counts.relations,canvases:preview.counts.canvases,sessions:preview.counts.learning_sessions,attachments:preview.counts.attachments})}</p>{Object.keys(preview.conflicts).length ? <ErrorBox message={t("存在 ID 冲突：{0}。请使用空数据库恢复。", {
            "0": Object.entries(preview.conflicts).map(([k, v]) => `${k} ${v}`).join('，')
          })} /> : <button onClick={restore} disabled={busy}>{busy ? msg("恢复中…") : msg("恢复已检查的备份")}</button>}</div>}</section><LLMSettings /></div></>;
}
