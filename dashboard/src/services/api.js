/**
 * api.js — DMRE backend API wrappers
 * All calls proxy through Vite's /api prefix to http://localhost:8000.
 * Each function throws on non-2xx so callers can handle errors uniformly.
 */

import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

/** Semantic text search — returns SearchResponse */
export async function searchText(query, topK = 5) {
  const { data } = await client.post('/search/text', { query, top_k: topK })
  return data
}

/** Voice search — accepts a Blob (WebM/OGG) from MediaRecorder */
export async function searchVoice(audioBlob) {
  const ext = audioBlob.type.includes('ogg') ? 'ogg' : 'webm'
  const form = new FormData()
  form.append('file', audioBlob, `recording.${ext}`)
  const { data } = await client.post('/search/voice', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** Image search — accepts a File object from an <input type="file"> */
export async function searchImage(imageFile) {
  const form = new FormData()
  form.append('file', imageFile)
  const { data } = await client.post('/search/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** Blockchain integrity verification for a single memory */
export async function verifyMemory(memoryId) {
  const { data } = await client.get(`/verify/${memoryId}`)
  return data
}
