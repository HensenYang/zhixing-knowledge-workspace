import { msg } from "../i18n";
async function request(path, options = {}) {
  const workspaceId = localStorage.getItem('knowledge-workspace-id');
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'same-origin',
    headers: {
      ...(options.body instanceof FormData ? {} : {
        "Content-Type": "application/json"
      }),
      ...(workspaceId ? {'X-Workspace-ID': workspaceId} : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const error = new Error(typeof result.detail === "string" ? result.detail : result.detail?.message || msg("请求失败，请检查内容与服务状态。"));
    error.status = response.status;
    error.existingImport = result.detail?.existing_import;
    if (response.status === 401) window.dispatchEvent(new Event('auth-required'));
    throw error;
  }
  return response;
}
export async function api(path, options = {}) {
  return (await request(path, options)).json();
}
// List endpoints return plain JSON plus the number of matching records in X-Total-Count.
export async function apiPage(path, options = {}) {
  const response = await request(path, options);
  const items = await response.json();
  const total = Number(response.headers.get('X-Total-Count'));
  return {
    items,
    total: Number.isFinite(total) && response.headers.has('X-Total-Count') ? total : (Array.isArray(items) ? items.length : 0)
  };
}
export const write = (path, data, method = "POST") => api(path, {
  method,
  body: JSON.stringify(data)
});
