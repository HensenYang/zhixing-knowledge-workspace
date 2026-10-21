import { t, useLanguage } from "../i18n";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { api, write } from "../services/api";
import { PageTitle, Field, ErrorBox, Empty, DateText, Markdown } from "../components/shared";
import { DeleteButton, useWorkspaceChanges } from "../components/RecordActions";
const blank = {
  objective: "",
  activity_md: "",
  understanding_change_md: "",
  blockers_md: "",
  next_step_md: "",
  object_ids: []
};
export default function Timeline() {
  useLanguage();
  const [sessions, setSessions] = useState([]),
    [runs, setRuns] = useState([]),
    [objects, setObjects] = useState([]),
    [show, setShow] = useState(false),
    [form, setForm] = useState(blank),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = () => Promise.all([api("/sessions"), api("/runs"), api("/objects?limit=1000&archived=true")]).then(([s, r, o]) => {
    setSessions(s);
    setRuns(r);
    setObjects(o);
  }).catch(e => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useWorkspaceChanges(load);
  const change = (key, value) => setForm({
    ...form,
    [key]: value
  });
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await write(form.id ? `/sessions/${form.id}` : "/sessions", form, form.id ? "PATCH" : "POST");
      setForm(blank);
      setShow(false);
      setError("");
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const events = [...sessions.map(s => ({
    ...s,
    type: "session",
    time: s.occurred_at
  })), ...runs.map(r => ({
    ...r,
    type: "run",
    time: r.created_at
  }))].sort((a, b) => new Date(b.time) - new Date(a.time));
  return <><PageTitle eyebrow={t("LEARNING JOURNEY")} title={t("学习轨迹")} actions={<button onClick={() => {
      setForm(blank);
      setShow(true);
    }}><Plus size={16} />{t("记录一次学习")}</button>}>{t("记录实际做了什么、理解如何变化，以及下一步要验证什么。")}</PageTitle><ErrorBox message={error} />{show && <form className="panel session-form" onSubmit={save}><h2>{form.id ? t("修改学习记录") : t("本次学习记录")}</h2><Field label={t("学习时间")}><input type="datetime-local" value={form.occurred_at ? new Date(new Date(form.occurred_at).getTime() - new Date(form.occurred_at).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ""} onChange={e => change("occurred_at", e.target.value ? new Date(e.target.value).toISOString() : null)} /></Field><Field label={t("用时（分钟，可选）")}><input type="number" min="0" value={form.duration_minutes ?? ""} onChange={e => change("duration_minutes", e.target.value ? Number(e.target.value) : null)} /></Field><Field label={t("目标")}><input required value={form.objective} onChange={e => change("objective", e.target.value)} /></Field><div className="form-grid">{[["activity_md", t("实际阅读／操作")], ["understanding_change_md", t("理解变化")], ["blockers_md", t("尚未解决的问题")], ["next_step_md", t("下一步")]].map(([k, v]) => <Field key={k} label={v}><textarea rows={4} value={form[k]} onChange={e => change(k, e.target.value)} /></Field>)}</div><Field label={t("关联知识（Ctrl 可多选）")}><select multiple value={form.object_ids} onChange={e => change("object_ids", Array.from(e.target.selectedOptions, o => o.value))}>{form.object_ids.filter(id => !objects.some(o => o.id === id)).map(id => <option key={id} value={id}>{t("已删除的关联知识（可恢复）")}</option>)}{objects.map(o => <option key={o.id} value={o.id}>{o.title}</option>)}</select></Field><div className="actions"><button disabled={busy}>{t("保存记录")}</button><button type="button" className="ghost" onClick={() => setShow(false)}>{t("收起")}</button></div></form>}<div className="timeline">{events.map(event => <article className="timeline-event" key={`${event.type}-${event.id}`}><div className="timeline-marker" /><div className="timeline-date"><DateText value={event.time} /><span>{event.type === "session" ? t("学习记录") : t("实验运行")}</span></div><div className="panel">{event.type === "session" ? <><div className="section-heading"><h2>{event.objective}</h2><div className="actions"><button className="ghost" onClick={() => {
                  setForm(event);
                  setShow(true);
                  window.scrollTo({
                    top: 0,
                    behavior: "smooth"
                  });
                }}>{t("修改")}</button><DeleteButton kind="session" id={event.id} title={event.objective} onDeleted={() => {
                  setShow(false);
                  load();
                }} /></div></div><Markdown>{event.activity_md}</Markdown>{event.understanding_change_md && <><h3>{t("理解变化")}</h3><Markdown>{event.understanding_change_md}</Markdown></>}{event.blockers_md && <div className="info-note"><strong>{t("待解决")}</strong><p>{event.blockers_md}</p></div>}{event.next_step_md && <p className="next-step">{t("下一步 →")} {event.next_step_md}</p>}<div className="tag-links">{event.object_ids.map(id => objects.some(o => o.id === id) ? <Link key={id} to={`/knowledge/${id}`}>{objects.find(o => o.id === id)?.title}</Link> : <span key={id}>{t("关联知识已删除 · 可在回收站恢复")}</span>)}</div></> : <><h2>{objects.find(o => o.id === event.experiment_id)?.title || t("实验运行")}</h2><span className="badge">{{
                planned: t("待运行"),
                running: t("运行中"),
                succeeded: t("已完成"),
                failed: t("失败"),
                cancelled: t("已取消")
              }[event.status]}</span><Markdown>{event.result_md || event.failure_md || event.hypothesis_md}</Markdown><Link className="text-link" to="/experiments">{t("查看运行配置 ↗")}</Link></>}</div></article>)}</div>{!events.length && !error && <Empty title={t("你的学习轨迹从这里开始")} />}</>;
}
