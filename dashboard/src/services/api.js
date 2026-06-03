/**
 * api.js — DMRE backend API wrappers.
 * All requests go through the auth-aware axios client (auth.js), which
 * attaches the JWT bearer token automatically and clears it on 401.
 */

import { api } from './auth'

/** Semantic text search — returns SearchResponse */
export async function searchText(query, topK = 5) {
  const { data } = await api.post('/search/text', { query, top_k: topK })
  return data
}

/** Voice search — accepts a Blob (WebM/OGG) from MediaRecorder */
export async function searchVoice(audioBlob) {
  const ext = audioBlob.type.includes('ogg') ? 'ogg' : 'webm'
  const form = new FormData()
  form.append('file', audioBlob, `recording.${ext}`)
  const { data } = await api.post('/search/voice', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** Image search — accepts a File object from an <input type="file"> */
export async function searchImage(imageFile) {
  const form = new FormData()
  form.append('file', imageFile)
  const { data } = await api.post('/search/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** Blockchain integrity verification for a single memory */
export async function verifyMemory(memoryId) {
  const { data } = await api.get(`/verify/${memoryId}`)
  return data
}

// ---------- Activity / History ----------

/** Recent captures (newest first) for the current user. */
export async function listMemories(limit = 50, offset = 0) {
  const { data } = await api.get('/memories', { params: { limit, offset } })
  return data
}

/** Recent search queries (newest first) for the current user. */
export async function listQueries(limit = 50, offset = 0) {
  const { data } = await api.get('/queries', { params: { limit, offset } })
  return data
}

/** Permanently delete one of the current user's captured memories. */
export async function deleteMemory(memoryId) {
  await api.delete(`/memories/${memoryId}`)
}

/** Permanently delete the current account and all its data. */
export async function deleteAccount() {
  await api.delete('/account')
}

// ---------- Email export ----------

/** Email the current user a copy of these search results. */
export async function emailSearchResults(query, topK = 10) {
  const { data } = await api.post('/search/email-export', { query, top_k: topK })
  return data
}

/** Email the current user a digest of recent captures + search history. */
export async function emailActivityDigest() {
  const { data } = await api.post('/queries/email-export', {})
  return data
}
