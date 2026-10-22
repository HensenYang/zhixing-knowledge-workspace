import Pager from '../components/Pager';
import { t, msg, useLanguage } from "../i18n";
import { useEffect, useState } from "react";
import { api, apiPage, write } from "../services/api";
import { PageTitle, ErrorBox, Empty, DateText } from "../components/shared";
import { announceChange, useWorkspaceChanges } from "../components/RecordActions";
const labels = {
  object: msg("知识对象"),
  relation: msg("知识关系"),
  canvas: msg("画布"),
  session: msg("学习记录"),
  run: msg("实验运行"),
  attachment: msg("附件"),
  path: msg("学习路径")
};
const PAGE_SIZE = 50;
export default function Trash() {
  useLanguage();
  const [rows, setRows] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(null),
    [deleting, setDeleting] = useState(null), [offset, setOffset] = useState(0), [total, setTotal] = useState(0);
  const load = () => apiPage(`/trash?limit=${PAGE_SIZE}&offset=${offset}`).then(({items,total}) => { setRows(items); setTotal(total); if(!items.length && offset > 0) setOffset(Math.max(0,offset-PAGE_SIZE)); }).catch(e => setError(e.message));
  useEffect(() => {
    load();
  }, [offset]);
  useWorkspaceChanges(load);
  async function restore(row) {
    setBusy(row.id);
    try {
      await write(`/trash/${row.kind}/${row.id}/restore`, {});
      setError("");
      announceChange();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }
  async function remove() {
    setBusy(deleting.id);
    try {
      const result = await api(`/trash/${deleting.kind}/${deleting.id}`, {
        method: "DELETE"
      });
      setError(result.warnings?.join(" ") || "");
      window.dispatchEvent(new CustomEvent("workspace-purged", {
        detail: deleting
      }));
      setDeleting(null);
      announceChange();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }
  return <><PageTitle eyebrow={t("RECOVER YOUR WORK")} title={t("回收站")}>{t("恢复记录，或永久删除不再需要的内容。永久删除无法撤销；已有备份不受影响。")}</PageTitle><ErrorBox message={error} /><div className="record-list">{rows.map(row => <article className="panel record-row" key={`${row.kind}-${row.id}`}><div><span className="badge">{t(labels[row.kind])}</span><h3>{row.title}</h3><DateText value={row.deleted_at} /></div><div className="actions"><button disabled={busy === row.id} onClick={() => restore(row)}>{t("恢复")}</button><button className="danger ghost" disabled={busy === row.id} onClick={() => {
            setError("");
            setDeleting(row);
          }}>{t("永久删除")}</button></div></article>)}</div>{!rows.length && !error && <Empty title={t("回收站为空")} />}<Pager total={total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />{deleting && <div className="modal-backdrop"><section className="panel confirm-dialog" role="dialog" aria-modal="true" aria-label={t("确认永久删除")}><h2>{t("永久删除「{title}」？", {
            title: deleting.title
          })}</h2><p>{t("此操作无法撤销，记录将无法从回收站恢复。")}</p>{deleting.kind === "object" && <p>{t("同时删除相关知识关系、所属实验运行、修订历史及未被其他对象引用的附件；学习记录保留，画布卡片转为文本占位。含此对象的画布历史也会清理。")}</p>}{deleting.kind === "relation" && <p>{t("关系证据同时删除，画布连线转为局部连线，含此关系的画布历史也会清理。")}</p>}{deleting.kind === "attachment" && <p>{t("附件记录与本地附件文件同时删除。")}</p>}<ErrorBox message={error} /><div className="actions"><button className="danger" disabled={busy !== null} onClick={remove}>{t("确认永久删除")}</button><button className="ghost" disabled={busy !== null} onClick={() => setDeleting(null)}>{t("取消")}</button></div></section></div>}</>;
}
