/**
 * AdminView.jsx — Operational stats + user roster.
 * Visible ONLY to users with is_admin=true. Calls /api/admin/* endpoints.
 * Deliberately exposes no per-user content — only counts and timestamps.
 */

import { useEffect, useState } from 'react'
import { SpinnerIcon, ShieldXIcon } from './Icons'
import { api } from '../services/auth'

function relativeTime(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  const h = Math.floor(diff / 3600000)
  const d = Math.floor(diff / 86400000)
  if (d > 0) return `${d}d ago`
  if (h > 0) return `${h}h ago`
  if (m > 0) return `${m}m ago`
  return 'just now'
}

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="text-2xl font-semibold text-slate-900 mt-1 tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function AdminView({ currentUserId }) {
  const [stats,   setStats]   = useState(null)
  const [users,   setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [deleting, setDeleting] = useState(null)

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      const [s, u] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/users', { params: { limit: 100 } }),
      ])
      setStats(s.data)
      setUsers(u.data)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : (err.message || 'Failed to load admin data.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  async function handleDeleteUser(uid) {
    if (deleting) return
    if (!confirm('Permanently delete this user and all their data? This cannot be undone.')) return
    setDeleting(uid)
    try {
      await api.delete(`/admin/users/${uid}`)
      setUsers((prev) => prev.filter((u) => u.id !== uid))
      // Refresh stats since totals just dropped.
      const s = await api.get('/admin/stats')
      setStats(s.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Delete failed.')
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return (
      <div className="py-16 flex items-center justify-center text-slate-500">
        <SpinnerIcon className="w-5 h-5 mr-2" /> Loading admin data…
      </div>
    )
  }

  return (
    <div className="mt-6 space-y-6">
      {error && (
        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          {error}
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">System health</h2>
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatCard label="Total users"           value={stats.total_users}
                      sub={`${stats.admins} admin${stats.admins === 1 ? '' : 's'}`} />
            <StatCard label="New (24h)"             value={stats.users_signed_up_24h}
                      sub={`${stats.users_signed_up_7d} in 7d`} />
            <StatCard label="Memories captured"     value={stats.total_memories.toLocaleString()}
                      sub={`+${stats.memories_24h} in 24h`} />
            <StatCard label="Searches"              value={stats.total_searches.toLocaleString()}
                      sub={`+${stats.searches_24h} in 24h`} />
            <StatCard label="On-chain anchors"      value={stats.blockchain_anchored.toLocaleString()}
                      sub="Memories anchored to blockchain" />
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700">Users ({users.length})</h2>
          <p className="text-[11px] text-slate-400">
            Counts only — page contents are never exposed to admins.
          </p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">User</th>
                <th className="px-3 py-2 font-medium text-right">Memories</th>
                <th className="px-3 py-2 font-medium">Last search</th>
                <th className="px-3 py-2 font-medium">Joined</th>
                <th className="px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-200">
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-900">
                      {u.username}
                      {u.is_admin && (
                        <span className="ml-2 text-[10px] uppercase tracking-wider
                          bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded-md">admin</span>
                      )}
                      {u.id === currentUserId && (
                        <span className="ml-2 text-[10px] text-slate-400">(you)</span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500">{u.email}</div>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-700">{u.memory_count}</td>
                  <td className="px-3 py-2 text-slate-500">{relativeTime(u.last_search_at)}</td>
                  <td className="px-3 py-2 text-slate-500">{relativeTime(u.created_at)}</td>
                  <td className="px-3 py-2 text-right">
                    {u.id !== currentUserId && (
                      <button
                        onClick={() => handleDeleteUser(u.id)}
                        disabled={deleting === u.id}
                        className="inline-flex items-center gap-1 px-2 py-1 text-[11px]
                          text-red-700 hover:bg-red-50 rounded-md disabled:opacity-50"
                      >
                        <ShieldXIcon className="w-3 h-3" />
                        {deleting === u.id ? '…' : 'Delete'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
