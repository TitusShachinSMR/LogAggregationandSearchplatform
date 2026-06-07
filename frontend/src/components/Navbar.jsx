import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../api'

export default function Navbar({ projects, activeProject, onSelectProject, onProjectsChange }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')

  function handleLogout() {
    logout()
    navigate('/login')
  }

  async function handleAddProject(e) {
    e.preventDefault()
    setAdding(true)
    setAddError('')
    try {
      await api.post('/projects', { name: newName, user_id: user.user_id })
      setNewName('')
      setShowAdd(false)
      onProjectsChange()
    } catch (err) {
      setAddError(err.response?.data?.detail || 'Failed to create project')
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(e, project) {
    e.stopPropagation()
    if (!confirm(`Delete "${project.project_name}" and all its logs?`)) return
    try {
      await api.delete(`/projects/${project.project_id}?user_id=${user.user_id}`)
      onProjectsChange()
    } catch {
      alert('Failed to delete project')
    }
  }

  return (
    <>
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-0 flex items-stretch justify-between">

        {/* Left: logo + project tabs */}
        <div className="flex items-stretch gap-1">
          <div className="flex items-center gap-2 pr-5 mr-2 border-r border-gray-800">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            <span className="font-bold text-white text-sm">LogPlatform</span>
          </div>

          {projects.map((p) => (
            <button
              key={p.project_id}
              onClick={() => onSelectProject(p)}
              className={`group relative flex items-center gap-2 px-4 text-sm border-b-2 transition-colors ${
                activeProject?.project_id === p.project_id
                  ? 'border-indigo-500 text-white'
                  : 'border-transparent text-gray-400 hover:text-white'
              }`}
            >
              <span>{p.project_name}</span>
              {/* tenant badge on hover */}
              <span className="hidden group-hover:block absolute top-full left-0 mt-1 z-10 bg-gray-800 border border-gray-700 text-gray-300 text-xs px-2 py-1 rounded whitespace-nowrap font-mono">
                {p.tenant_id}
              </span>
              {/* delete X */}
              <span
                onClick={(e) => handleDelete(e, p)}
                className="ml-1 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition text-xs leading-none"
                title="Delete project"
              >
                ✕
              </span>
            </button>
          ))}

          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1 px-4 text-sm text-gray-500 hover:text-indigo-400 border-b-2 border-transparent transition"
          >
            + New project
          </button>
        </div>

        {/* Right: username + logout */}
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{user?.username}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-3 py-1.5 my-3 rounded-lg transition"
          >
            Logout
          </button>
        </div>
      </nav>

      {/* Add project modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-sm shadow-2xl">
            <h2 className="text-lg font-semibold text-white mb-4">New project</h2>

            {addError && (
              <div className="mb-3 p-3 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">
                {addError}
              </div>
            )}

            <form onSubmit={handleAddProject} className="space-y-4">
              <input
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="my-service"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setShowAdd(false); setAddError('') }}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 py-2 rounded-lg text-sm transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adding}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition"
                >
                  {adding ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
