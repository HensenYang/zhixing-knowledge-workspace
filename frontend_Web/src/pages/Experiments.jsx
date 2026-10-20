import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, FlaskConical } from 'lucide-react';
import { api, write } from '../services/api';
import { PageTitle, Field, ErrorBox, Empty, DateText, Markdown } from '../components/shared';
import { DeleteButton, useWorkspaceChanges } from '../components/RecordActions';
const blank = {
  experiment_id: '',
  status: 'planned',
  hypothesis_md: '',
  command: '',
  git_commit: '',
  weight_version: '',
  dataset_version: '',
  config: {},
  environment: {},
  metrics: {},
  seed: null,
  result_md: '',
  failure_md: '',
  artifacts: []
};
export default function Experiments() {
  const [objects, setObjects] = useState([]),
    [runs, setRuns] = useState([]),
    [form, setForm] = useState(null),
    [jsonFields, setJsonFields] = useState({}),
    [artifactPath, setArtifactPath] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const load = () => Promise.all([api('/objects?kind=experiment&archived=true'), api('/runs')]).then(([o, r]) => {
    setObjects(o);
    setRuns(r);
  }).catch(e => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useWorkspaceChanges(load);
  function edit(run) {
    setForm({
      ...run
    });
    setJsonFields(Object.fromEntries(['config', 'environment', 'metrics'].map(k => [k, JSON.stringify(run[k], null, 2)])));
    setArtifactPath(run.artifacts?.[0]?.location || '');
    setError('');
  }
  const change = (key, value) => setForm({
    ...form,
    [key]: value
  });
  async function newExperiment() {
    const title = window.prompt('实验主题名称');
    if (!title) return;
    try {
      const o = await write('/objects', {
        kind: 'experiment',
        title
      });
      await load();
      edit({
        ...blank,
        experiment_id: o.id
      });
    } catch (e) {
      setError(e.message);
    }
  }
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = {
        ...form
      };
      for (const k of ['config', 'environment', 'metrics']) {
        data[k] = JSON.parse(jsonFields[k]);
        if (!data[k] || typeof data[k] !== 'object' || Array.isArray(data[k])) throw Error(`${k} 必须为 JSON 对象。`);
      }
      data.artifacts = [...(artifactPath ? [{
        ...form.artifacts?.[0],
        artifact_type: form.artifacts?.[0]?.artifact_type || 'external',
        sha256: artifactPath === form.artifacts?.[0]?.location ? form.artifacts?.[0]?.sha256 : null,
        location: artifactPath
      }] : []), ...(form.artifacts || []).slice(1)];
      await write(form.id ? `/runs/${form.id}` : '/runs', data, form.id ? 'PATCH' : 'POST');
      setForm(null);
      setError('');
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <><PageTitle eyebrow="REPRODUCIBLE EXPERIMENTS" title="实验与复现" actions={<><button className="ghost" onClick={newExperiment}>新建实验主题</button><button disabled={!objects.length} onClick={() => edit({
        ...blank,
        experiment_id: objects[0].id
      })}><Plus size={16} />记录运行</button></>}>将假设、代码版本、配置与结果保存在一起。</PageTitle><ErrorBox message={error} />{form && <form className="panel run-form" onSubmit={save}><h2>{form.id ? '修改运行记录' : '新的运行记录'}</h2><div className="form-grid"><Field label="关联实验"><select value={form.experiment_id} onChange={e => change('experiment_id', e.target.value)}>{objects.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}</select></Field><Field label="状态"><select value={form.status} onChange={e => change('status', e.target.value)}>{Object.entries({
              planned: '待运行',
              running: '运行中',
              succeeded: '已完成',
              failed: '失败',
              cancelled: '取消'
            }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field></div><Field label="假设与对照"><textarea value={form.hypothesis_md} onChange={e => change('hypothesis_md', e.target.value)} rows={3} /></Field><Field label="启动命令"><textarea className="code-input" value={form.command} onChange={e => change('command', e.target.value)} rows={2} /></Field><div className="form-grid">{[['git_commit', '代码 commit'], ['weight_version', '权重版本'], ['dataset_version', '数据版本']].map(([k, v]) => <Field key={k} label={v}><input value={form[k] || ''} onChange={e => change(k, e.target.value)} /></Field>)}<Field label="随机种子（可选）"><input type="number" value={form.seed ?? ''} onChange={e => change('seed', e.target.value === '' ? null : Number(e.target.value))} /></Field></div><div className="form-grid">{[['config', '配置 JSON'], ['environment', '环境 JSON'], ['metrics', '指标 JSON']].map(([k, v]) => <Field key={k} label={v}><textarea className="code-input" rows={5} value={jsonFields[k]} onChange={e => setJsonFields({
            ...jsonFields,
            [k]: e.target.value
          })} /></Field>)}</div><div className="form-grid"><Field label="结果与结论"><textarea rows={4} value={form.result_md} onChange={e => change('result_md', e.target.value)} /></Field><Field label="失败原因"><textarea rows={4} value={form.failure_md} onChange={e => change('failure_md', e.target.value)} /></Field></div><Field label="外部产物路径／链接"><input value={artifactPath} onChange={e => setArtifactPath(e.target.value)} placeholder="大型产物只记录路径，备份不复制权重和数据集。" /></Field><div className="actions"><button disabled={busy}>保存运行记录</button><button type="button" className="ghost" onClick={() => setForm(null)}>收起</button></div></form>}<div className="experiment-grid">{objects.map(o => <section className="panel" key={o.id}><div className="section-heading"><div><FlaskConical size={19} /><h2>{o.title}</h2></div><Link className="text-link" to={`/knowledge/${o.id}`}>修改实验笔记 ↗</Link><DeleteButton kind="object" id={o.id} title={o.title} label="删除主题" onDeleted={() => {
            setForm(null);
            load();
          }} /></div>{runs.filter(r => r.experiment_id === o.id).map(r => <div className="run-card" key={r.id}><div className="section-heading"><span className={`status-pill ${r.status}`}>{{
                planned: '待运行',
                running: '运行中',
                succeeded: '已完成',
                failed: '失败',
                cancelled: '取消'
              }[r.status]}</span><div className="actions"><button className="ghost" onClick={() => edit(r)}>修改</button><DeleteButton kind="run" id={r.id} title={r.hypothesis_md || o.title} onDeleted={() => {
                setForm(null);
                load();
              }} /></div></div><DateText value={r.created_at} /><Markdown>{r.result_md || r.failure_md || r.hypothesis_md}</Markdown>{Object.keys(r.metrics).length > 0 && <div className="metrics">{Object.entries(r.metrics).map(([k, v]) => <span key={k}>{k}<strong>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</strong></span>)}</div>}<details><summary>命令与版本</summary><pre>{r.command}</pre><p>commit: {r.git_commit || '未记录'}<br />权重: {r.weight_version || '未记录'}<br />数据: {r.dataset_version || '未记录'}</p></details></div>)}<button className="ghost" onClick={() => edit({
          ...blank,
          experiment_id: o.id
        })}><Plus size={14} />为此实验记录一次运行</button></section>)}</div>{!objects.length && !error && <Empty title="先定义一个可验证的问题">新建实验主题，再记录实际运行；待运行与实际结果会明确区分。</Empty>}</>;
}
