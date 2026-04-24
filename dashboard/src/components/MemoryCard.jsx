/**
 * MemoryCard.jsx — Single search result card.
 * Shows title, domain, snippet, engagement metadata, and a Verify button that
 * calls the blockchain integrity endpoint and updates its state in place.
 */

import { useState } from 'react'
import { ShieldIcon, ShieldCheckIcon, ShieldXIcon, ClockIcon, LinkIcon, SpinnerIcon } from './Icons'
import { verifyMemory } from '../services/api'

const RANK_COLORS = [
  'from-amber-500 to-orange-500',   // 1
  'from-slate-400 to-slate-500',    // 2
  'from-orange-600 to-orange-700',  // 3
  'from-blue-600 to-blue-700',      // 4
  'from-blue-700 to-violet-700',    // 5
]

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function relativeTime(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
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

export default function MemoryCard({ result, rank }) {
  const [verifyState, setVerifyState] = useState('idle') // idle | loading | ok | fail
  const [verifyMsg, setVerifyMsg]     = useState('')

  const handleVerify = async () => {
    if (verifyState === 'loading') return
    setVerifyState('loading')
    try {
      const data = await verifyMemory(result.memory_id)
      setVerifyState(data.verified ? 'ok' : 'fail')
      setVerifyMsg(
        data.verified
          ? `Verified · block ${data.block_number}`
          : 'Hash mismatch — possible tampering'
      )
    } catch (err) {
      setVerifyState('fail')
      setVerifyMsg(err.response?.data?.detail || 'Verification unavailable')
    }
  }

  const scorePercent = Math.round(result.semantic_similarity * 100)

  return (
    <div className="group relative bg-navy-800 border border-navy-600 rounded-xl p-5
      hover:border-blue-500/40 transition-all duration-200 animate-fade-up
      hover:shadow-lg hover:shadow-blue-900/10">

      {/* Left accent bar on hover */}
      <div className="absolute left-0 top-4 bottom-4 w-0.5 rounded-full bg-blue-500
        opacity-0 group-hover:opacity-100 transition-opacity duration-200" />

      <div className="flex items-start gap-4">
        {/* Rank badge */}
        <div className={`
          flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
          text-xs font-bold text-white bg-gradient-to-br shadow-sm
          ${RANK_COLORS[(rank - 1) % RANK_COLORS.length]}
        `}>
          {rank}
        </div>

        <div className="flex-1 min-w-0">
          {/* Title */}
          <h3 className="text-[15px] font-semibold text-slate-100 leading-snug
            group-hover:text-white transition-colors truncate">
            {result.title || '(Untitled page)'}
          </h3>

          {/* Domain */}
          <div className="flex items-center gap-1.5 mt-1">
            <LinkIcon className="w-3 h-3 text-slate-600 flex-shrink-0" />
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-slate-500 hover:text-blue-400 transition-colors truncate"
            >
              {extractDomain(result.url)}
            </a>
          </div>

          {/* Snippet */}
          <p className="mt-2.5 text-[13px] text-slate-400 leading-relaxed line-clamp-2">
            {result.snippet || 'No preview available.'}
          </p>

          {/* Metadata row */}
          <div className="flex items-center flex-wrap gap-x-4 gap-y-2 mt-3">
            {/* Visited time */}
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <ClockIcon className="w-3.5 h-3.5" />
              <span>{relativeTime(result.visited_at)}</span>
            </div>

            {/* Dwell time */}
            {result.dwell_time > 0 && (
              <span className="text-xs text-slate-600">
                {formatDwell(result.dwell_time)} on page
              </span>
            )}

            {/* Relevance bar */}
            <div className="flex items-center gap-2 ml-auto">
              <div className="w-16 h-1 bg-navy-600 rounded-full overflow-hidden">
                <div
                  className="h-full score-fill rounded-full transition-all duration-500"
                  style={{ width: `${scorePercent}%` }}
                />
              </div>
              <span className="text-xs text-slate-600 tabular-nums w-8 text-right">
                {scorePercent}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mt-4 pt-3.5 border-t border-navy-600/60 flex items-center justify-between gap-3">
        {/* Verify result message */}
        <div className="text-xs text-slate-600 truncate">
          {verifyState === 'ok'   && <span className="text-emerald-500">{verifyMsg}</span>}
          {verifyState === 'fail' && <span className="text-red-400">{verifyMsg}</span>}
        </div>

        {/* Verify button */}
        <button
          onClick={handleVerify}
          disabled={verifyState === 'loading'}
          className={`
            flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg
            text-xs font-medium transition-all duration-200
            ${verifyState === 'idle'    && 'bg-navy-700 hover:bg-navy-600 text-slate-400 hover:text-slate-200 border border-navy-600'}
            ${verifyState === 'loading' && 'bg-navy-700 text-slate-500 border border-navy-600 cursor-not-allowed'}
            ${verifyState === 'ok'      && 'bg-emerald-900/40 text-emerald-400 border border-emerald-800/50'}
            ${verifyState === 'fail'    && 'bg-red-900/30 text-red-400 border border-red-800/40'}
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
