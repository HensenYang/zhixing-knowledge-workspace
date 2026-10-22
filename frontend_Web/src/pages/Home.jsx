import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Plus, Network, BookOpen, FlaskConical, Route } from 'lucide-react';
import { apiPage, write } from '../services/api';
import { PageTitle, Badge, ErrorBox, DateText, Empty } from '../components/shared';
import { useWorkspaceChanges } from '../components/RecordActions';
import GraphView from '../components/GraphView';
export default function Home() {
  const [totals, setTotals] = useState({ objects: 0, relations: 0, sessions: 0, runs: 0 }),
    [focus, setFocus] = useState([]),
    [recent, setRecent] = useState([]),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const load = () => Promise.all(['/objects?limit=1', '/objects?kind=question&limit=4', '/objects?kind=task&limit=4', '/sessions?limit=3', '/runs?limit=1', '/relations?limit=1'].map(path => apiPage(path))).then(([all, questions, tasks, sessions, runs, relations]) => {
    // Only a few rows and the totals are needed here, however large the library is.
    setTotals({ objects: all.total, relations: relations.total, sessions: sessions.total, runs: runs.total });
    setFocus([...questions.items, ...tasks.items].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 4));
    setRecent(sessions.items);
    setError('');
  }).catch(e => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useWorkspaceChanges(load);
  async function seed() {
    setBusy(true);
    try {
      const definitions = [{
        kind: 'concept',
        title: '世界模型',
        summary: '学习环境如何随动作演化，以及预测如何服务于决策。',
        body_md: '# 当前理解\n\n区分状态预测、视频预测与模型辅助决策。\n\n## 待验证\n\n预测质量如何与任务成功率联系？',
        tags: ['世界模型']
      }, {
        kind: 'model',
        title: 'UnifoLM-WMA-0',
        summary: '后续复现目标：先运行官方交互式世界模型样例。',
        source_url: 'https://github.com/unitreerobotics/unifolm-world-model-action',
        tags: ['世界模型', '待复现']
      }, {
        kind: 'repository',
        title: 'UnifoLM 官方代码仓库',
        source_url: 'https://github.com/unitreerobotics/unifolm-world-model-action',
        summary: '记录 commit、入口脚本、依赖与运行笔记。',
        tags: ['代码']
      }, {
        kind: 'question',
        title: '4090 可运行哪种 UnifoLM 配置？',
        summary: '通过实测记录峰值显存、耗时与输出。',
        tags: ['部署']
      }, {
        kind: 'task',
        title: '第一步：读懂一条机器人轨迹',
        summary: '解释观测字段、动作单位、控制频率与坐标系。',
        metadata: {
          acceptance: '能用自己的话解释样本的输入、输出与单位。'
        },
        tags: ['入门']
      }, {
        kind: 'concept',
        title: 'VLA 与动作表示',
        summary: '视觉和语言如何转换为机器人可执行的动作。',
        tags: ['VLA']
      }, {
        kind: 'experiment',
        title: '部署可行性调查',
        summary: '这是待开展的实验，没有实际模型运行结果。',
        tags: ['部署']
      }];
      const created = [];
      for (const d of definitions) created.push(await write('/objects', d));
      for (const [a, b, type] of [[1, 0, 'depends_on'], [2, 1, 'implements'], [3, 1, 'related_to'], [5, 0, 'compares_with'], [6, 1, 'evaluates']]) await write('/relations', {
        source_id: created[a].id,
        target_id: created[b].id,
        relation_type: type,
        description: '启动示例关系，可按自己的理解修改。'
      });
      await write('/sessions', {
        objective: '建立学习工作台',
        activity_md: '录入首批待学习对象与问题。',
        next_step_md: '先验收知识库，再开始机器人轨迹与模仿学习实验。',
        object_ids: created.map(o => o.id)
      });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <><PageTitle eyebrow="EMBODIED INTELLIGENCE / PERSONAL LAB" title="把理解连接起来" actions={<Link className="button" to="/knowledge"><Plus size={16} />记录新知识</Link>}>从机器人操作出发，沿着 VLA 与世界模型建立你的研究路径。</PageTitle><ErrorBox message={error} /><div className="stats-grid">{[[BookOpen, totals.objects, '知识对象'], [Network, totals.relations, '知识连接'], [Route, totals.sessions, '学习记录'], [FlaskConical, totals.runs, '实验运行']].map(([Icon, count, label]) => <div className="stat-card" key={label}><Icon size={18} /><strong>{count}</strong><span>{label}</span></div>)}</div><div className="home-grid"><section className="panel"><div className="section-heading"><div><span className="eyebrow">YOUR KNOWLEDGE MAP</span><h2>正在生长的知识网络</h2></div><Link to="/graph" className="text-link">探索图谱 <ArrowUpRight size={14} /></Link></div><GraphView refresh={totals.objects + totals.relations} onNode={id => {
          window.location.href = `/knowledge/${id}`;
        }} />{!totals.objects && !error && <div className="seed-action"><button onClick={seed} disabled={busy}>{busy ? '建立中…' : '建立首批学习对象'}</button><p>加入主题、官方仓库和待验证问题，不生成实验结果。</p></div>}</section><section className="panel"><span className="eyebrow">NEXT STEP</span><h2>当前问题与下一步</h2>{focus.map(o => <Link className="focus-row" to={`/knowledge/${o.id}`} key={o.id}><Badge kind={o.kind} /><h3>{o.title}</h3><p>{o.summary}</p></Link>)}{!focus.length && <Empty title="给学习一个问题">记录当前疑问，并写下完成条件。</Empty>}<div className="info-note">按完成条件推进。能解释、能运行、能分析局限，比阅读数量更有意义。</div></section></div><section className="panel recent-panel"><div className="section-heading"><h2>最近的理解与活动</h2><Link className="text-link" to="/timeline">查看轨迹 ↗</Link></div>{recent.map(s => <div className="recent-row" key={s.id}><span className="timeline-dot" /><div><h3>{s.objective}</h3><p>{s.understanding_change_md || s.activity_md}</p></div><DateText value={s.occurred_at} /></div>)}{!totals.sessions && <p className="muted">阅读或实验结束后，记录理解变化与下一步。</p>}</section></>;
}
