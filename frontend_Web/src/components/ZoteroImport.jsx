import { useEffect, useRef, useState } from "react";
import { t, useLanguage } from "../i18n";
import { write } from "../services/api";
import { ErrorBox, Field } from "./shared";

export default function ZoteroImport({ provider, onPreview, onBusyChange, disabled }) {
  useLanguage();
  const [query, setQuery] = useState("");
  const [qmode, setQmode] = useState("titleCreatorYear");
  const [tag, setTag] = useState("");
  const [limit, setLimit] = useState(20);
  const [includeFulltext, setIncludeFulltext] = useState(true);
  const [includeMedia, setIncludeMedia] = useState(true);
  const [items, setItems] = useState([]);
  const [searched, setSearched] = useState(false);
  const [operation, setOperation] = useState("");
  const [error, setError] = useState("");
  const requestId = useRef(0);
  const busy = !!operation;
  useEffect(() => () => { requestId.current += 1; }, []);
  useEffect(() => {
    onBusyChange(busy);
    return () => onBusyChange(false);
  }, [busy, onBusyChange]);

  async function search() {
    if (!query.trim() || busy || disabled) return;
    const current = ++requestId.current;
    setOperation("search"); setError(""); setSearched(false); setItems([]);
    try {
      const result = await write("/source-imports/zotero/search", { query, qmode, tag, limit });
      if (requestId.current !== current) return;
      setItems(result.items); setSearched(true);
    } catch (failure) {
      if (requestId.current === current) setError(failure.message);
    } finally {
      if (requestId.current === current) setOperation("");
    }
  }

  async function preview(itemKey) {
    if (busy || disabled) return;
    const current = ++requestId.current;
    setOperation("preview"); setError("");
    try {
      const result = await write("/source-imports/zotero/preview", { item_key: itemKey, include_fulltext: includeFulltext, include_media: includeMedia });
      if (requestId.current === current) onPreview(result);
    } catch (failure) {
      if (requestId.current === current) setError(failure.message);
    } finally {
      if (requestId.current === current) setOperation("");
    }
  }

  return <div className="zotero-import" aria-label={t("zotero.panel")}>
    <p className="muted">{t("zotero.readOnly")}</p>
    {!provider?.configured ? <>
      <p className="info-note">{t("zotero.setup")}</p>
      <ErrorBox message={provider?.error} />
    </> : <>
      <Field label={t("zotero.query")}><input aria-label={t("zotero.query")} value={query} disabled={busy || disabled} placeholder={t("zotero.queryPlaceholder")} onChange={event => setQuery(event.target.value)} onKeyDown={event => {
        if (event.key === "Enter") { event.preventDefault(); search(); }
      }} /></Field>
      <Field label={t("zotero.mode")}><select aria-label={t("zotero.mode")} value={qmode} disabled={busy || disabled} onChange={event => setQmode(event.target.value)}>
        <option value="titleCreatorYear">{t("zotero.modeMetadata")}</option>
        <option value="everything">{t("zotero.modeEverything")}</option>
      </select></Field>
      <Field label={t("zotero.tag")}><input aria-label={t("zotero.tag")} value={tag} disabled={busy || disabled} onChange={event => setTag(event.target.value)} /></Field>
      <Field label={t("zotero.limit")}><select aria-label={t("zotero.limit")} value={limit} disabled={busy || disabled} onChange={event => setLimit(Number(event.target.value))}>
        {[20, 50, 100].map(value => <option key={value} value={value}>{value}</option>)}
      </select></Field>
      <label className="check"><input type="checkbox" checked={includeFulltext} disabled={busy || disabled} onChange={event => setIncludeFulltext(event.target.checked)} />{t("zotero.includeFulltext")}</label>
      <label className="check"><input type="checkbox" checked={includeMedia} disabled={busy || disabled} onChange={event => setIncludeMedia(event.target.checked)} />{t("media.includePdf")}</label>
      <button type="button" onClick={search} disabled={busy || disabled || !query.trim()}>{operation === "search" ? t("zotero.searching") : t("zotero.search")}</button>
      <p className="muted">{t("zotero.searchHint")}</p>
      <ErrorBox message={error} />
      {operation === "preview" && <p role="status">{t("zotero.reading")}</p>}
      {searched && <div role="status"><p>{items.length ? t("zotero.resultCount", { count: items.length }) : t("zotero.empty")}</p>
        {items.length > 0 && <p className="muted">{t("zotero.limitHint")}</p>}
      </div>}
      <ul className="zotero-results">{items.map(item => <li key={item.item_key}>
        <strong>{item.title}</strong>
        <p>{item.authors || t("zotero.noAuthors")}</p>
        <p className="muted">{item.date} · {item.item_key}</p>
        <button type="button" className="ghost" disabled={busy || disabled} aria-label={t("zotero.previewItem", { title: item.title })} onClick={() => preview(item.item_key)}>{t("zotero.preview")}</button>
      </li>)}</ul>
    </>}
  </div>;
}
