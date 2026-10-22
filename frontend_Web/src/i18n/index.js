import { useSyncExternalStore } from 'react';
import zh from './zh.json';
import en from './en.json';
import { createI18n } from './runtime';

function updateDocument(language) {
  if (typeof document === 'undefined') return;
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  document.title = language === 'zh' ? '知行 · Knowledge in Motion' : 'Zhixing · Knowledge in Motion';
}
const store = createI18n({
  catalogs: { zh, en },
  storage: {
    getItem: key => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value)
  },
  onChange: updateDocument
});

export const t = store.t;
export const msg = store.msg;
export const translateMessage = store.translateMessage;
export const setLanguage = store.setLanguage;
export const getLanguage = store.getLanguage;
export const dateLocale = () => store.getLanguage() === 'zh' ? 'zh-CN' : 'en-GB';
export function useLanguage() {
  return useSyncExternalStore(store.subscribe, store.getLanguage, () => 'zh');
}

updateDocument(store.getLanguage());
if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key === 'workspace:language' || event.key === null) {
      store.setLanguage(event.newValue || 'zh', { persist: false });
    }
  });
}
