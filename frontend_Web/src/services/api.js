export async function api(path, options = {}) {
  const workspaceId = localStorage.getItem('knowledge-workspace-id');
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'same-origin',
    headers: {
      ...(options.body instanceof FormData ? {} : {
        'Content-Type': 'application/json'
      }),
      ...(workspaceId ? {'X-Workspace-ID': workspaceId} : {}),
      ...options.headers
    }
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const error = new Error(typeof result.detail === 'string' ? result.detail : '请求失败，请检查内容与服务状态。');
    error.status = response.status;
    if (response.status === 401) window.dispatchEvent(new Event('auth-required'));
    throw error;
  }
  return response.json();
}
export const write = (path, data, method = 'POST') => api(path, {
  method,
  body: JSON.stringify(data)
});
