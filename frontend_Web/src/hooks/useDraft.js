import { useEffect, useRef, useState } from 'react';
import { get, set, del } from 'idb-keyval';

// A failed or conflicting save never discards the local IndexedDB draft.
export default function useDraft(key, initial, saver, enabled = true) {
  const [value, setValue] = useState(null);
  const [status, setStatus] = useState('加载中');
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const baseline = useRef('');
  const current = useRef(null);
  const saving = useRef(false);
  const paused = useRef(false);
  const saveFn = useRef(saver);
  saveFn.current = saver;
  useEffect(() => {
    if (!initial) return;
    let alive = true;
    baseline.current = JSON.stringify(initial);
    get(key).catch(() => null).then(draft => {
      if (!alive) return;
      const restored = draft || initial;
      current.current = restored;
      setValue(restored);
      paused.current = false;
      setStatus(draft ? '已恢复本地草稿' : '已保存');
    });
    return () => {
      alive = false;
    };
  }, [key, initial]);
  const change = next => {
    const updated = typeof next === 'function' ? next(current.current) : next;
    current.current = updated;
    setValue(updated);
    setStatus('未保存');
    set(key, updated).catch(() => setError('浏览器草稿缓存不可用，请及时保存或下载草稿。'));
  };
  async function save() {
    if (saving.current || !current.current) return false;
    const snapshot = current.current;
    saving.current = true;
    setStatus('保存中');
    setError('');
    try {
      const saved = await saveFn.current(snapshot);
      baseline.current = JSON.stringify(saved);
      const next = JSON.stringify(current.current) === JSON.stringify(snapshot) ? saved : {
        ...current.current,
        version: saved.version
      };
      current.current = next;
      setValue(next);
      if (JSON.stringify(next) === baseline.current) {
        await del(key);
        setStatus('已保存');
      } else {
        await set(key, next);
        setStatus('未保存');
      }
      paused.current = false;
      return true;
    } catch (e) {
      paused.current = true;
      setStatus('保存失败 · 草稿保留');
      setError(e.message);
      return false;
    } finally {
      saving.current = false;
      setTick(t => t + 1);
    }
  }
  useEffect(() => {
    if (!enabled || !value || paused.current || JSON.stringify(value) === baseline.current) return;
    const timer = setTimeout(save, 1100);
    return () => clearTimeout(timer);
  }, [value, tick, enabled]);
  useEffect(() => {
    const warn = e => {
      if (current.current && JSON.stringify(current.current) !== baseline.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(current.current, null, 2)], {
      type: 'application/json'
    }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'workspace-draft.json';
    a.click();
    URL.revokeObjectURL(url);
  };
  const discard = async () => {
    await del(key);
    paused.current = false;
    current.current = initial;
    baseline.current = JSON.stringify(initial);
    setValue(initial);
    setError('');
    setStatus('已保存');
  };
  return {
    value,
    change,
    status,
    error,
    save,
    download,
    discard
  };
}
