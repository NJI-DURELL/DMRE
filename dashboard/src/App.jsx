/**
 * App.jsx — DMRE dashboard root component.
 * Manages global search state and composes the header, search bar, and results list.
 */

import { useState } from 'react'
import SearchBar from './components/SearchBar'
import ResultsList from './components/ResultsList'
import { BrainIcon } from './components/Icons'
import { searchText, searchVoice, searchImage } from './services/api'

export default function App() {
  const [results, setResults]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [searched, setSearched] = useState(false)
  const [lastQuery, setLastQuery] = useState('')

  const handleSearch = async ({ type, query, audioBlob, imageFile }) => {
    setLoading(true)
    setError(null)

    try {
      let data
      if (type === 'text') {
        setLastQuery(query)
        data = await searchText(query)
      } else if (type === 'voice') {
        setLastQuery('voice query')
        data = await searchVoice(audioBlob)
        setLastQuery(data.query || 'voice query')
      } else if (type === 'image') {
        setLastQuery('image query')
        data = await searchImage(imageFile)
        setLastQuery(data.query || 'image query')
      }

      setResults(data.results || [])
      setSearched(true)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Search failed'
      setError(msg)
      setResults([])
      setSearched(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100">

      {/* Fixed header */}
      <header className="sticky top-0 z-10 bg-navy-950/90 backdrop-blur-md
        border-b border-navy-600/50">
        <div className="max-w-2xl mx-auto px-4 py-3.5 flex items-center justify-between">
          {/* Wordmark */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-violet-600
              flex items-center justify-center shadow-sm">
              <BrainIcon className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <span className="text-sm font-semibold text-white tracking-tight">DMRE</span>
              <span className="text-xs text-slate-600 ml-2 hidden sm:inline">
                Digital Memory Reconstruction Engine
              </span>
            </div>
          </div>

          {/* Status dot */}
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm
              shadow-emerald-500/50" />
            <span className="text-xs text-slate-600">Active</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-2xl mx-auto px-4 py-10">

        {/* Hero text — hidden once user has searched */}
        {!searched && (
          <div className="text-center mb-10 animate-fade-up">
            <h1 className="text-3xl font-bold text-white tracking-tight">
              Reconstruct your memory
            </h1>
            <p className="mt-3 text-slate-500 text-base leading-relaxed">
              Search every page you have ever visited using natural language,
              voice, or image — powered by Sentence-BERT and XGBoost re-ranking.
            </p>
          </div>
        )}

        {/* Search bar */}
        <SearchBar onSearch={handleSearch} loading={loading} />

        {/* Error banner */}
        {error && (
          <div className="mt-4 px-4 py-3 bg-red-900/30 border border-red-800/50
            rounded-xl text-sm text-red-400 animate-fade-up">
            {error}
          </div>
        )}

        {/* Results */}
        <ResultsList
          results={results}
          loading={loading}
          searched={searched}
          query={lastQuery}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-navy-600/40 mt-16 py-6">
        <p className="text-center text-xs text-slate-700">
          DMRE v1.0 &nbsp;·&nbsp; Sentence-BERT + XGBoost &nbsp;·&nbsp; Ganache integrity
        </p>
      </footer>
    </div>
  )
}
