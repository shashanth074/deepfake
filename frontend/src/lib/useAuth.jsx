import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, getStoredUser, getToken, clearSession } from './api'

const AuthContext = createContext({ user: null, setUser: () => {}, loading: true })

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser)
  const [loading, setLoading] = useState(Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    // Confirm the stored token is still valid rather than trusting localStorage.
    api
      .me()
      .then(setUser)
      .catch(() => {
        clearSession()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const value = useMemo(() => ({ user, setUser, loading }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
