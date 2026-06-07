import { useEffect, useState, useCallback } from 'react'
import Navbar from '../components/Navbar'
import StatCard from '../components/StatCard'
import LogSearch from '../components/LogSearch'
import LevelPieChart from '../components/LevelPieChart'
import ServiceBarChart from '../components/ServiceBarChart'
import ErrorTrendChart from '../components/ErrorTrendChart'
import LogsPerDayChart from '../components/LogsPerDayChart'
import { useAuth } from '../context/AuthContext'
import api from '../api'

export default function Dashboard() {
  const { user } = useAuth()
  const [projects, setProjects]       = useState([])
  const [active, setActive]           = useState(null)
  const [summary, setSummary]         = useState(null)
  const [byLevel, setByLevel]         = useState([])
  const [byService, setByService]     = useState([])
  const [errorTrend, setErrorTrend]   = useState([])
  const [perDay, setPerDay]           = useState([])
  const [logs, setLogs]               = useState([])
  const [logsLoading, setLogsLoading] = useState(false)

  // Load projects list
  const loadProjects = useCallback(async () => {
    try {
      const { data } = await api.get(`/users/${user.user_id}/projects`)
      setProjects(data)
      // auto-select first project if nothing selected or active was deleted
      setActive((prev) => {
        if (prev && data.find((p) => p.project_id === prev.project_id)) return prev
        return data[0] ?? null
      })
    } catch {}
  }, [user.user_id])

  useEffect(() => { loadProjects() }, [loadProjects])

  // Load analytics whenever active project changes
  useEffect(() => {
    if (!active?.tenant_id) return
    const h = { headers: { 'X-Tenant-ID': active.tenant_id } }
    setSummary(null)
    setByLevel([])
    setByService([])
    setErrorTrend([])
    setPerDay([])
    setLogs([])

    api.get('/analytics/summary', h).then((r) => setSummary(r.data)).catch(() => {})
    api.get('/analytics/by-level', h).then((r) => setByLevel(r.data)).catch(() => {})
    api.get('/analytics/by-service', h).then((r) => setByService(r.data)).catch(() => {})
    api.get('/analytics/error-trend', h).then((r) => setErrorTrend(r.data)).catch(() => {})
    api.get('/analytics/logs-per-day', h).then((r) => setPerDay(r.data)).catch(() => {})

    // fetch initial logs
    const params = new URLSearchParams({ limit: '100' })
    setLogsLoading(true)
    api.get(`/logs/search?${params}`, h)
      .then((r) => setLogs(r.data))
      .catch(() => setLogs([]))
      .finally(() => setLogsLoading(false))
  }, [active?.tenant_id])

  const fetchLogs = useCallback(async ({ keyword = '', level = '', service = '' } = {}) => {
    if (!active?.tenant_id) return
    setLogsLoading(true)
    try {
      const params = new URLSearchParams({ limit: '100' })
      if (keyword) params.append('keyword', keyword)
      if (level)   params.append('level', level)
      if (service) params.append('service', service)

      const { data } = await api.get(`/logs/search?${params}`, {
        headers: { 'X-Tenant-ID': active.tenant_id },
      })
      setLogs(data)
    } catch {
      setLogs([])
    } finally {
      setLogsLoading(false)
    }
  }, [active?.tenant_id])

  if (!projects.length) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar
          projects={[]}
          activeProject={null}
          onSelectProject={() => {}}
          onProjectsChange={loadProjects}
        />
        <div className="flex-1 flex flex-col items-center justify-center gap-4 text-gray-400">
          <p className="text-lg">No projects yet</p>
          <p className="text-sm text-gray-600">Click <span className="text-indigo-400">+ New project</span> in the navbar to get started</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar
        projects={projects}
        activeProject={active}
        onSelectProject={setActive}
        onProjectsChange={loadProjects}
      />

      <main className="flex-1 px-6 py-6 max-w-7xl mx-auto w-full space-y-6">

        {/* Tenant ID badge */}
        {active && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Tenant ID:</span>
            <code className="text-xs text-indigo-400 bg-indigo-900/20 border border-indigo-800/40 px-2 py-0.5 rounded font-mono">
              {active.tenant_id}
            </code>
          </div>
        )}

        {/* Summary cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard label="Total Logs"  value={summary?.total_logs}   color="indigo" />
          <StatCard label="Errors"      value={summary?.error_logs}   color="red"    />
          <StatCard label="Warnings"    value={summary?.warning_logs} color="yellow" />
        </div>

        {/* Charts row 1 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <LevelPieChart   data={byLevel}   />
          <ServiceBarChart data={byService} />
        </div>

        {/* Charts row 2 — error trend + logs per day (full width, drillable) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ErrorTrendChart data={errorTrend} />
        </div>

        <div className="grid grid-cols-1 gap-4">
          <LogsPerDayChart data={perDay} tenantId={active?.tenant_id} />
        </div>

        {/* Log search + table */}
        <LogSearch
          onSearch={fetchLogs}
          logs={logs}
          loading={logsLoading}
        />

      </main>
    </div>
  )
}
