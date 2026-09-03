import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { clearSession } from '../lib/api'
import { useAuth } from '../lib/useAuth'
import { useTheme } from '../lib/theme'
import { Moon, ShieldCheck, Sun } from './ui/Icons'

function NavItem({ to, children }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `relative rounded-lg px-3 py-1.5 text-[0.8125rem] font-medium transition-colors ${
          isActive ? 'text-ink-primary' : 'text-ink-muted hover:text-ink-primary'
        }`
      }
    >
      {({ isActive }) => (
        <>
          {children}
          {isActive && (
            <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full"
                  style={{ background: 'var(--accent)' }} />
          )}
        </>
      )}
    </NavLink>
  )
}

function ThemeToggle() {
  const { resolved, setTheme } = useTheme()
  const next = resolved === 'dark' ? 'light' : 'dark'
  return (
    <button
      onClick={() => setTheme(next)}
      className="btn-ghost h-8 w-8 !px-0"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
    >
      {resolved === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  )
}

export default function Layout() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()

  function signOut() {
    clearSession()
    setUser(null)
    navigate('/')
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header
        className="sticky top-0 z-30 border-b backdrop-blur"
        style={{ background: 'color-mix(in srgb, var(--surface-1) 88%, transparent)',
                 borderColor: 'var(--border-subtle)' }}
      >
        <div className="mx-auto flex h-14 max-w-content items-center justify-between px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg text-white"
                  style={{ background: 'var(--accent)' }}>
              <ShieldCheck size={18} />
            </span>
            <span className="leading-none">
              <span className="block text-[0.9375rem] font-bold tracking-tight text-ink-primary">
                Veritas
              </span>
              <span className="mt-0.5 block text-[0.6875rem] font-medium text-ink-muted">
                Deepfake Forensics
              </span>
            </span>
          </Link>

          <nav className="flex items-center gap-1">
            <div className="mr-2 hidden items-center gap-1 sm:flex">
              <NavItem to="/analyse">Analyse</NavItem>
              {user && <NavItem to="/history">History</NavItem>}
              <NavItem to="/how-it-works">How it works</NavItem>
            </div>
            <ThemeToggle />
            {user ? (
              <div className="ml-1 flex items-center gap-2">
                <span className="hidden max-w-[10rem] truncate text-[0.8125rem] text-ink-muted md:block">
                  {user.email}
                </span>
                <button onClick={signOut} className="btn-secondary !py-1.5 text-[0.8125rem]">
                  Sign out
                </button>
              </div>
            ) : (
              <Link to="/login" className="btn-secondary ml-1 !py-1.5 text-[0.8125rem]">
                Sign in
              </Link>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-content flex-1 px-5 py-9">
        <Outlet />
      </main>

      <footer className="border-t" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="mx-auto max-w-content px-5 py-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:justify-between">
            <div className="max-w-xl">
              <p className="text-[0.8125rem] font-semibold text-ink-primary">
                Automated technical assessment — not a certified forensic opinion.
              </p>
              <p className="mt-2 text-[0.75rem] leading-relaxed text-ink-muted">
                This platform produces an evidence report you may attach to a complaint. It does
                not file complaints with any authority, and detection models produce both false
                positives and false negatives. For legal proceedings, verification by a certified
                forensic expert is recommended.
              </p>
            </div>
            <div className="text-[0.75rem] leading-relaxed text-ink-muted sm:text-right">
              <p className="font-medium text-ink-secondary">Acceptable use</p>
              <p className="mt-2 max-w-xs">
                Analyse only media you own or are authorised to analyse. Generating deepfakes
                with this tool is prohibited.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
