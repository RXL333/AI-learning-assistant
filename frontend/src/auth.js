import { reactive } from "vue";

const TOKEN_KEY = "token";
const USERNAME_KEY = "username";
const LOGIN_AT_KEY = "loginAt";
const REDIRECT_KEY = "postLoginRedirect";

let syncStarted = false;

function readToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function readUsername() {
  return localStorage.getItem(USERNAME_KEY) || "";
}

function readLoginAt() {
  const raw = sessionStorage.getItem(LOGIN_AT_KEY);
  return raw ? Number(raw) : 0;
}

export const authState = reactive({
  token: readToken(),
  username: readUsername(),
  loginAt: readLoginAt(),
});

export function setAuth(token, username) {
  const loginAt = Date.now();
  authState.token = token;
  authState.username = username;
  authState.loginAt = loginAt;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USERNAME_KEY, username);
  sessionStorage.setItem(LOGIN_AT_KEY, String(loginAt));
}

export function restoreAuthSession() {
  const token = readToken();
  const username = readUsername();
  const loginAt = readLoginAt();
  authState.token = token;
  authState.username = username;
  authState.loginAt = loginAt || (token ? Date.now() : 0);
  if (token && !loginAt) sessionStorage.setItem(LOGIN_AT_KEY, String(authState.loginAt));
}

export function updateUsername(username) {
  authState.username = username;
  localStorage.setItem(USERNAME_KEY, username);
}

export function clearAuth() {
  authState.token = "";
  authState.username = "";
  authState.loginAt = 0;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
  sessionStorage.removeItem(LOGIN_AT_KEY);
}

export function savePostLoginRedirect(path) {
  if (!path || path === "/login" || path === "/register") return;
  sessionStorage.setItem(REDIRECT_KEY, path);
}

export function consumePostLoginRedirect() {
  const path = sessionStorage.getItem(REDIRECT_KEY) || "/dashboard";
  sessionStorage.removeItem(REDIRECT_KEY);
  return path;
}

export function initAuthSync() {
  if (syncStarted) return;
  syncStarted = true;

  window.addEventListener("storage", (event) => {
    if (![TOKEN_KEY, USERNAME_KEY].includes(event.key)) return;
    restoreAuthSession();
  });

  window.addEventListener("pageshow", () => {
    restoreAuthSession();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") restoreAuthSession();
  });
}
