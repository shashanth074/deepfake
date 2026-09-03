import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, setSession } from '../lib/api'
import { useAuth } from '../lib/useAuth'
import { Notice } from '../components/ui'
import { ArrowRight, ShieldCheck, Spinner } from '../components/ui/Icons'

export default function Login() {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const { setUser } = useAuth()
  const navigate = useNavigate()

  const isRegister = mode === 'register'
  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const payload = isRegister
        ? { email: form.email, password: form.password, full_name: form.full_name || null }
        : { email: form.email, password: form.password }
      const result = isRegister ? await api.register(payload) : await api.login(payload)
      setSession(result.access_token, result.user)
      setUser(result.user)
      navigate('/analyse')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md animate-in py-6">
      <div className="mb-6 text-center">
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-xl text-white"
              style={{ background: 'var(--accent)' }}>
          <ShieldCheck size={22} />
        </span>
        <h1 className="mt-4 text-[1.625rem] font-bold tracking-tight text-ink-primary">
          {isRegister ? 'Create your account' : 'Welcome back'}
        </h1>
        <p className="mt-2 text-[0.875rem] text-ink-secondary">
          {isRegister
            ? 'An account keeps your scan history and raises your upload limit.'
            : 'Sign in to reach your scan history and reports.'}
        </p>
      </div>

      <div className="card card-pad">
        <form onSubmit={submit} className="space-y-4">
          {isRegister && (
            <div>
              <label className="label" htmlFor="full_name">
                Full name <span className="font-normal text-ink-muted">(optional)</span>
              </label>
              <input id="full_name" className="input" value={form.full_name}
                     onChange={update('full_name')} autoComplete="name" placeholder="Jane Doe" />
            </div>
          )}

          <div>
            <label className="label" htmlFor="email">Email address</label>
            <input id="email" type="email" required className="input" value={form.email}
                   onChange={update('email')} autoComplete="email" placeholder="you@example.com" />
          </div>

          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" required
                   minLength={isRegister ? 8 : undefined} className="input"
                   value={form.password} onChange={update('password')}
                   autoComplete={isRegister ? 'new-password' : 'current-password'}
                   placeholder={isRegister ? 'At least 8 characters' : '••••••••'} />
          </div>

          {error && <Notice tone="critical">{error}</Notice>}

          <button type="submit" className="btn-primary w-full !py-2.5" disabled={busy}>
            {busy ? <><Spinner size={16} /> Please wait…</>
                  : <>{isRegister ? 'Create account' : 'Sign in'} <ArrowRight size={16} /></>}
          </button>
        </form>

        <div className="mt-5 border-t pt-4 text-center text-[0.8125rem]"
             style={{ borderColor: 'var(--border-subtle)' }}>
          <p className="text-ink-secondary">
            {isRegister ? 'Already have an account?' : 'No account yet?'}{' '}
            <button className="link"
                    onClick={() => { setMode(isRegister ? 'login' : 'register'); setError(null) }}>
              {isRegister ? 'Sign in' : 'Create one'}
            </button>
          </p>
          <p className="mt-2">
            <Link to="/analyse" className="text-ink-muted hover:text-ink-primary">
              Continue as a guest →
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
