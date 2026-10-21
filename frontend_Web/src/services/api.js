import { msg } from "../i18n";
export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : {
        "Content-Type": "application/json"
      }),
      ...options.headers
    }
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const error = new Error(typeof result.detail === "string" ? result.detail : msg("请求失败，请检查内容与服务状态。"));
    error.status = response.status;
    throw error;
  }
  return response.json();
}
export const write = (path, data, method = "POST") => api(path, {
  method,
  body: JSON.stringify(data)
});
