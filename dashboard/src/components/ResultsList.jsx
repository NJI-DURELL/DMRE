/**
 * ResultsList.jsx — Container for search results, loading skeletons, and empty states.
 * Handles three distinct states: pre-search idle, loading, and populated results.
 */

import MemoryCard from './MemoryCard'
import { SearchIcon } from './Icons'

function SkeletonCard() {
  return (
    <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
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
      <div className="w-14 h-14 rounded-2xl bg-navy-800 border border-navy-600
        flex items-center justify-center">
        <SearchIcon className="w-6 h-6 text-slate-600" />
      </div>
      <div>
        <p className="text-slate-400 font-medium">Search your memories</p>
        <p className="text-sm text-slate-600 mt-1 max-w-xs">
          Type a query, record your voice, or upload an image to retrieve
          semantically relevant pages from your browsing history.
        </p>
      </div>
    </div>
  )
}

function NoResults({ query }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
      <p className="text-slate-400 font-medium">No results for "{query}"</p>
      <p className="text-sm text-slate-600 max-w-xs">
        Try a different query, or browse more pages first so the engine has
        memories to retrieve.
      </p>
    </div>
  )
}

export default function ResultsList({ results, loading, searched, query }) {
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

  if (results.length === 0) return <NoResults query={query} />

  return (
    <div className="mt-8 space-y-3">
      {/* Result count header */}
      <div className="flex items-center justify-between mb-1 px-0.5">
        <p className="text-xs text-slate-600">
          <span className="text-slate-400 font-medium">{results.length}</span> results
          {query && <> for <span className="text-slate-400">"{query}"</span></>}
        </p>
        <p className="text-xs text-slate-600">re-ranked by XGBoost</p>
      </div>

      {results.map((result, i) => (
        <MemoryCard key={result.memory_id} result={result} rank={i + 1} />
      ))}
    </div>
  )
}

