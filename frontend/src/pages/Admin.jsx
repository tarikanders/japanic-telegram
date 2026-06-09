import { useState, useEffect, useRef } from 'react'
import { fetchAdminStatus, triggerSync, triggerMigrate, triggerRelink, triggerFreshRescrape, triggerResumeRescrape, triggerRenormalize, login } from '../api'
import api from '../api'
import toast from 'react-hot-toast'
import './Admin.css'

export default function Admin() {
  const [token, setToken] = useState(() => localStorage.getItem('admin_token'))
  const [password, setPassword] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  const [status, setStatus] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [relinking, setRelinking] = useState(false)
  const [migrating, setMigrating] = useState(false)
  const [renormalizing, setRenormalizing] = useState(false)
  const [logs, setLogs] = useState([])
  const wsRef = useRef(null)
  const logsEndRef = useRef(null)

  // Telegram setup state
  const [sessionExists, setSessionExists] = useState(null)
  const [tgPhone, setTgPhone] = useState('')
  const [tgCode, setTgCode] = useState('')
  const [tgHash, setTgHash] = useState('')
  const [tgStep, setTgStep] = useState(1) // 1=phone, 2=code
  const [tgLoading, setTgLoading] = useState(false)

  useEffect(() => {
    if (!token) return
    fetchAdminStatus()
      .then(setStatus)
      .catch(() => { localStorage.removeItem('admin_token'); setToken(null) })
    api.get('/telegram-setup/status').then(r => setSessionExists(r.data.session_exists)).catch(() => {})
  }, [token])

  const handleTgRequest = async (e) => {
    e.preventDefault()
    setTgLoading(true)
    try {
      const r = await api.post('/telegram-setup/request', { phone: tgPhone })
      setTgHash(r.data.phone_code_hash)
      setTgStep(2)
      toast.success('Code sent to your Telegram app!')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to send code')
    } finally {
      setTgLoading(false)
    }
  }

  const handleTgVerify = async (e) => {
    e.preventDefault()
    setTgLoading(true)
    try {
      const r = await api.post('/telegram-setup/verify', { code: tgCode, phone_code_hash: tgHash })
      toast.success(r.data.message)
      setSessionExists(true)
      setTgStep(1); setTgPhone(''); setTgCode(''); setTgHash('')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verification failed')
    } finally {
      setTgLoading(false)
    }
  }

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginLoading(true)
    try {
      await login(password)
      setToken(localStorage.getItem('admin_token'))
      toast.success('Logged in')
    } catch {
      toast.error('Invalid password')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleSync = async () => {
    if (syncing) return
    setSyncing(true)
    setLogs([])

    try {
      // Get a one-time ticket (JWT stays out of URL / server logs)
      const { data: { ticket } } = await api.post('/admin/logs/ticket')
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/admin/logs?ticket=${ticket}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (e) => setLogs(prev => [...prev, e.data])
      ws.onerror = () => setLogs(prev => [...prev, '[WebSocket error]'])
      ws.onclose = () => setSyncing(false)

      await triggerSync()
    } catch (e) {
      toast.error('Sync failed: ' + (e.response?.data?.detail || e.message))
      setSyncing(false)
    }
  }

  const handleMigrate = async () => {
    setMigrating(true)
    setLogs([])
    try {
      const result = await triggerMigrate()
      setLogs(result.applied || [])
      toast.success('Migrations applied')
    } catch (e) {
      toast.error('Migration failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setMigrating(false)
    }
  }

  const handleFreshRescrape = async () => {
    const confirmed = window.confirm(
      '⚠️ ATTENTION : Cette opération efface TOUTES les données (auctions + listings) et relance un scrape complet depuis le début.\n\nUn backup automatique sera créé.\n\nSi un re-scrape est déjà en cours (partiel), utilise "Resume Re-scrape" à la place.\n\nConfirmer ?'
    )
    if (!confirmed) return
    if (syncing || relinking) return
    setSyncing(true)
    setLogs([])
    try {
      const { data: { ticket } } = await api.post('/admin/logs/ticket')
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/admin/logs?ticket=${ticket}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (e) => setLogs(prev => [...prev, e.data])
      ws.onerror = () => setLogs(prev => [...prev, '[WebSocket error]'])
      ws.onclose = () => setSyncing(false)
      await triggerFreshRescrape(true) // force=true confirmé par l'utilisateur
    } catch (e) {
      const detail = e.response?.data?.detail || e.message
      if (e.response?.status === 409) {
        toast.error('Re-scrape interrompu détecté. Utilise "Resume Re-scrape" pour reprendre sans perte.')
      } else {
        toast.error('Fresh re-scrape failed: ' + detail)
      }
      setSyncing(false)
    }
  }

  const handleResumeRescrape = async () => {
    if (!window.confirm(
      'Reprendre le re-scrape depuis le dernier checkpoint ?\n\nLes données existantes sont conservées — le scrape continue là où il s\'est arrêté.'
    )) return
    if (syncing || relinking) return
    setSyncing(true)
    setLogs([])
    try {
      const { data: { ticket } } = await api.post('/admin/logs/ticket')
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/admin/logs?ticket=${ticket}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (e) => setLogs(prev => [...prev, e.data])
      ws.onerror = () => setLogs(prev => [...prev, '[WebSocket error]'])
      ws.onclose = () => setSyncing(false)
      await triggerResumeRescrape()
    } catch (e) {
      toast.error('Resume failed: ' + (e.response?.data?.detail || e.message))
      setSyncing(false)
    }
  }

  const handleRenormalize = async () => {
    if (renormalizing || syncing || relinking) return
    setRenormalizing(true)
    setLogs([])
    try {
      const { data: { ticket } } = await api.post('/admin/logs/ticket')
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/admin/logs?ticket=${ticket}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (e) => setLogs(prev => [...prev, e.data])
      ws.onerror = () => setLogs(prev => [...prev, '[WebSocket error]'])
      ws.onclose = () => setRenormalizing(false)
      await triggerRenormalize()
    } catch (e) {
      toast.error('Renormalize failed: ' + (e.response?.data?.detail || e.message))
      setRenormalizing(false)
    }
  }

  const handleRelink = async () => {
    if (relinking || syncing) return
    setRelinking(true)
    setLogs([])
    try {
      const { data: { ticket } } = await api.post('/admin/logs/ticket')
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/admin/logs?ticket=${ticket}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (e) => setLogs(prev => [...prev, e.data])
      ws.onerror = () => setLogs(prev => [...prev, '[WebSocket error]'])
      ws.onclose = () => setRelinking(false)
      await triggerRelink()
    } catch (e) {
      toast.error('Re-link failed: ' + (e.response?.data?.detail || e.message))
      setRelinking(false)
    }
  }

  if (!token) {
    return (
      <div className="admin-login">
        <div className="login-card">
          <h1 className="login-title">Admin Login</h1>
          <p className="login-sub">Japan Auction Intelligence</p>
          <form onSubmit={handleLogin} className="login-form">
            <input
              type="password"
              className="login-input"
              placeholder="Admin password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoFocus
            />
            <button type="submit" className="login-btn" disabled={loginLoading}>
              {loginLoading ? 'Logging in…' : 'Login'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1 className="admin-title">Admin Panel</h1>
        <button className="btn-logout" onClick={() => { localStorage.removeItem('admin_token'); setToken(null) }}>
          Logout
        </button>
      </div>

      <div className="admin-grid">
        <div className="admin-card">
          <h2 className="admin-section-title">Database</h2>
          {status ? (
            <div className="status-rows">
              <div className="status-row">
                <span>Total Auctions</span>
                <strong>{status.total_auctions?.toLocaleString()}</strong>
              </div>
              <div className="status-row">
                <span>Total Listings</span>
                <strong>{status.total_listings?.toLocaleString()}</strong>
              </div>
              <div className="status-row">
                <span>Records Synced</span>
                <strong>{status.records_synced_total?.toLocaleString()}</strong>
              </div>
            </div>
          ) : (
            <div className="skeleton" style={{ height: 80 }} />
          )}
        </div>

        <div className="admin-card">
          <h2 className="admin-section-title">Telegram Sync</h2>
          {status ? (
            <div className="status-rows">
              <div className="status-row">
                <span>Last Sync</span>
                <strong>{status.last_sync_at ? new Date(status.last_sync_at).toLocaleString() : 'Never'}</strong>
              </div>
              <div className="status-row">
                <span>Status</span>
                <strong className={`sync-status sync-status--${status.sync_status}`}>
                  {status.sync_status}
                </strong>
              </div>
              <div className="status-row">
                <span>Last Message ID</span>
                <strong>{status.last_message_id?.toLocaleString() || 0}</strong>
              </div>
              {status.error_message && (
                <div className="error-msg">{status.error_message}</div>
              )}
            </div>
          ) : (
            <div className="skeleton" style={{ height: 80 }} />
          )}
          <button
            className={`sync-btn ${syncing ? 'syncing' : ''}`}
            onClick={handleSync}
            disabled={syncing || relinking || migrating}
          >
            {syncing ? '⟳ Syncing…' : '▶ Force Sync Now'}
          </button>
          <button
            className="sync-btn rescrape-btn"
            onClick={handleFreshRescrape}
            disabled={syncing || relinking || migrating}
            title="Efface toutes les données et rescrape depuis 0 (backup auto)"
          >
            ↺ Fresh Re-scrape
          </button>
          {status?.last_message_id > 0 && (
            <button
              className="sync-btn resume-btn"
              onClick={handleResumeRescrape}
              disabled={syncing || relinking || migrating}
              title={`Reprendre le re-scrape depuis msg_id=${status.last_message_id.toLocaleString()}`}
            >
              ▶▶ Resume Re-scrape
            </button>
          )}
        </div>
      </div>

      {/* Telegram Setup Card */}
      <div className="admin-card tg-setup-card">
        <div className="tg-setup-header">
          <h2 className="admin-section-title">Telegram Session</h2>
          {sessionExists !== null && (
            <span className={`session-badge ${sessionExists ? 'session-ok' : 'session-missing'}`}>
              {sessionExists ? '● Connected' : '○ Not configured'}
            </span>
          )}
        </div>

        {!sessionExists && (
          <div className="tg-setup-form">
            {tgStep === 1 ? (
              <form onSubmit={handleTgRequest} className="tg-form-row">
                <input
                  className="tg-input"
                  type="tel"
                  placeholder="+33612345678"
                  value={tgPhone}
                  onChange={e => setTgPhone(e.target.value)}
                  required
                />
                <button className="tg-btn" type="submit" disabled={tgLoading || !tgPhone}>
                  {tgLoading ? 'Sending…' : 'Send Code'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleTgVerify} className="tg-form-row">
                <span className="tg-phone-label">Code sent to {tgPhone}</span>
                <input
                  className="tg-input"
                  type="text"
                  placeholder="12345"
                  maxLength={6}
                  value={tgCode}
                  onChange={e => setTgCode(e.target.value)}
                  autoFocus
                  required
                />
                <button className="tg-btn" type="submit" disabled={tgLoading || !tgCode}>
                  {tgLoading ? 'Verifying…' : 'Verify'}
                </button>
                <button type="button" className="tg-btn tg-btn-secondary" onClick={() => setTgStep(1)}>
                  ← Back
                </button>
              </form>
            )}
          </div>
        )}

        {sessionExists && (
          <p className="tg-ok-msg">Session active — Sync is ready to run.</p>
        )}
      </div>

      <div className="admin-card db-tools-card">
        <h2 className="admin-section-title">DB Tools</h2>
        <p className="db-tools-desc">
          Run after a code update or to improve match quality. Migrate adds missing columns,
          Re-link recomputes all auction↔listing associations with the optimal algorithm.
        </p>
        <div className="db-tools-row">
          <button
            className={`sync-btn ${migrating ? 'syncing' : ''}`}
            onClick={handleMigrate}
            disabled={migrating || syncing || relinking}
          >
            {migrating ? '⟳ Migrating…' : '▶ Apply Migrations'}
          </button>
          <button
            className={`sync-btn relink-btn ${relinking ? 'syncing' : ''}`}
            onClick={handleRelink}
            disabled={relinking || syncing || migrating || renormalizing}
          >
            {relinking ? '⟳ Re-linking…' : '⟳ Re-link DB'}
          </button>
          <button
            className={`sync-btn ${renormalizing ? 'syncing' : ''}`}
            onClick={handleRenormalize}
            disabled={renormalizing || relinking || syncing || migrating}
            title="Recalcule model_normalized + variant sur tous les listings et auctions existants"
          >
            {renormalizing ? '⟳ Renormalizing…' : '⟳ Renormaliser'}
          </button>
        </div>
      </div>

      <div className="logs-card">
        <div className="logs-header">
          <h2 className="admin-section-title">Sync Logs</h2>
          {logs.length > 0 && (
            <button className="btn-clear-logs" onClick={() => setLogs([])}>Clear</button>
          )}
        </div>
        <div className="logs-body">
          {logs.length === 0 ? (
            <span className="logs-empty">No logs yet. Start a sync to see output.</span>
          ) : (
            logs.map((l, i) => <div key={i} className="log-line">{l}</div>)
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  )
}
