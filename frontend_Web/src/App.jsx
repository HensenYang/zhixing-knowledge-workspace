import { t, msg, useLanguage } from "./i18n";
import { useEffect, useState } from "react";
import { NavLink, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, BookOpen, Network, PanelsTopLeft, Route as RouteIcon, FlaskConical, Settings as SettingsIcon, Search, Menu, Leaf, Archive as ArchiveIcon, Upload, ListOrdered } from "lucide-react";
import { api } from "./services/api";
import Home from "./pages/Home";
import LanguageSwitch from "./components/LanguageSwitch";
import Trash from "./pages/Trash";
import { TrashNotice } from "./components/RecordActions";
import { KnowledgeList, KnowledgeDetail } from "./pages/Knowledge";
import Graph from "./pages/Graph";
import { CanvasList, CanvasEditor } from "./pages/Canvas";
import Timeline from "./pages/Timeline";
import Experiments from "./pages/Experiments";
import Settings from "./pages/Settings";
import Imports from "./pages/Imports";
import { LearningPathList, LearningPathEditor, SharedLearningPath } from "./pages/LearningPaths";
const navigation = [["/", LayoutDashboard, msg("工作台")], ["/knowledge", BookOpen, msg("知识与资料")], ["/imports", Upload, msg("资料导入")], ["/paths", ListOrdered, msg("研究学习路径")], ["/graph", Network, msg("知识图谱")], ["/canvases", PanelsTopLeft, msg("自由画布")], ["/timeline", RouteIcon, msg("学习轨迹")], ["/experiments", FlaskConical, msg("实验与复现")], ["/trash", ArchiveIcon, msg("回收站")], ["/settings", SettingsIcon, msg("环境与备份")]];
export default function App() {
  useLanguage();
  const [health, setHealth] = useState(null),
    [q, setQ] = useState(""),
    [results, setResults] = useState([]),
    [menu, setMenu] = useState(false);
  const navigate = useNavigate(), location = useLocation();
  useEffect(() => {
    const load = () => api("/health").then(setHealth).catch(() => setHealth({
      database: "unavailable"
    }));
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    let alive = true;
    const timer = setTimeout(() => api(`/objects?q=${encodeURIComponent(q)}&limit=8`).then(rows => {
      if (alive) setResults(rows);
    }).catch(() => setResults([])), 250);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [q]);
  if (location.pathname.startsWith("/shared/paths/")) return <Routes><Route path="/shared/paths/:token" element={<SharedLearningPath />} /><Route path="*" element={<div className="empty">{t("分享链接无效。")}</div>} /></Routes>;
  return <div className="app-shell"><aside className={`sidebar ${menu ? "open" : ""}`}><div className="brand"><div className="brand-mark"><Leaf size={23} /></div><div><strong>{t("知行 · Embodied")}</strong><span>{t("个人研究工作台")}</span></div></div><span className="nav-label">{t("WORKSPACE")}</span><nav>{navigation.map(([path, Icon, label]) => <NavLink key={path} to={path} end={path === "/"} onClick={() => setMenu(false)}><Icon size={18} /><span>{t(label)}</span></NavLink>)}</nav><div className="sidebar-bottom"><span className="eyebrow">{t("RESEARCH FOCUS")}</span><p>{t("机器人操作")}<br />{t("VLA · 世界模型")}</p><div className="local-indicator"><i />{t("本地存储 · 个人使用")}</div></div></aside><div className="main-shell"><header className="topbar"><button className="mobile-toggle ghost" aria-label={t("展开导航")} onClick={() => setMenu(!menu)}><Menu size={19} /></button><div className="global-search"><Search size={16} /><input aria-label={t("全局搜索")} placeholder={t("搜索知识、代码与问题…")} value={q} onChange={e => setQ(e.target.value)} />{q && <div className="search-results">{results.length ? results.map(o => <button key={o.id} onClick={() => {
              navigate(`/knowledge/${o.id}`);
              setQ("");
            }}>{o.title}</button>) : <p>{t("没有匹配内容")}</p>}</div>}</div><div className="topbar-status"><i className={health?.database === "ready" ? "ready" : ""} />{health?.database === "ready" ? t("PostgreSQL 已连接") : t("数据库待配置")}</div><LanguageSwitch /><span className="avatar">{t("研")}</span></header>{health && health.database !== "ready" && <div className="connection-banner">{t("后端已启动，数据库尚未就绪。运行本地初始化脚本后即可保存内容。")}<NavLink to="/settings">{t("查看设置 ↗")}</NavLink></div>}<main><Routes><Route path="/" element={<Home />} /><Route path="/knowledge" element={<KnowledgeList />} /><Route path="/knowledge/:id" element={<KnowledgeDetail />} /><Route path="/imports" element={<Imports />} /><Route path="/paths" element={<LearningPathList />} /><Route path="/paths/:id" element={<LearningPathEditor />} /><Route path="/graph" element={<Graph />} /><Route path="/canvases" element={<CanvasList />} /><Route path="/canvases/:id" element={<CanvasEditor />} /><Route path="/timeline" element={<Timeline />} /><Route path="/experiments" element={<Experiments />} /><Route path="/trash" element={<Trash />} /><Route path="/settings" element={<Settings />} /><Route path="*" element={<div className="empty">{t("页面不存在，请从左侧导航继续。")}</div>} /></Routes></main><TrashNotice /></div></div>;
}
