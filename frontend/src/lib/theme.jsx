import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const KEY = 'dfd.theme'
const ThemeContext = createContext({ theme: 'system', setTheme: () => {}, resolved: 'light' })

function readStored() {
  try {
    return localStorage.getItem(KEY) || 'system'
  } catch {
    return 'system'
  }
}

/**
 * Theme provider.
 *
 * Three states: an explicit light or dark choice stamps `data-theme` on the
 * root element and wins over the OS setting in both directions; "system"
 * removes the attribute and lets `prefers-color-scheme` decide.
 */
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readStored)
  const [resolved, setResolved] = useState('light')

  useEffect(() => {
    const root = document.documentElement
    const media = window.matchMedia('(prefers-color-scheme: dark)')

    function apply() {
      if (theme === 'system') {
        root.removeAttribute('data-theme')
        setResolved(media.matches ? 'dark' : 'light')
      } else {
        root.setAttribute('data-theme', theme)
        setResolved(theme)
      }
    }

    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])

  const setTheme = useCallback((next) => {
    setThemeState(next)
    try {
      if (next === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, next)
    } catch {
      /* storage blocked — the choice still applies for this session */
    }
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolved }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
