import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import Layout from './components/Layout'
import LoadingRoute from './components/ui/LoadingRoute'
import { AuthProvider, useAuth } from './lib/useAuth'
import { ThemeProvider } from './lib/theme'
import Landing from './pages/Landing'
import UploadPage from './pages/Upload'
import Result from './pages/Result'
import Report from './pages/Report'
import History from './pages/History'
import HowItWorks from './pages/HowItWorks'
import Login from './pages/Login'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingRoute />
  return user ? children : <Navigate to="/login" replace />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Landing />} />
            <Route path="analyse" element={<UploadPage />} />
            <Route path="jobs/:jobId" element={<Result />} />
            <Route path="jobs/:jobId/report" element={<Report />} />
            <Route path="how-it-works" element={<HowItWorks />} />
            <Route path="login" element={<Login />} />
            <Route
              path="history"
              element={
                <RequireAuth>
                  <History />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
