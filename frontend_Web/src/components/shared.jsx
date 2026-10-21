import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Link } from 'react-router-dom';
function MarkdownLink({ href, children, node, ...props }) {
  // Local reading links keep the router history, so readers can return to their task.
  if (href) {
    try {
      const url = new URL(href, window.location.href);
      if (url.origin === window.location.origin && /^\/(knowledge|canvases|paths|graph|timeline|experiments|settings|trash)(\/|$)/.test(url.pathname)) {
        return <Link {...props} to={url.pathname + url.search + url.hash}>{children}</Link>;
      }
    } catch { /* Keep malformed or non-web links as ordinary anchors. */ }
  }
  return <a {...props} href={href}>{children}</a>;
}
export const KINDS = {
  concept: '概念',
  resource: '资料',
  repository: '代码仓库',
  model: '模型',
  dataset: '数据集',
  benchmark: '评测',
  experiment: '实验',
  question: '问题',
  task: '任务'
};
export const RELATIONS = {
  depends_on: '依赖',
  implements: '实现',
  uses: '使用',
  evaluates: '评测',
  supports: '支持',
  questions: '质疑',
  compares_with: '比较',
  related_to: '相关'
};
export const COLORS = {
  concept: '#5d9380',
  resource: '#8b87bc',
  repository: '#7597b6',
  model: '#c4945e',
  dataset: '#6b9fa0',
  benchmark: '#a6a15c',
  experiment: '#ca8169',
  question: '#ac7d98',
  task: '#819c5f'
};
export function Markdown({
  children
}) {
  return <div className="markdown"><ReactMarkdown components={{a: MarkdownLink}} remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{children || '*尚未添加内容*'}</ReactMarkdown></div>;
}
export function Badge({
  kind
}) {
  return <span className="badge" style={{
    color: COLORS[kind],
    background: `${COLORS[kind]}16`
  }}>{KINDS[kind] || kind}</span>;
}
export function Field({
  label,
  children
}) {
  return <label className="field"><span>{label}</span>{children}</label>;
}
export function ErrorBox({
  message
}) {
  return message ? <div role="alert" className="error-box">{message}</div> : null;
}
export function Empty({
  title = '这里还没有记录',
  children
}) {
  return <div className="empty"><span className="empty-symbol">◇</span><h3>{title}</h3><p>{children || '从一个问题或一份资料开始，逐步建立连接。'}</p></div>;
}
export function PageTitle({
  eyebrow,
  title,
  children,
  actions
}) {
  return <div className="page-title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{children && <p>{children}</p>}</div><div className="actions">{actions}</div></div>;
}
export function CollapsiblePanel({title, children, actions, className = '', defaultCollapsed = false}) {
  const [collapsed,setCollapsed] = React.useState(defaultCollapsed);
  return <section className={`panel collapsible-panel ${collapsed ? 'collapsed' : ''} ${className}`.trim()}>
    <div className="section-heading collapsible-heading"><h3>{title}</h3><div className="actions">{actions}<button type="button" className="ghost collapse-button" aria-expanded={!collapsed} aria-label={`${collapsed ? '展开' : '折叠'}${title}`} onClick={() => setCollapsed(value => !value)}>{collapsed ? '展开' : '收起'}</button></div></div>
    <div className="collapsible-content" hidden={collapsed}>{children}</div>
  </section>;
}
export function SelectKind({
  value,
  onChange
}) {
  return <select value={value} onChange={onChange}>{Object.entries(KINDS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>;
}
export function DateText({
  value
}) {
  return <time>{value ? new Date(value).toLocaleString('zh-CN') : ''}</time>;
}
