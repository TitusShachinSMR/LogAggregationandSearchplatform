import { useState } from 'react'

const LEVEL_COLORS = {
  ERROR: 'text-red-400 bg-red-900/30',
  WARN:  'text-yellow-400 bg-yellow-900/30',
  INFO:  'text-green-400 bg-green-900/30',
}

export default function LogSearch({ onSearch, logs, loading }) {
  const [filters, setFilters] = useState({ keyword: '', level: '', service: '' })

  function handleSubmit(e) {
    e.preventDefault()
    onSearch(filters)
  }

  function handleReset() {
    const cleared = { keyword: '', level: '', service: '' }
    setFilters(cleared)
    onSearch(cleared)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-base font-semibold text-white mb-4">Search Logs</h2>

      <form onSubmit={handleSubmit} className="flex flex-wrap gap-3 mb-5">
        <input
          className="flex-1 min-w-[180px] bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Search message..."
          value={filters.keyword}
          onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
        />
        <select
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={filters.level}
          onChange={(e) => setFilters({ ...filters, level: e.target.value })}
        >
          <option value="">All levels</option>
          <option value="INFO">INFO</option>
          <option value="WARN">WARN</option>
          <option value="ERROR">ERROR</option>
        </select>
        <input
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Service name"
          value={filters.service}
          onChange={(e) => setFilters({ ...filters, service: e.target.value })}
        />
        <button
          type="submit"
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
        >
          Search
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm px-4 py-2 rounded-lg transition"
        >
          Reset
        </button>
      </form>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="pb-2 pr-4">Timestamp</th>
              <th className="pb-2 pr-4">Level</th>
              <th className="pb-2 pr-4">Service</th>
              <th className="pb-2">Message</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="py-8 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && logs.length === 0 && (
              <tr>
                <td colSpan={4} className="py-8 text-center text-gray-500">
                  No logs found
                </td>
              </tr>
            )}
            {!loading && logs.map((log, i) => (
              <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
                <td className="py-2.5 pr-4 text-gray-400 whitespace-nowrap font-mono text-xs">
                  {new Date(log.timestamp).toLocaleString()}
                </td>
                <td className="py-2.5 pr-4">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${LEVEL_COLORS[log.level] ?? 'text-gray-400'}`}>
                    {log.level}
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-gray-300 whitespace-nowrap">{log.service}</td>
                <td className="py-2.5 text-gray-300">{log.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
