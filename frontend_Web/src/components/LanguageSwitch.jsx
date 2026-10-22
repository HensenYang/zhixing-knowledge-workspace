import { Languages } from "lucide-react";
import { t, setLanguage, useLanguage } from "../i18n";
export default function LanguageSwitch() {
  const language = useLanguage();
  return <label className="language-switch">
    <Languages size={17} aria-hidden="true" />
    <select aria-label={t("界面语言")} value={language} onChange={event => setLanguage(event.target.value)}>
      <option value="zh">{t("中文")}</option>
      <option value="en">{t("English")}</option>
    </select>
  </label>;
}
