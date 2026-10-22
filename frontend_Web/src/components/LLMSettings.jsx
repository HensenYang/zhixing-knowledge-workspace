import { t, useLanguage } from "../i18n";
import { useEffect, useState } from "react";
import { api } from "../services/api";
import { ErrorBox } from "./shared";
export default function LLMSettings() {
  const language = useLanguage();
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function check() {
    setError("");
    setResult(null);
    try {
      setStatus(await api("/llm/status"));
    } catch (e) {
      setStatus(null);
      setError(e.message);
    }
  }
  useEffect(() => {
    check();
  }, []);
  async function test() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api("/llm/test", {
        method: "POST"
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return <section className="panel" aria-label={t("LLM 接入")}>
    <div className="section-heading"><h2>{t("LLM 接入")}</h2><button className="ghost" onClick={check} disabled={busy}>{t("刷新模型配置")}</button></div>
    <ErrorBox message={error || status?.error} />
    <dl className="environment-list">
      <div><dt>{t("配置状态")}</dt><dd>{status ? status.configured ? t("已配置 · 待测试连接") : t("尚未配置完成") : t("配置状态未知")}</dd></div>
      <div><dt>{t("模型")}</dt><dd>{status?.model || t("未指定")}</dd></div>
      <div><dt>{t("API 地址")}</dt><dd style={{
          overflowWrap: "anywhere"
        }}>{status?.base_url || t("未就绪")}</dd></div>
      <div><dt>API Key</dt><dd>{status?.api_key_configured ? t("后端已设置") : t("后端未设置")}</dd></div>
    </dl>
    {!!status?.missing?.length && <p className="muted">{t("待配置：")}{status.missing.join(language === "zh" ? "、" : ", ")}</p>}
    <p>{t("在本机 .env 中设置 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL，然后重启后端。")}</p>
    <p className="muted">{t("支持 OpenAI 兼容的 Chat Completions 文本接口。模型由后端配置决定，密钥仅由后端读取。")}</p>
    <button onClick={test} disabled={!status?.configured || busy}>{busy ? t("正在测试…") : t("测试模型连接")}</button>
    <p className="muted">{t("测试会向已配置服务发送一条固定短消息，可能产生少量 API 费用；不会发送知识库内容。")}</p>
    {result?.ok && <div className="success-box" role="status">{t("连接成功 ·")} {result.model}<p style={{
        whiteSpace: "pre-wrap"
      }}>{result.content}</p>{result.usage?.total_tokens != null && <small>{t("用量：{tokens} tokens", {
          tokens: result.usage.total_tokens
        })}</small>}</div>}
  </section>;
}
