// Framework-independent store; language changes never remount editors or mutate data.
export function createI18n({ catalogs, storage, onChange = () => {} }) {
  const storageKey = 'workspace:language';
  const supported = value => value === 'zh' || value === 'en';
  let language = 'zh';
  try {
    const saved = storage?.getItem(storageKey);
    if (supported(saved)) language = saved;
  } catch { /* The switch also works when browser storage is unavailable. */ }
  const listeners = new Set();
  const format = (text, values = {}) => text.replace(/\{(\w+)\}/g, (match, key) =>
    Object.hasOwn(values, key) ? String(values[key]) : match);
  const t = (key, values) => {
    if (typeof key !== 'string') return key;
    return format(catalogs[language][key] ?? catalogs.zh[key] ?? key, values);
  };
  // Mark a message for later rendering (e.g. state, label maps, and exceptions).
  const msg = (key, values) => values ? format(catalogs.zh[key] ?? key, values) : key;
  const patterns = Object.entries(catalogs.zh).filter(([, text]) => /\{\w+\}/.test(text)).map(([key, text]) => {
    const names = [];
    const pattern = text.split(/(\{\w+\})/).map(part => {
      const placeholder = /^\{(\w+)\}$/.exec(part);
      if (placeholder) { names.push(placeholder[1]); return '([\\s\\S]*?)'; }
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('');
    return { key, names, regex: new RegExp('^' + pattern + '$') };
  });
  function translateMessage(message) {
    if (!message || typeof message !== 'string') return message;
    if (Object.hasOwn(catalogs.zh, message)) return t(message);
    for (const { key, names, regex } of patterns) {
      const match = regex.exec(message);
      if (match) return t(key, Object.fromEntries(names.map((name, index) => [name, match[index + 1]])));
    }
    // Unknown upstream English errors remain readable. Existing server messages
    // are catalogued; new Chinese errors get an English fallback until translated.
    return language === 'en' && /[\u3400-\u9fff]/.test(message)
      ? t('请求失败，请检查内容与服务状态。') : message;
  }
  return {
    t, msg, translateMessage,
    getLanguage: () => language,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    setLanguage(next, { persist = true } = {}) {
      if (!supported(next)) return;
      if (persist) {
        try { storage?.setItem(storageKey, next); } catch { /* Keep the in-memory preference. */ }
      }
      if (language === next) return;
      language = next;
      onChange(language);
      for (const listener of listeners) listener();
    }
  };
}
