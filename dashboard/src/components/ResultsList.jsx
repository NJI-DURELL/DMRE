/**
 * ResultsList.jsx — Container for search results, loading skeletons, and empty states.
 */

import MemoryCard from './MemoryCard'
import { SearchIcon } from './Icons'

function SkeletonCard() {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="flex items-start gap-4">
        <div className="skeleton w-8 h-8 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-2.5">
          <div className="skeleton h-4 w-3/4 rounded-md" />
          <div className="skeleton h-3 w-1/3 rounded-md" />
          <div className="skeleton h-3 w-full rounded-md mt-3" />
          <div className="skeleton h-3 w-5/6 rounded-md" />
          <div className="skeleton h-3 w-1/4 rounded-md mt-1" />
        </div>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-50 border border-slate-200
        flex items-center justify-center">
        <SearchIcon className="w-6 h-6 text-blue-600" />
      </div>
      <div>
        <p className="text-slate-700 font-medium">Search your memories</p>
        <p className="text-sm text-slate-500 mt-1 max-w-xs">
          Type a query, record your voice, or upload an image to retrieve
          semantically relevant pages from your browsing history.
        </p>
      </div>
    </div>
  )
}

function NoResults() {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-50 border border-slate-200
        flex items-center justify-center">
        <SearchIcon className="w-6 h-6 text-slate-400" />
      </div>
      <div>
        <p className="text-slate-900 font-semibold tracking-wide uppercase text-sm">
          You are yet to visit this page
        </p>
        <p className="text-sm text-slate-500 mt-2 max-w-xs">
          DMRE has no recorded memory matching your query.
          Browse the page first and it will be captured automatically.
        </p>
      </div>
    </div>
  )
}

export default function ResultsList({ results, loading, searched, query, rawQuery, notFound }) {
  if (loading) {
    return (
      <div className="mt-8 space-y-3">
        <div className="flex items-center gap-2 mb-4">
          <div className="skeleton h-3.5 w-32 rounded-md" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (!searched) return <EmptyState />

  if (results.length === 0 || notFound) return <NoResults />

  const best = results[0]
  const rest = results.slice(1)

  return (
    <div className="mt-8 space-y-3">
      <div className="flex items-center gap-2 px-0.5">
        <span className="w-2 h-2 rounded-full bg-blue-600 shadow-sm shadow-blue-300 animate-pulse" />
        <p className="text-xs text-blue-800 font-medium">Best match — click to open</p>
      </div>
      <MemoryCard result={best} rank={1} query={rawQuery} />

      {rest.length > 0 && (
        <>
          <div className="flex items-center justify-between pt-2 px-0.5">
            <p className="text-xs text-slate-500">
              Other matches
              {query && <> for <span className="text-slate-700">"{query}"</span></>}
            </p>
            <p className="text-xs text-slate-400">re-ranked by XGBoost</p>
          </div>
          {rest.map((result, i) => (
            <MemoryCard key={result.memory_id} result={result} rank={i + 2} query={rawQuery} />
          ))}
        </>
      )}
    </div>
  )
}
