import { authState, clearAuth, restoreAuthSession } from "./auth.js";
import { showToast } from "./toast.js";

restoreAuthSession();

const DEFAULT_TIMEOUT = 60000;
let handlingUnauthorized = false;

function withTimeout(timeoutMs = DEFAULT_TIMEOUT) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  return { controller, timer };
}

function handleUnauthorized(message) {
  if (handlingUnauthorized) throw new Error(message);
  handlingUnauthorized = true;
  clearAuth();
  window.location.hash = "#/login";
  showToast(message, "error");
  window.setTimeout(() => {
    handlingUnauthorized = false;
  }, 800);
  throw new Error(message);
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (authState.token) headers.Authorization = `Bearer ${authState.token}`;

  const { controller, timer } = withTimeout(options.timeoutMs);
  let res;
  let data = {};

  try {
    res = await fetch(`/api${path}`, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });
    try {
      data = await res.json();
    } catch {
      data = { code: res.ok ? 0 : res.status, message: res.statusText || "请求失败", data: {} };
    }
  } catch (error) {
    window.clearTimeout(timer);
    if (error.name === "AbortError") {
      const text = "请求超时，请稍后重试";
      showToast(text, "error");
      throw new Error(text);
    }
    const text = error.message || "网络异常，请检查连接后重试";
    showToast(text, "error");
    throw error;
  }

  window.clearTimeout(timer);

  if (res.status === 401) {
    const text = data.detail || data.message || "登录已失效，请重新登录";
    handleUnauthorized(text);
  }

  if (!res.ok && typeof data.code === "undefined") {
    const text = data.message || "请求失败";
    showToast(text, "error");
    throw new Error(text);
  }

  if (data.code && data.code !== 0) {
    showToast(data.message || "操作失败", "error");
  }

  return data;
}
