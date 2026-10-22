import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, apiPage, write } from '../services/api';
import { PageTitle, ErrorBox, Empty, Badge, DateText, RELATIONS } from '../components/shared';
import Pager from '../components/Pager';

const SEVERITY = { error: '错误', warning: '警告', info: '提示' };
const PAGE_SIZE = 20;

function Ref({ item }) {
  return <Link className="health-ref" to={`/knowledge/${item.id}`}>{item.kind && <Badge kind={item.kind} />}{item.title}</Link>;
}

function Finding({ item }) {
  const relation = item.relation;
  return <article className={`panel health-finding ${item.severity}`}>
    <div className="health-finding-head"><span className={`pill health-${item.severity}`}>{SEVERITY[item.severity]}</span><p>{item.message}</p></div>
    {relation && <p className="health-relation"><Ref item={relation.source} /><span>—{RELATIONS[relation.relation_type]}→</span><Ref item={relation.target} /></p>}
    {item.objects.length > 0 && <p className="health-objects">{item.objects.map(o => <Ref key={o.id} item={o} />)}</p>}
    {item.detail.url && /^https?:\/\//.test(item.detail.url) && <p className="muted"><a href={item.detail.url} target="_blank" rel="noreferrer">{item.detail.url} ↗</a>{item.detail.checked_at && <> · 检查于 <DateText value={item.detail.checked_at} /></>}</p>}
    {item.detail.supporters && <div className="health-sides"><div><strong>支持</strong>{item.detail.supporters.map(o => <Ref key={o.id} item={o} />)}</div><div><strong>质疑</strong>{item.detail.questioners.map(o => <Ref key={o.id} item={o} />)}</div></div>}
  </article>;
}

export default function EvidenceHealth() {
  const [summary, setSummary] = useState(null),
    [selected, setSelected] = useState(''),
    [detail, setDetail] = useState(null),
    [offset, setOffset] = useState(0),
    [staleDays, setStaleDays] = useState(180),
    [job, setJob] = useState(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);

  const loadSummary = () => api(`/evidence-health?stale_days=${staleDays}`).then(data => {
    setSummary(data);
    setSelected(current => current || (data.checks.find(c => c.count > 0) || data.checks[0]).id);
    setError('');
  }).catch(e => setError(e.message));
  useEffect(() => { loadSummary(); }, [staleDays]);
  useEffect(() => {
    api('/jobs?kind=link_check&limit=1').then(([latest]) => { if (latest && ['queued', 'running'].includes(latest.status)) setJob(latest); }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!selected) return;
    let alive = true;
    apiPage(`/evidence-health/${selected}?stale_days=${staleDays}&limit=${PAGE_SIZE}&offset=${offset}`).then(({ items }) => {
      if (alive) setDetail(items);
    }).catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [selected, offset, staleDays, summary?.generated_at]);
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    const timer = setTimeout(() => api(`/jobs/${job.id}`).then(next => {
      setJob(next);
      if (next.status === 'succeeded') loadSummary();
      if (next.status === 'failed') setError(next.error || '链接检查失败。');
    }).catch(e => setError(e.message)), 1000);
    return () => clearTimeout(timer);
  }, [job]);

  async function startLinkCheck(force) {
    setBusy(true);
    setError('');
    try {
      const started = await write(`/evidence-health/link-check?force=${force}`, {});
      setJob({ id: started.job_id, status: 'queued', progress: 0, message: '排队中' });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const select = id => {
    if (id === selected) return;   // nothing to reload; clearing the list here would leave it empty
    setSelected(id);
    setOffset(0);
    setDetail(null);
  };
  const running = job && ['queued', 'running'].includes(job.status);
  const coverage = summary?.coverage, links = summary?.links;
  const current = summary?.checks.find(c => c.id === selected);

  return <><PageTitle eyebrow="EVIDENCE HEALTH" title="证据健康">找出知识库里“说得比证据多”的地方：没有证据的关系、打不开的链接、过期的资料、尚未验证的实验声明。</PageTitle>
    <ErrorBox message={error} />
    {summary && <>
      <div className="stats-grid" aria-label="证据概况">
        <div className="stat-card"><strong>{coverage.percent === null ? '—' : `${coverage.percent}%`}</strong><span>证据覆盖率（{coverage.with_evidence} / {coverage.relations} 条关系有证据）</span></div>
        <div className="stat-card"><strong>{coverage.relations ? `${Math.round(100 * coverage.with_locator / coverage.relations)}%` : '—'}</strong><span>有页码／章节定位的关系（{coverage.with_locator} 条）</span></div>
        <div className="stat-card"><strong>{summary.totals.error + summary.totals.warning}</strong><span>需要处理（{summary.totals.error} 错误 · {summary.totals.warning} 警告）</span></div>
        <div className="stat-card"><strong>{links.checked} / {links.distinct_urls}</strong><span>链接已检查（{links.dead} 个失效{links.unclear ? `，${links.unclear} 个无法判断` : ''}）</span></div>
      </div>
      <section className="panel health-toolbar">
        <div className="actions">
          <button disabled={busy || running} onClick={() => startLinkCheck(false)}>{running ? '检查中…' : '检查链接'}</button>
          <button className="ghost" disabled={busy || running} onClick={() => startLinkCheck(true)}>全部重新检查</button>
          <label className="check">资料超过 <select aria-label="过期天数" value={staleDays} onChange={e => { setStaleDays(Number(e.target.value)); setOffset(0); }}>{[90, 180, 365].map(d => <option key={d} value={d}>{d}</option>)}</select> 天未核对视为过期</label>
        </div>
        {running && <div className="job-progress" role="status"><div className="job-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={job.progress}><i style={{ width: `${job.progress}%` }} /></div><span>{job.message || '处理中'} · {job.progress}%</span></div>}
        <p className="muted">链接检查会联网访问笔记和证据里的外部地址（本机和内网地址会被跳过）。{links.last_checked_at ? <>上次检查：<DateText value={links.last_checked_at} />。</> : '尚未检查过。'}</p>
      </section>
      <div className="health-layout">
        <nav className="health-checks" aria-label="检查项">{summary.checks.map(check => <button key={check.id} type="button" className={`health-check ${selected === check.id ? 'active' : ''}`} onClick={() => select(check.id)} aria-current={selected === check.id}>
          <i className={`health-dot ${check.count ? check.severity : 'ok'}`} /><span>{check.title}</span><strong>{check.count}</strong></button>)}</nav>
        <section aria-live="polite">{current && <>
          <div className="panel"><h2>{current.title}</h2><p>{current.description}</p><p className="muted"><strong>怎么处理：</strong>{current.fix}</p></div>
          {detail && detail.findings.map(item => <Finding key={item.key} item={item} />)}
          {detail && !detail.findings.length && <Empty title="这项检查没有发现问题">{current.id === 'dead_links' && !links.checked ? '还没有检查过链接，点“检查链接”开始。' : '继续保持。'}</Empty>}
          {detail && <Pager total={detail.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />}</>}</section>
      </div></>}
    {!summary && !error && <div className="empty">正在检查…</div>}</>;
}
