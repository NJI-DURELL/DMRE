/**
 * auth.js — Token storage + axios bootstrap for the dashboard.
 *
 * The token lives in localStorage under `dmre_auth`. The exported axios client
 * automatically attaches it as a Bearer header and clears it on 401.
 */

import axios from 'axios'

const STORAGE_KEY = 'dmre_auth'

// Vite proxy ('/api' -> http://localhost:8000/api) handles dev. In production
// the backend URL is set at build time via VITE_BACKEND_URL.
const baseURL = import.meta.env.VITE_BACKEND_URL
  ? `${import.meta.env.VITE_BACKEND_URL.replace(/\/$/, '')}/api`
  : '/api'

export const api = axios.create({ baseURL })

export function readAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    // Corrupted JSON, browser denying access (private mode), or storage
    // disabled. Treat as logged-out and move on.
    return null
  }
}

export function writeAuth(auth) {
  try {
    if (auth) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(auth))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // QuotaExceededError or storage unavailable — silently no-op so the
    // user can still use the session in-memory until they reload.
  }
}

export function getToken() {
  return readAuth()?.access_token || null
}

let onUnauthorized = null
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401) {
      writeAuth(null)
      if (onUnauthorized) onUnauthorized()
    }
    return Promise.reject(err)
  },
)

// ---------- Auth API ----------

export async function login(email, password) {
  const { data } = await api.post('/auth/login-json', { email, password })
  writeAuth(data)
  return data
}

export async function signup(email, password, username) {
  const { data } = await api.post('/auth/signup', {
    email,
    password,
    username: username || null,
  })
  writeAuth(data)
  return data
}

export async function fetchMe() {
  const { data } = await api.get('/auth/me')
  return data
}

export async function verifyEmail(code) {
  const { data } = await api.post('/auth/verify-email', { code })
  // The token already encodes the user_id; we just refresh the cached user
  // record so `email_verified` flips to true on the client without re-login.
  const cur = readAuth()
  if (cur) writeAuth({ ...cur, user: data })
  return data
}

export async function resendOtp() {
  const { data } = await api.post('/auth/resend-otp', {})
  return data
}

export function logout() {
  writeAuth(null)
}
