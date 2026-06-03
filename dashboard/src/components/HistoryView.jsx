/**
 * HistoryView.jsx — User's private activity log.
 *
 * Two panes: Captures (recent pages saved by the extension) and Searches
 * (queries the user submitted). Each capture row has a delete button.
 * A "Delete account" button at the bottom wipes everything (privacy
 * compliance for the Chrome Web Store).
 */

import { useEffect, useState } from 'react'
import { ClockIcon, SearchIcon, ShieldXIcon, SpinnerIcon } from './Icons'
import {
  deleteAccount,
  deleteMemory,
  emailActivityDigest,
  listMemories,
  listQueries,
} from '../services/api'

function relativeTime(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  const h = Math.floor(diff / 3600000)
  const d = Math.floor(diff / 86400000)
  if (d > 0) return `${d}d ago`
  if (h > 0) return `${h}h ago`
  if (m > 0) return `${m}m ago`
  return 'just now'
}

function formatDwell(seconds) {
  if (!seconds || seconds < 1) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

function extractDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

function faviconUrl(url) {
  try {
    const d = new URL(url).hostname
    return `https://www.google.com/s2/favicons?sz=32&domain=${d}`
  } catch { return null }
}

export default function HistoryView({ onAccountDeleted }) {
  const [pane, setPane]         = useState('captures') // 'captures' | 'searches'
  const [captures, setCaptures] = useState([])
  const [queries, setQueries]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [deleting, setDeleting] = useState(null)
  const [confirmingWipe, setConfirmingWipe] = useState(false)
  const [emailing, setEmailing] = useState(false)
  const [emailToast, setEmailToast] = useState('')

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      const [m, q] = await Promise.all([listMemories(100), listQueries(100)])
      setCaptures(m)
      setQueries(q)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load history.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  async function handleDelete(id) {
    if (deleting) return
    setDeleting(id)
    try {
      await deleteMemory(id)
      setCaptures((prev) => prev.filter((c) => c.id !== id))
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Delete failed.')
    } finally {
      setDeleting(null)
    }
  }

  async function handleWipe() {
    try {
      await deleteAccount()
      onAccountDeleted?.()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Account deletion failed.')
      setConfirmingWipe(false)
    }
  }

  async function handleEmailDigest() {
    if (emailing) return
    setEmailing(true)
    setEmailToast('')
    try {
      const r = await emailActivityDigest()
      setEmailToast(`Sent your activity digest to ${r.sent_to}.`)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setEmailToast(typeof detail === 'string' ? detail : (err.message || 'Could not send email.'))
    } finally {
      setEmailing(false)
      setTimeout(() => setEmailToast(''), 6000)
    }
  }

  return (
    <div className="mt-6">
      {/* Pane switcher */}
      <div className="flex gap-1 mb-4 bg-slate-50 p-1 rounded-xl border border-slate-200">
        <button
          onClick={() => setPane('captures')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all
            ${pane === 'captures'
              ? 'bg-white text-slate-900 shadow-sm border border-slate-200'
              : 'text-slate-500 hover:text-slate-900'}`}
        >
          Captured pages ({captures.length})
        </button>
        <button
          onClick={() => setPane('searches')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all
            ${pane === 'searches'
              ? 'bg-white text-slate-900 shadow-sm border border-slate-200'
              : 'text-slate-500 hover:text-slate-900'}`}
        >
          Search history ({queries.length})
        </button>
      </div>

      {error && (
        <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg
          text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 mb-3">
        {emailToast && <span className="text-xs text-slate-500">{emailToast}</span>}
        <button
          onClick={handleEmailDigest}
          disabled={emailing}
          className="text-xs px-3 py-1.5 rounded-md border border-slate-200
            bg-white hover:bg-blue-50 text-blue-700 hover:text-blue-800
            font-medium disabled:opacity-50 transition-colors"
          title="Email yourself a copy of your captures + searches"
        >
          {emailing ? 'Sending…' : '✉ Email me my activity'}
        </button>
      </div>

      {loading ? (
        <div className="py-16 flex items-center justify-center text-slate-500">
          <SpinnerIcon className="w-5 h-5 mr-2" /> Loading…
        </div>
      ) : pane === 'captures' ? (
        captures.length === 0 ? (
          <EmptyMessage
            title="No pages captured yet"
            body="Browse the web with the DMRE extension enabled and your captures will appear here."
          />
        ) : (
          <ul className="space-y-2">
            {captures.map((c) => {
              const fav = faviconUrl(c.url)
              return (
                <li key={c.id}
                    className="flex items-start gap-3 p-3 bg-white border border-slate-200
                      rounded-xl hover:border-blue-300 transition-colors">
                  {fav
                    ? <img src={fav} alt="" className="w-7 h-7 rounded-md mt-0.5 flex-shrink-0" />
                    : <div className="w-7 h-7 rounded-md bg-slate-100 flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <a href={c.url} target="_blank" rel="noopener noreferrer"
                       className="text-sm font-medium text-slate-900 hover:text-blue-700
                         truncate block">
                      {c.title || '(untitled)'}
                    </a>
                    <div className="text-xs text-slate-500 truncate">{extractDomain(c.url)}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      <ClockIcon className="w-3 h-3 inline -mt-0.5" /> {relativeTime(c.visited_at)}
                      &nbsp;·&nbsp; {formatDwell(c.dwell_time)} read
                      {c.visit_count > 1 && <> &nbsp;·&nbsp; {c.visit_count}× visited</>}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(c.id)}
                    disabled={deleting === c.id}
                    className="flex-shrink-0 px-2.5 py-1 text-xs text-red-600
                      hover:bg-red-50 rounded-md disabled:opacity-50"
                    title="Delete this memory"
                  >
                    {deleting === c.id ? '…' : 'Delete'}
                  </button>
                </li>
              )
            })}
          </ul>
        )
      ) : (
        queries.length === 0 ? (
          <EmptyMessage
            title="No searches yet"
            body="When you search for something, the query is logged so you can revisit your past lookups."
          />
        ) : (
          <ul className="space-y-2">
            {queries.map((q) => (
              <li key={q.id}
                  className="flex items-center gap-3 p-3 bg-white border border-slate-200 rounded-xl">
                <SearchIcon className="w-4 h-4 text-blue-700 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-slate-900 truncate">"{q.query_text}"</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {q.query_type} &nbsp;·&nbsp; {q.result_count} result{q.result_count === 1 ? '' : 's'}
                    &nbsp;·&nbsp; {relativeTime(q.created_at)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )
      )}

      {/* Danger zone */}
      <div className="mt-10 pt-6 border-t border-slate-200">
        <h3 className="text-sm font-semibold text-slate-700">Danger zone</h3>
        <p className="text-xs text-slate-500 mt-1">
          Permanently delete your account and every page you have captured.
          This cannot be undone.
        </p>
        {!confirmingWipe ? (
          <button
            onClick={() => setConfirmingWipe(true)}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs
              text-red-700 bg-red-50 hover:bg-red-100 border border-red-200
              rounded-md font-medium"
          >
            <ShieldXIcon className="w-3.5 h-3.5" />
            Delete my account
          </button>
        ) : (
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={handleWipe}
              className="px-3 py-1.5 text-xs text-white bg-red-600 hover:bg-red-700
                rounded-md font-medium"
            >
              Yes, wipe everything
            </button>
            <button
              onClick={() => setConfirmingWipe(false)}
              className="px-3 py-1.5 text-xs text-slate-700 bg-white hover:bg-slate-100
                border border-slate-300 rounded-md"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyMessage({ title, body }) {
  return (
    <div className="py-16 text-center">
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">{body}</p>
    </div>
  )
}
