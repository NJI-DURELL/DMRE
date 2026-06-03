/**
 * LoginScreen.jsx — Sign-in / sign-up gate for the dashboard.
 * Calls /api/auth/login-json or /api/auth/signup and persists the token.
 */

import { useState } from 'react'
import { BrainIcon, SpinnerIcon } from './Icons'
import { login, signup } from '../services/auth'

/**
 * FastAPI's RequestValidationError default body is a list of objects.
 * Our backend already flattens these to strings, but be defensive against
 * older deployments / 4xx responses with mixed shapes.
 */
function flattenDetail(detail, fallback) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (typeof d === 'string' ? d : (d?.msg || JSON.stringify(d))))
      .filter(Boolean)
    if (parts.length) return parts.join('; ')
  }
  if (detail && typeof detail === 'object' && detail.msg) return String(detail.msg)
  return fallback
}

export default function LoginScreen({ onAuthenticated }) {
  const [mode, setMode]         = useState('login')
  const [email, setEmail]       = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const isSignup = mode === 'signup'

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!email || !password) {
      setError('Email and password are required.')
      return
    }
    if (isSignup && password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setLoading(true)
    try {
      const tokenResp = isSignup
        ? await signup(email.trim(), password, username.trim())
        : await login(email.trim(), password)
      onAuthenticated(tokenResp)
    } catch (err) {
      const fallback = err?.message || 'Authentication failed.'
      const isNetwork = !err?.response && /Network|fetch|timeout/i.test(fallback)
      const msg = isNetwork
        ? 'Cannot reach the DMRE backend. Check your connection.'
        : flattenDetail(err?.response?.data?.detail, fallback)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white text-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Wordmark */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <div className="w-10 h-10 rounded-xl bg-blue-600
            flex items-center justify-center shadow-md">
            <BrainIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-base font-semibold text-slate-900 tracking-tight">DMRE</div>
            <div className="text-xs text-slate-500">Digital Memory Reconstruction Engine</div>
          </div>
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h1 className="text-lg font-semibold text-slate-900 mb-1">
            {isSignup ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="text-xs text-slate-500 mb-5">
            {isSignup
              ? 'Your captured browsing history will be private to your account.'
              : 'Sign in to access your private memory store.'}
          </p>

          {error && (
            <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200
              rounded-lg text-xs text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-xs text-slate-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                className="w-full px-3 py-2.5 bg-white border border-slate-300 rounded-lg
                  text-sm text-slate-900 placeholder-slate-400 outline-none
                  focus:border-blue-600 focus:ring-1 focus:ring-blue-500/30 transition-colors"
                placeholder="you@example.com"
              />
            </div>

            {isSignup && (
              <div>
                <label className="block text-xs text-slate-700 mb-1">
                  Username <span className="text-slate-400">(optional)</span>
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  className="w-full px-3 py-2.5 bg-white border border-slate-300 rounded-lg
                    text-sm text-slate-900 placeholder-slate-400 outline-none
                    focus:border-blue-600 focus:ring-1 focus:ring-blue-500/30 transition-colors"
                  placeholder="jane"
                />
              </div>
            )}

            <div>
              <label className="block text-xs text-slate-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={isSignup ? 'new-password' : 'current-password'}
                required
                minLength={isSignup ? 8 : 1}
                className="w-full px-3 py-2.5 bg-white border border-slate-300 rounded-lg
                  text-sm text-slate-900 placeholder-slate-400 outline-none
                  focus:border-blue-600 focus:ring-1 focus:ring-blue-500/30 transition-colors"
                placeholder="••••••••"
              />
              {isSignup && (
                <p className="mt-1 text-[11px] text-slate-500">At least 8 characters.</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 bg-blue-600 hover:bg-blue-700
                disabled:bg-slate-100 disabled:text-slate-400 text-white text-sm
                font-semibold rounded-lg flex items-center justify-center gap-2
                transition-all shadow-sm"
            >
              {loading
                ? <><SpinnerIcon className="w-4 h-4" />Working…</>
                : (isSignup ? 'Create account' : 'Sign in')}
            </button>
          </form>

          <div className="text-center text-xs text-slate-500 mt-5">
            {isSignup ? 'Already have an account?' : "Don't have an account?"}
            {' '}
            <button
              type="button"
              onClick={() => { setMode(isSignup ? 'login' : 'signup'); setError('') }}
              className="text-blue-700 hover:text-blue-800 font-medium"
            >
              {isSignup ? 'Sign in' : 'Create one'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
