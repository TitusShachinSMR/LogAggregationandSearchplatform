export default function StatCard({ label, value, color }) {
  const colors = {
    indigo: 'border-indigo-500/40 bg-indigo-500/10 text-indigo-400',
    red:    'border-red-500/40 bg-red-500/10 text-red-400',
    yellow: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400',
    green:  'border-green-500/40 bg-green-500/10 text-green-400',
  }

  return (
    <div className={`rounded-xl border p-5 ${colors[color] ?? colors.indigo}`}>
      <p className="text-sm text-gray-400 mb-1">{label}</p>
      <p className="text-3xl font-bold text-white">{value ?? '—'}</p>
    </div>
  )
}
