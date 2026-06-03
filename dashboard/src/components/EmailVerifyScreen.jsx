/**
 * EmailVerifyScreen.jsx — Shown when the user is signed in but
 * email_verified=false. Blocks every other dashboard view until they
 * submit the 6-digit code or request a new one.
 */

import { useEffect, useState } from 'react'
import { BrainIcon, SpinnerIcon } from './Icons'
import { logout, resendOtp, verifyEmail } from '../services/auth'

const RESEND_COOLDOWN = 30 // seconds — must match OTP_RESEND_COOLDOWN_SECONDS server-side

function flattenDetail(detail, fallback) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => (typeof d === 'string' ? d : (d?.msg || ''))).filter(Boolean)
    if (parts.length) return parts.join('; ')
  }
  return fallback
}

export default function EmailVerifyScreen({ user, onVerified, onSignOut }) {
  const [code, setCode]         = useState('')
  const [error, setError]       = useState('')
  const [info, setInfo]         = useState('')
  const [loading, setLoading]   = useState(false)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const id = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(id)
  }, [cooldown])

  function handleCodeChange(e) {
    const next = e.target.value.replace(/\D/g, '').slice(0, 6)
    setCode(next)
    if (error) setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (code.length < 6 || loading) return
    setLoading(true)
    setError('')
    setInfo('')
    try {
      const me = await verifyEmail(code)
      if (me.email_verified) onVerified(me)
    } catch (err) {
      setError(flattenDetail(err?.response?.data?.detail, err.message || 'Verification failed.'))
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    if (cooldown > 0 || loading) return
    setLoading(true)
    setError('')
    setInfo('')
    try {
      await resendOtp()
      setInfo('A new code is on its way. Check your inbox.')
      setCooldown(RESEND_COOLDOWN)
    } catch (err) {
      const detail = flattenDetail(err?.response?.data?.detail, err.message || 'Could not resend.')
      // Server returns "Please wait Ns…" → start the local clock from that.
      const m = /wait\s+(\d+)s/.exec(detail)
      if (m) setCooldown(parseInt(m[1], 10))
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white text-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
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
          <h1 className="text-lg font-semibold text-slate-900 mb-1">Verify your email</h1>
          <p className="text-xs text-slate-500 mb-5">
            We sent a 6-digit code to <span className="font-medium text-slate-700">{user.email}</span>.
            Enter it below to unlock your DMRE account.
          </p>

          {error && (
            <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200
              rounded-lg text-xs text-red-700">{error}</div>
          )}
          {info && !error && (
            <div className="mb-3 px-3 py-2 bg-blue-50 border border-blue-200
              rounded-lg text-xs text-blue-800">{info}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="text"
              inputMode="numeric"
              pattern="\d*"
              autoComplete="one-time-code"
              value={code}
              onChange={handleCodeChange}
              placeholder="123 456"
              maxLength={6}
              autoFocus
              className="w-full text-center tracking-[0.5em] font-mono text-2xl
                py-3 bg-white border border-slate-300 rounded-lg
                text-slate-900 placeholder-slate-300 outline-none
                focus:border-blue-600 focus:ring-1 focus:ring-blue-500/30 transition-colors"
            />
            <button
              type="submit"
              disabled={code.length < 6 || loading}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700
                disabled:bg-slate-100 disabled:text-slate-400 text-white text-sm
                font-semibold rounded-lg flex items-center justify-center gap-2
                transition-all shadow-sm"
            >
              {loading
                ? <><SpinnerIcon className="w-4 h-4" />Verifying…</>
                : 'Verify email'}
            </button>
          </form>

          <div className="flex items-center justify-between mt-5 text-xs">
            <button
              type="button"
              onClick={handleResend}
              disabled={cooldown > 0 || loading}
              className="text-blue-700 hover:text-blue-800 font-medium
                disabled:text-slate-400 disabled:cursor-not-allowed"
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
            </button>
            <button
              type="button"
              onClick={onSignOut}
              className="text-slate-500 hover:text-slate-900"
            >
              Sign out
            </button>
          </div>
        </div>

        <p className="text-center text-[11px] text-slate-400 mt-6">
          Wrong address? Sign out and create a new account.
        </p>
      </div>
    </div>
  )
}
