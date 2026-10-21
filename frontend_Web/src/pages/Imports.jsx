import { t, msg, useLanguage, translateMessage } from "../i18n";
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Upload, FileSearch, CheckCircle2 } from 'lucide-react';
import { api, write } from '../services/api';
import { PageTitle, Field, ErrorBox, SelectKind } from '../components/shared';
const emptyProviders = {
  providers: ['arxiv', 'doi', 'github', 'pdf'],
  mcp: {
    enabled: false,
    tool: 'import_source'
  }
};
export default function Imports() {
  useLanguage();
  const [providers, setProviders] = useState(emptyProviders),
    [sourceType, setSourceType] = useState('auto'),
    [source, setSource] = useState(''),
    [file, setFile] = useState(null),
    [preview, setPreview] = useState(null),
    [metadataText, setMetadataText] = useState('{}'),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [attachmentError, setAttachmentError] = useState(''),
    [busy, setBusy] = useState(false),
    [created, setCreated] = useState(null);
  useEffect(() => {
    api('/source-imports/providers').then(setProviders).catch(() => setProviders(emptyProviders));
  }, []);
  async function inspect(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    setAttachmentError('');
    setCreated(null);
    try {
      let result;
      if (sourceType === 'pdf') {
        if (!file) throw Error(msg("请选择一个 PDF 文件。"));
        const data = new FormData();
        data.append('file', file);
        result = await api('/source-imports/preview-file', {
          method: 'POST',
          body: data
        });
      } else {
        result = await write('/source-imports/preview', {
          source,
          source_type: sourceType
        });
      }
      setPreview({
        ...result,
        kind: result.suggested_kind,
        tagsText: (result.tags || []).join(', ')
      });
      setMetadataText(JSON.stringify(result.metadata || {}, null, 2));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }
  const change = (key, value) => setPreview(current => ({
    ...current,
    [key]: value
  }));
  async function commit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    setAttachmentError('');
    try {
      const metadata = JSON.parse(metadataText);
      if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) throw Error(msg("扩展属性必须是有效的 JSON 对象。"));
      const object = {
        kind: preview.kind,
        title: preview.title,
        summary: preview.summary,
        body_md: preview.body_md,
        source_url: preview.source_url || null,
        metadata,
        tags: preview.tagsText.split(/[,，]/).map(tag => tag.trim()).filter(Boolean)
      };
      const saved = await write('/source-imports/commit', {
        source_type: preview.source_type,
        source_key: preview.source_key,
        extracted_metadata: preview.metadata || {},
        object
      });
      let attachmentWarning = '';
      if (preview.source_type === 'pdf' && file) {
        const data = new FormData();
        data.append('file', file);
        try {
          await api(`/objects/${saved.id}/attachments`, {
            method: 'POST',
            body: data
          });
        } catch (failure) {
          attachmentWarning = failure.message;
        }
      }
      setCreated(saved);
      setAttachmentError(attachmentWarning);
      setMessage(msg('资料已导入。'));
    } catch (failure) {
      setError(failure instanceof SyntaxError ? msg("扩展属性必须是有效的 JSON 对象。") : failure.message);
    } finally {
      setBusy(false);
    }
  }
  function reset() {
    setPreview(null);
    setCreated(null);
    setMessage('');
    setAttachmentError('');
    setError('');
    setSource('');
    setFile(null);
  }
  return <><PageTitle eyebrow={t("SOURCE IMPORT")} title={t("资料导入")}>{t("从 arXiv、DOI、GitHub、PDF 或已配置的 MCP Server 提取资料；确认前不会写入知识库。")}</PageTitle>
    <div className="import-layout">
      <form className="panel import-source-panel" onSubmit={inspect}>
        <h2>{t("1. 选择资料来源")}</h2>
        <Field label={t("来源类型")}><select value={sourceType} onChange={event => {
            setSourceType(event.target.value);
            setPreview(null);
            setError('');
          }}>
          <option value="auto">{t("自动识别链接或标识符")}</option>
          <option value="arxiv">{t("arXiv")}</option>
          <option value="doi">{t("DOI / Crossref")}</option>
          <option value="github">{t("GitHub 仓库")}</option>
          <option value="pdf">{t("本地 PDF")}</option>
          {providers.mcp?.enabled && <option value="mcp">{t("MCP · {tool}", {
                tool: providers.mcp.tool
              })}</option>}
        </select></Field>
        {sourceType === 'pdf' ? <label className="file-upload"><Upload size={18} /><span>{file?.name || t("选择不超过 32 MB 的 PDF")}</span><input aria-label={t("选择 PDF")} type="file" accept="application/pdf,.pdf" onChange={event => setFile(event.target.files[0] || null)} /></label> : <Field label={sourceType === 'mcp' ? t("交给 MCP 工具的资料地址或标识符") : t("链接或标识符")}><input aria-label={t("资料地址")} value={source} onChange={event => setSource(event.target.value)} placeholder={t("arXiv URL、DOI、GitHub 仓库 URL…")} /></Field>}
        <button disabled={busy}><FileSearch size={16} />{busy ? t("正在提取…") : t("提取并预览")}</button>
        {!providers.mcp?.enabled && <p className="muted">{t("MCP 为可选来源，配置 MCP_IMPORT_SERVER_URL 后会自动显示。")}</p>}
      </form>

      <section className="panel import-help">
        <h2>{t("导入原则")}</h2>
        <ol>
          <li>{t("系统只从限定来源读取数据，避免任意 URL 请求。")}</li>
          <li>{t("提取结果先进入预览，不会直接写入知识图谱。")}</li>
          <li>{t("用户确认标题、正文和元数据后才创建知识对象。")}</li>
          <li>{t("相同来源重复导入会被拒绝，已有记录不会被覆盖。")}</li>
        </ol>
      </section>
    </div>
    <ErrorBox message={error} />
    {message && <div className="success-box"><CheckCircle2 size={18} />{attachmentError ? t("资料已导入，但原 PDF 附件上传失败：{error}", {error: translateMessage(attachmentError)}) : translateMessage(message)}</div>}
    {created && <div className="actions"><Link className="button" to={`/knowledge/${created.id}`}>{t("打开已导入资料")}</Link><button className="ghost" onClick={reset}>{t("继续导入")}</button></div>}

    {preview && !created && <form className="panel import-review" onSubmit={commit}>
      <div className="section-heading"><div><span className="eyebrow">{t("REVIEW BEFORE COMMIT")}</span><h2>{t("2. 检查并确认")}</h2></div><span className="status-pill">{preview.source_type.toUpperCase()}</span></div>
      {preview.warnings?.length > 0 && <div className="warning-box">{preview.warnings.map(item => <p key={item}>{translateMessage(item)}</p>)}</div>}
      {preview.possible_duplicates?.length > 0 && <div className="warning-box"><strong>{t("可能已经存在：")}</strong>{preview.possible_duplicates.map(item => <Link key={item.id} to={`/knowledge/${item.id}`}>{item.title}</Link>)}</div>}
      <div className="form-grid"><Field label={t("知识类型")}><SelectKind value={preview.kind} onChange={event => change('kind', event.target.value)} /></Field><Field label={t("标签（逗号分隔）")}><input value={preview.tagsText} onChange={event => change('tagsText', event.target.value)} /></Field></div>
      <Field label={t("标题")}><input required value={preview.title} onChange={event => change('title', event.target.value)} /></Field>
      <Field label={t("摘要")}><textarea rows={3} value={preview.summary} onChange={event => change('summary', event.target.value)} /></Field>
      <Field label={t("来源链接")}><input value={preview.source_url || ''} onChange={event => change('source_url', event.target.value)} /></Field>
      <Field label={t("Markdown 正文")}><textarea className="markdown-editor import-body" value={preview.body_md} onChange={event => change('body_md', event.target.value)} /></Field>
      <details><summary>{t("扩展属性 JSON")}</summary><textarea className="code-input" rows={10} value={metadataText} onChange={event => setMetadataText(event.target.value)} /></details>
      <div className="actions"><button disabled={busy}>{busy ? t("正在保存…") : t("确认并创建知识对象")}</button><button type="button" className="ghost" onClick={() => setPreview(null)}>{t("放弃预览")}</button></div>
    </form>}
  </>;
}
