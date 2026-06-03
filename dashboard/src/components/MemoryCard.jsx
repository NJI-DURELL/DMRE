/**
 * MemoryCard.jsx — Single search result card (light theme).
 */

import { useState } from 'react'
import { ShieldIcon, ShieldCheckIcon, ShieldXIcon, ClockIcon, SpinnerIcon } from './Icons'
import { verifyMemory } from '../services/api'
import { buildFragmentUrl } from '../utils/textFragment'

const RANK_COLORS = [
  'bg-blue-600',
  'bg-blue-400',
  'bg-blue-300 text-blue-800',
  'bg-blue-100 text-blue-800',
  'bg-blue-100 text-blue-800',
]

function extractDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

function faviconUrl(url) {
  try {
    const domain = new URL(url).hostname
    return `https://www.google.com/s2/favicons?sz=32&domain=${domain}`
  } catch { return null }
}

function relativeTime(isoString) {
  const diff  = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (days > 0)  return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (mins > 0)  return `${mins}m ago`
  return 'just now'
}

function formatDwell(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

function highlightText(text, query) {
  if (!query || !text) return [text]
  const tokens = [...new Set(
    query.toLowerCase().split(/\s+/).filter(t => t.length > 2)
  )]
  if (tokens.length === 0) return [text]

  const pattern = new RegExp(`(${tokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  const parts   = text.split(pattern)

  return parts.map((part, i) =>
    pattern.test(part)
      ? <mark key={i} className="bg-blue-100 text-blue-800 rounded px-0.5">{part}</mark>
      : part
  )
}

export default function MemoryCard({ result, rank, query }) {
  const [verifyState, setVerifyState] = useState('idle')
  const [verifyMsg,   setVerifyMsg]   = useState('')
  const [expanded,    setExpanded]    = useState(false)

  const handleVerify = async () => {
    if (verifyState === 'loading') return
    setVerifyState('loading')
    try {
      const data = await verifyMemory(result.memory_id)
      setVerifyState(data.verified ? 'ok' : 'fail')
      setVerifyMsg(data.verified ? `Verified · block ${data.block_number}` : 'Hash mismatch — possible tampering')
    } catch (err) {
      setVerifyState('fail')
      setVerifyMsg(err.response?.data?.detail || 'Verification unavailable')
    }
  }

  const openPage  = () => window.open(buildFragmentUrl(result.url, result.snippet, query), '_blank', 'noopener,noreferrer')
  const scorePercent = Math.round(result.semantic_similarity * 100)
  const favicon   = faviconUrl(result.url)
  const domain    = extractDomain(result.url)

  const snippetShort  = result.snippet?.slice(0, 300) || ''
  const snippetFull   = result.snippet || ''
  const hasMore       = snippetFull.length > 300
  const displayText   = expanded ? snippetFull : snippetShort

  return (
    <div
      onClick={openPage}
      className="group relative bg-white border border-slate-200 rounded-xl p-5
        hover:border-blue-300 transition-all duration-200 animate-fade-up
        hover:shadow-md hover:shadow-blue-100 cursor-pointer"
    >
      <div className="absolute left-0 top-4 bottom-4 w-0.5 rounded-full bg-blue-600
        opacity-0 group-hover:opacity-100 transition-opacity duration-200" />

      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 flex flex-col items-center gap-1.5">
          {favicon ? (
            <img
              src={favicon}
              alt={domain}
              className="w-8 h-8 rounded-lg object-contain bg-slate-100 p-1"
              onError={(e) => { e.currentTarget.style.display = 'none' }}
            />
          ) : (
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center
              text-xs font-bold text-white shadow-sm
              ${RANK_COLORS[(rank - 1) % RANK_COLORS.length]}`}>
              {rank}
            </div>
          )}
          {favicon && (
            <div className={`w-5 h-5 rounded-md flex items-center justify-center
              text-[10px] font-bold text-white
              ${RANK_COLORS[(rank - 1) % RANK_COLORS.length]}`}>
              {rank}
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-[15px] font-semibold text-slate-900 leading-snug
              group-hover:text-blue-800 transition-colors line-clamp-2">
              {highlightText(result.title || '(Untitled page)', query)}
            </h3>
            <span className="flex-shrink-0 text-xs text-slate-400
              group-hover:text-blue-600 transition-colors mt-0.5">↗</span>
          </div>

          <div className="flex items-center gap-1.5 mt-1">
            <span className="text-xs text-slate-500 group-hover:text-blue-700
              transition-colors truncate">{domain}</span>
          </div>

          <p className="mt-2.5 text-[13px] text-slate-700 leading-relaxed">
            {highlightText(displayText, query)}
            {!expanded && hasMore && (
              <button
                onClick={(e) => { e.stopPropagation(); setExpanded(true) }}
                className="ml-1 text-blue-700 hover:text-blue-800 text-xs font-medium"
              >
                show more
              </button>
            )}
            {expanded && (
              <button
                onClick={(e) => { e.stopPropagation(); setExpanded(false) }}
                className="ml-1 text-blue-700 hover:text-blue-800 text-xs font-medium"
              >
                show less
              </button>
            )}
          </p>

          <div className="flex items-center flex-wrap gap-x-4 gap-y-2 mt-3">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <ClockIcon className="w-3.5 h-3.5" />
              <span>{relativeTime(result.visited_at)}</span>
            </div>
            {result.dwell_time > 0 && (
              <span className="text-xs text-slate-500">{formatDwell(result.dwell_time)} read</span>
            )}
            {result.visit_count > 1 && (
              <span className="text-xs text-slate-500">{result.visit_count}× visited</span>
            )}
            <div className="flex items-center gap-2 ml-auto">
              <div className="w-16 h-1 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full score-fill rounded-full transition-all duration-500"
                  style={{ width: `${scorePercent}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 tabular-nums w-8 text-right">
                {scorePercent}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <div
        className="mt-4 pt-3.5 border-t border-slate-200 flex items-center justify-between gap-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-xs text-slate-500 truncate">
          {verifyState === 'ok'   && <span className="text-blue-800">{verifyMsg}</span>}
          {verifyState === 'fail' && <span className="text-red-600">{verifyMsg}</span>}
        </div>
        <button
          onClick={handleVerify}
          disabled={verifyState === 'loading'}
          className={`
            flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg
            text-xs font-medium transition-all duration-200
            ${verifyState === 'idle'    && 'bg-slate-100 hover:bg-blue-100 text-slate-700 hover:text-blue-800 border border-slate-200'}
            ${verifyState === 'loading' && 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'}
            ${verifyState === 'ok'      && 'bg-blue-100 text-blue-800 border border-blue-200'}
            ${verifyState === 'fail'    && 'bg-red-50 text-red-700 border border-red-200'}
          `}
        >
          {verifyState === 'idle'    && <><ShieldIcon className="w-3.5 h-3.5" />Verify</>}
          {verifyState === 'loading' && <><SpinnerIcon className="w-3.5 h-3.5" />Checking…</>}
          {verifyState === 'ok'      && <><ShieldCheckIcon className="w-3.5 h-3.5" />Verified</>}
          {verifyState === 'fail'    && <><ShieldXIcon className="w-3.5 h-3.5" />Failed</>}
        </button>
      </div>
    </div>
  )
}
