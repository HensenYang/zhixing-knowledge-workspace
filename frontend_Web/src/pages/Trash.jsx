import { useEffect, useState } from 'react';
import { api, write } from '../services/api';
import { PageTitle, ErrorBox, Empty, DateText } from '../components/shared';
import { announceChange, useWorkspaceChanges } from '../components/RecordActions';
const labels = {
  object: '知识对象',
  relation: '知识关系',
  canvas: '画布',
  session: '学习记录',
  run: '实验运行',
  attachment: '附件'
};
export default function Trash() {
  const [rows, setRows] = useState([]),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(null),
    [deleting, setDeleting] = useState(null);
  const load = () => api('/trash').then(setRows).catch(e => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  useWorkspaceChanges(load);
  async function restore(row) {
    setBusy(row.id);
    try {
      await write(`/trash/${row.kind}/${row.id}/restore`, {});
      setError('');
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
        method: 'DELETE'
      });
      setError(result.warnings?.join(' ') || '');
      window.dispatchEvent(new CustomEvent('workspace-purged', {
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
  return <><PageTitle eyebrow="RECOVER YOUR WORK" title="回收站">恢复记录，或永久删除不再需要的内容。永久删除无法撤销；已有备份不受影响。</PageTitle><ErrorBox message={error} /><div className="record-list">{rows.map(row => <article className="panel record-row" key={`${row.kind}-${row.id}`}><div><span className="badge">{labels[row.kind]}</span><h3>{row.title}</h3><DateText value={row.deleted_at} /></div><div className="actions"><button disabled={busy === row.id} onClick={() => restore(row)}>恢复</button><button className="danger ghost" disabled={busy === row.id} onClick={() => {
            setError('');
            setDeleting(row);
          }}>永久删除</button></div></article>)}</div>{!rows.length && !error && <Empty title="回收站为空" />}{deleting && <div className="modal-backdrop"><section className="panel confirm-dialog" role="dialog" aria-modal="true" aria-label="确认永久删除"><h2>永久删除「{deleting.title}」？</h2><p>此操作无法撤销，记录将无法从回收站恢复。</p>{deleting.kind === 'object' && <p>同时删除相关知识关系、所属实验运行、修订历史及未被其他对象引用的附件；学习记录保留，画布卡片转为文本占位。含此对象的画布历史也会清理。</p>}{deleting.kind === 'relation' && <p>关系证据同时删除，画布连线转为局部连线，含此关系的画布历史也会清理。</p>}{deleting.kind === 'attachment' && <p>附件记录与本地附件文件同时删除。</p>}<ErrorBox message={error} /><div className="actions"><button className="danger" disabled={busy !== null} onClick={remove}>确认永久删除</button><button className="ghost" disabled={busy !== null} onClick={() => setDeleting(null)}>取消</button></div></section></div>}</>;
}
