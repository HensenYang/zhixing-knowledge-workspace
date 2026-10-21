import { t, msg, useLanguage } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { NavLink, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, BookOpen, Network, PanelsTopLeft, Route as RouteIcon,
  FlaskConical, Settings as SettingsIcon, Search, Menu, Leaf,
  Archive as ArchiveIcon, Upload, ListOrdered, Users, LogOut
} from "lucide-react";
import { api } from "./services/api";
import { useAuth } from "./contexts/AuthContext";
import AuthScreen from "./components/AuthScreen";
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
import Collaboration from "./pages/Collaboration";
import { LearningPathList, LearningPathEditor, SharedLearningPath } from "./pages/LearningPaths";
import PathArtifactImport from "./pages/PathArtifactImport";

const navigation = [
  ["/", LayoutDashboard, msg("工作台")],
  ["/knowledge", BookOpen, msg("知识与资料")],
  ["/imports", Upload, msg("资料导入")],
  ["/paths", ListOrdered, msg("研究学习路径")],
  ["/graph", Network, msg("知识图谱")],
  ["/canvases", PanelsTopLeft, msg("自由画布")],
  ["/timeline", RouteIcon, msg("学习轨迹")],
  ["/experiments", FlaskConical, msg("实验与复现")],
  ["/collaboration", Users, msg("团队协作")],
  ["/trash", ArchiveIcon, msg("回收站")],
  ["/settings", SettingsIcon, msg("环境与备份")]
];

export default function App() {
  useLanguage();
  const { user, loading } = useAuth();
  const location = useLocation();
  if (location.pathname === "/artifacts") return <PathArtifactImport />;
  if (location.pathname.startsWith("/shared/paths/")) {
    return <Routes><Route path="/shared/paths/:token" element={<SharedLearningPath />} /><Route path="*" element={<div className="empty">{t("分享链接无效。")}</div>} /></Routes>;
  }
  if (loading) return <div className="empty">{t("正在连接协作空间…")}</div>;
  return user ? <WorkspaceApp /> : <AuthScreen />;
}

function WorkspaceApp() {
  useLanguage();
  const { user, workspace, logout } = useAuth();
  const lastActivity = useRef(null);
  const [health, setHealth] = useState(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [menu, setMenu] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const load = () => api("/health").then(setHealth).catch(() => setHealth({ database: "unavailable" }));
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

  useEffect(() => {
    let alive = true;
    const check = () => api("/activity?limit=1").then(rows => {
      const latest = rows[0]?.id || 0;
      if (alive && lastActivity.current !== null && latest !== lastActivity.current) {
        window.dispatchEvent(new Event("workspace-changed"));
      }
      lastActivity.current = latest;
    }).catch(() => {});
    check();
    const timer = setInterval(check, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [workspace?.id]);

  return <div className="app-shell">
    <aside className={`sidebar ${menu ? "open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Leaf size={23} /></div><div><strong>{t("知行 · Embodied")}</strong><span>{t("团队研究工作台")}</span></div></div>
      <label className="workspace-switcher"><span className="nav-label">{t("WORKSPACE")}</span><select value={workspace?.id || ""} onChange={event => {
        localStorage.setItem("knowledge-workspace-id", event.target.value);
        window.location.assign("/");
      }}>{user.workspaces.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <nav>{navigation.map(([path, Icon, label]) => <NavLink key={path} to={path} end={path === "/"} onClick={() => setMenu(false)}><Icon size={18} /><span>{t(label)}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><span className="eyebrow">{t("SIGNED IN")}</span><p>{user.display_name}<br />{user.email}</p><div className="local-indicator"><i />{t("团队数据库")} · {workspace?.role}</div><button className="ghost logout-button" onClick={logout}><LogOut size={14} />{t("退出登录")}</button></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><button className="mobile-toggle ghost" aria-label={t("展开导航")} onClick={() => setMenu(!menu)}><Menu size={19} /></button><div className="global-search"><Search size={16} /><input aria-label={t("全局搜索")} placeholder={t("搜索知识、代码与问题…")} value={q} onChange={event => setQ(event.target.value)} />{q && <div className="search-results">{results.length ? results.map(object => <button key={object.id} onClick={() => {
        navigate(`/knowledge/${object.id}`);
        setQ("");
      }}>{object.title}</button>) : <p>{t("没有匹配内容")}</p>}</div>}</div><div className="topbar-status"><i className={health?.database === "ready" ? "ready" : ""} />{health?.database === "ready" ? t("协作数据库已连接") : t("数据库待配置")}</div><LanguageSwitch /><span className="avatar">{user.display_name.slice(0, 1)}</span></header>
      {health && health.database !== "ready" && <div className="connection-banner">{t("后端已启动，数据库尚未就绪。请运行最新迁移。")}<NavLink to="/settings">{t("查看设置 ↗")}</NavLink></div>}
      <main><Routes>
        <Route path="/" element={<Home />} />
        <Route path="/knowledge" element={<KnowledgeList />} />
        <Route path="/knowledge/:id" element={<KnowledgeDetail />} />
        <Route path="/imports" element={<Imports />} />
        <Route path="/paths" element={<LearningPathList />} />
        <Route path="/paths/:id" element={<LearningPathEditor />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/canvases" element={<CanvasList />} />
        <Route path="/canvases/:id" element={<CanvasEditor />} />
        <Route path="/timeline" element={<Timeline />} />
        <Route path="/experiments" element={<Experiments />} />
        <Route path="/collaboration" element={<Collaboration />} />
        <Route path="/trash" element={<Trash />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<div className="empty">{t("页面不存在，请从左侧导航继续。")}</div>} />
      </Routes></main>
      <TrashNotice />
    </div>
  </div>;
}
