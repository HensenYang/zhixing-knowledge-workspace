// Previous / next controls for a paged list. Renders nothing when everything fits on one page.
export default function Pager({ total, limit, offset, onChange }) {
  if (total <= limit) return null;
  const last = Math.min(offset + limit, total);
  return <nav className="pager" aria-label="分页">
    <button type="button" className="ghost" disabled={offset <= 0} onClick={() => onChange(Math.max(0, offset - limit))}>上一页</button>
    <span role="status">第 {offset + 1}–{last} 条，共 {total} 条</span>
    <button type="button" className="ghost" disabled={last >= total} onClick={() => onChange(offset + limit)}>下一页</button>
  </nav>;
}
