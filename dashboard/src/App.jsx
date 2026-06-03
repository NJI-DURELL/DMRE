/**
 * App.jsx — DMRE dashboard root component.
 * Gates the search UI behind authentication and adds a Search/History tab
 * pair so each user can audit and prune their own captured data.
 */

import { useEffect, useState } from 'react'
import SearchBar from './components/SearchBar'
import ResultsList from './components/ResultsList'
import LoginScreen from './components/LoginScreen'
import HistoryView from './components/HistoryView'
import AdminView from './components/AdminView'
import EmailVerifyScreen from './components/EmailVerifyScreen'
import { BrainIcon } from './components/Icons'
import { emailSearchResults, searchText, searchVoice, searchImage } from './services/api'
import { fetchMe, logout, readAuth, setUnauthorizedHandler, writeAuth } from './services/auth'

const TAB_SEARCH  = 'search'
const TAB_HISTORY = 'history'
const TAB_ADMIN   = 'admin'

export default function App() {
  const [user, setUser]           = useState(null)
  const [authChecked, setChecked] = useState(false)
  const [tab, setTab]             = useState(TAB_SEARCH)
  const [results, setResults]     = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [searched, setSearched]   = useState(false)
  const [lastQuery, setLastQuery] = useState('')
  const [notFound, setNotFound]   = useState(false)
  const [emailing, setEmailing]     = useState(false)
  const [emailToast, setEmailToast] = useState('')

  // ---- Boot: validate stored token ----
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))

    const stored = readAuth()
    if (!stored?.access_token) {
      setChecked(true)
      return
    }
    fetchMe()
      .then((me) => setUser(me))
      .catch(() => {
        writeAuth(null)
        setUser(null)
      })
      .finally(() => setChecked(true))
  }, [])

  if (!authChecked) {
    return <div className="min-h-screen bg-white" />
  }

  if (!user) {
    return (
      <LoginScreen
        onAuthenticated={(tokenResp) => setUser(tokenResp.user)}
      />
    )
  }

  // Email-verification gate — only verify-email / resend-otp / sign-out are
  // reachable until the user enters the 6-digit code from their inbox.
  if (!user.email_verified) {
    return (
      <EmailVerifyScreen
        user={user}
        onVerified={(me) => setUser(me)}
        onSignOut={() => { logout(); setUser(null) }}
      />
    )
  }

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
      setNotFound(data.not_found || false)
      setSearched(true)
    } catch (err) {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : (err.message || 'Search failed')
      setError(msg)
      setResults([])
      setNotFound(false)
      setSearched(true)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    setUser(null)
    setResults([])
    setSearched(false)
    setLastQuery('')
  }

  const handleEmailResults = async () => {
    if (!searched || !results.length || emailing) return
    setEmailing(true)
    setEmailToast('')
    try {
      const r = await emailSearchResults(lastQuery, Math.max(results.length, 5))
      setEmailToast(`Sent ${r.items} result(s) to ${r.sent_to}.`)
    } catch (err) {
      const detail = err.response?.data?.detail
      setEmailToast(typeof detail === 'string' ? detail : (err.message || 'Could not send email.'))
    } finally {
      setEmailing(false)
      setTimeout(() => setEmailToast(''), 6000)
    }
  }

  return (
    <div className="min-h-screen bg-white text-slate-900">

      {/* Fixed header */}
      <header className="sticky top-0 z-10 bg-white/85 backdrop-blur-md
        border-b border-slate-200">
        <div className="max-w-2xl mx-auto px-4 py-3.5 flex items-center justify-between">
          {/* Wordmark */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600
              flex items-center justify-center shadow-sm">
              <BrainIcon className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <span className="text-sm font-semibold text-slate-900 tracking-tight">DMRE</span>
              <span className="text-xs text-slate-400 ml-2 hidden sm:inline">
                Digital Memory Reconstruction Engine
              </span>
            </div>
          </div>

          {/* Account + status */}
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline text-xs text-slate-500" title={user.email}>
              {user.username || user.email}
            </span>
            <span className="w-2 h-2 rounded-full bg-blue-600 shadow-sm
              shadow-blue-300" />
            <button
              onClick={handleLogout}
              className="text-xs text-slate-500 hover:text-slate-900 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="max-w-3xl mx-auto px-4 pb-2 flex gap-4">
          <TabButton active={tab === TAB_SEARCH}  onClick={() => setTab(TAB_SEARCH)}>Search</TabButton>
          <TabButton active={tab === TAB_HISTORY} onClick={() => setTab(TAB_HISTORY)}>History</TabButton>
          {user.is_admin && (
            <TabButton active={tab === TAB_ADMIN} onClick={() => setTab(TAB_ADMIN)}>Admin</TabButton>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className={`mx-auto px-4 py-8 ${tab === TAB_ADMIN ? 'max-w-4xl' : 'max-w-2xl'}`}>
        {tab === TAB_SEARCH ? (
          <>
            {!searched && (
              <div className="text-center mb-8 animate-fade-up">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
                  Reconstruct your memory
                </h1>
                <p className="mt-3 text-slate-500 text-base leading-relaxed">
                  Search every page you have ever visited using natural language,
                  voice, or image — powered by Sentence-BERT and XGBoost re-ranking.
                </p>
              </div>
            )}

            <SearchBar onSearch={handleSearch} loading={loading} />

            {error && (
              <div className="mt-4 px-4 py-3 bg-red-50 border border-red-200
                rounded-xl text-sm text-red-700 animate-fade-up">
                {error}
              </div>
            )}

            {searched && results.length > 0 && (
              <div className="mt-4 flex items-center justify-end gap-3">
                {emailToast && (
                  <span className="text-xs text-slate-500">{emailToast}</span>
                )}
                <button
                  onClick={handleEmailResults}
                  disabled={emailing}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200
                    bg-white hover:bg-blue-50 text-blue-700 hover:text-blue-800
                    font-medium disabled:opacity-50 transition-colors"
                  title="Send these results to your email"
                >
                  {emailing ? 'Sending…' : '✉ Email me these results'}
                </button>
              </div>
            )}

            <ResultsList
              results={results}
              loading={loading}
              searched={searched}
              query={lastQuery}
              rawQuery={lastQuery}
              notFound={notFound}
            />
          </>
        ) : tab === TAB_HISTORY ? (
          <HistoryView onAccountDeleted={handleLogout} />
        ) : tab === TAB_ADMIN && user.is_admin ? (
          <AdminView currentUserId={user.id} />
        ) : null}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 mt-16 py-6">
        <p className="text-center text-xs text-slate-400">
          DMRE v1.0 &nbsp;·&nbsp; Sentence-BERT + XGBoost &nbsp;·&nbsp; Blockchain integrity
        </p>
      </footer>
    </div>
  )
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`text-sm font-medium pb-2 -mb-px border-b-2 transition-colors
        ${active
          ? 'text-blue-800 border-blue-600'
          : 'text-slate-500 border-transparent hover:text-slate-900'}`}
    >
      {children}
    </button>
  )
}
