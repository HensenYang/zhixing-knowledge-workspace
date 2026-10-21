import { t, msg, useLanguage, dateLocale, translateMessage } from "../i18n";
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Link } from "react-router-dom";
function MarkdownLink({
  href,
  children,
  node,
  ...props
}) {
  useLanguage(); // Local reading links keep the router history, so readers can return to their task.
  if (href) {
    try {
      const url = new URL(href, window.location.href);
      if (url.origin === window.location.origin && /^\/(knowledge|canvases|paths|graph|timeline|experiments|settings|trash)(\/|$)/.test(url.pathname)) {
        return <Link {...props} to={url.pathname + url.search + url.hash}>{children}</Link>;
      }
    } catch {/* Keep malformed or non-web links as ordinary anchors. */}
  }
  return <a {...props} href={href}>{children}</a>;
}
export const KINDS = {
  concept: msg("概念"),
  resource: msg("资料"),
  repository: msg("代码仓库"),
  model: msg("模型"),
  dataset: msg("数据集"),
  benchmark: msg("评测"),
  experiment: msg("实验"),
  question: msg("问题"),
  task: msg("任务")
};
export const RELATIONS = {
  depends_on: msg("依赖"),
  implements: msg("实现"),
  uses: msg("使用"),
  evaluates: msg("relation.evaluates"),
  supports: msg("支持"),
  questions: msg("质疑"),
  compares_with: msg("比较"),
  related_to: msg("相关")
};
export const COLORS = {
  concept: "#5d9380",
  resource: "#8b87bc",
  repository: "#7597b6",
  model: "#c4945e",
  dataset: "#6b9fa0",
  benchmark: "#a6a15c",
  experiment: "#ca8169",
  question: "#ac7d98",
  task: "#819c5f"
};
export function Markdown({
  children
}) {
  useLanguage();
  return <div className="markdown"><ReactMarkdown components={{
      a: MarkdownLink
    }} remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{children || t("*尚未添加内容*")}</ReactMarkdown></div>;
}
export function Badge({
  kind
}) {
  useLanguage();
  return <span className="badge" style={{
    color: COLORS[kind],
    background: `${COLORS[kind]}16`
  }}>{t(KINDS[kind]) || kind}</span>;
}
export function Field({
  label,
  children
}) {
  useLanguage();
  return <label className="field"><span>{t(label)}</span>{children}</label>;
}
export function ErrorBox({
  message
}) {
  useLanguage();
  return message ? <div role="alert" className="error-box">{translateMessage(message)}</div> : null;
}
export function Empty({
  title = t("这里还没有记录"),
  children
}) {
  useLanguage();
  return <div className="empty"><span className="empty-symbol">◇</span><h3>{title}</h3><p>{children || t("从一个问题或一份资料开始，逐步建立连接。")}</p></div>;
}
export function PageTitle({
  eyebrow,
  title,
  children,
  actions
}) {
  useLanguage();
  return <div className="page-title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{children && <p>{children}</p>}</div><div className="actions">{actions}</div></div>;
}
export function CollapsiblePanel({title, children, actions, className = '', defaultCollapsed = false}) {
  useLanguage();
  const [collapsed, setCollapsed] = React.useState(defaultCollapsed);
  return <section aria-label={title} className={`panel collapsible-panel ${collapsed ? 'collapsed' : ''} ${className}`.trim()}>
    <div className="section-heading collapsible-heading"><h3>{title}</h3><div className="actions">{actions}<button type="button" className="ghost collapse-button" aria-expanded={!collapsed} aria-label={collapsed ? t("展开{title}", {title}) : t("折叠{title}", {title})} onClick={() => setCollapsed(value => !value)}>{collapsed ? t("展开") : t("收起")}</button></div></div>
    <div className="collapsible-content" hidden={collapsed}>{children}</div>
  </section>;
}
export function SelectKind({
  value,
  onChange
}) {
  useLanguage();
  return <select value={value} onChange={onChange}>{Object.entries(KINDS).map(([id, label]) => <option key={id} value={id}>{t(label)}</option>)}</select>;
}
export function DateText({
  value
}) {
  useLanguage();
  return <time>{value ? new Date(value).toLocaleString(dateLocale()) : ""}</time>;
}
