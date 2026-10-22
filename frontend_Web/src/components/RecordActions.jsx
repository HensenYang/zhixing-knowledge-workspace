import { t, msg, useLanguage } from "../i18n";
import { useEffect, useRef, useState } from "react";
import { api, write } from "../services/api";
import { ErrorBox } from "./shared";
export function announceChange() {
  window.dispatchEvent(new Event("workspace-changed"));
}
export function useWorkspaceChanges(callback) {
  const latest = useRef(callback);
  latest.current = callback;
  useEffect(() => {
    const listener = () => latest.current();
    window.addEventListener("workspace-changed", listener);
    return () => window.removeEventListener("workspace-changed", listener);
  }, []);
}
export function DeleteButton({
  kind,
  id,
  title,
  onDeleted,
  label = t("删除"),
  beforeDelete
}) {
  useLanguage();
  const [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function remove() {
    setBusy(true);
    setError("");
    try {
      if (beforeDelete && (await beforeDelete()) === false) throw Error(msg("请先处理未保存的修改。"));
      const paths = {
        object: "objects",
        relation: "relations",
        canvas: "canvases",
        session: "sessions",
        run: "runs",
        attachment: "attachments",
        path: "learning-paths"
      };
      await api(`/${paths[kind]}/${id}`, {
        method: "DELETE"
      });
      setConfirm(false);
      onDeleted?.();
      announceChange();
      window.dispatchEvent(new CustomEvent("workspace-deleted", {
        detail: {
          kind,
          id,
          title
        }
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <><button type="button" className="danger ghost" onClick={() => setConfirm(true)}>{t(label)}</button>{confirm && <div className="modal-backdrop"><section className="panel confirm-dialog" role="dialog" aria-modal="true" aria-label={t("确认删除")}><h2>{t("移入回收站？")}</h2><p>{t("「{title}」将从当前页面隐藏，可在回收站恢复。", {
            title
          })}</p>{kind === "object" && <p className="muted">{t("相关连接和实验运行会暂时隐藏；画布引用保留，恢复后重新显示。")}</p>}{kind === "relation" && <p className="muted">{t("画布引用保留，恢复后重新关联。")}</p>}<ErrorBox message={error} /><div className="actions"><button type="button" className="danger" disabled={busy} onClick={remove}>{t("确认删除")}</button><button type="button" className="ghost" disabled={busy} onClick={() => setConfirm(false)}>{t("取消")}</button></div></section></div>}</>;
}
export function TrashNotice() {
  useLanguage();
  const [record, setRecord] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    const listener = e => {
      setRecord(e.detail);
      setError("");
    };
    window.addEventListener("workspace-deleted", listener);
    const purged = () => {
      setRecord(null);
      setError("");
    };
    window.addEventListener("workspace-purged", purged);
    return () => {
      window.removeEventListener("workspace-deleted", listener);
      window.removeEventListener("workspace-purged", purged);
    };
  }, []);
  if (!record) return null;
  return <div className="trash-notice" role="status"><span>{t("已移入回收站：{title}", {
        title: record.title
      })}</span><button type="button" className="ghost" onClick={async () => {
      try {
        await write(`/trash/${record.kind}/${record.id}/restore`, {});
        setRecord(null);
        announceChange();
      } catch (e) {
        setError(e.message);
      }
    }}>{t("撤销删除")}</button><button type="button" className="ghost" aria-label={t("关闭删除提示")} onClick={() => setRecord(null)}>×</button><ErrorBox message={error} /></div>;
}
