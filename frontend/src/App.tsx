import { Routes, Route, useLocation } from 'react-router-dom'
import HomePage from './pages/HomePage'
import PlanPage from './pages/PlanPage'
import ItineraryPage from './pages/ItineraryPage'
import ComparePage from './pages/ComparePage'
import ChatPage from './pages/ChatPage'
import SearchResultPage from './pages/SearchResultPage'
import LoginPage from './pages/LoginPage'
import HistoryPage from './pages/HistoryPage'
import HistoryDetailPage from './pages/HistoryDetailPage'
import DesktopNav from './components/DesktopNav'
import MobileNav from './components/MobileNav'
import RequireAuth from './components/RequireAuth'
import { AuthProvider } from './context/AuthContext'

export default function App() {
  const location = useLocation()
  const isLoginPage = location.pathname === '/login'

  return (
    <AuthProvider>
      <div className="min-h-screen bg-gray-50">
        {!isLoginPage && <DesktopNav />}
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<RequireAuth><HomePage /></RequireAuth>} />
          <Route path="/plan" element={<RequireAuth><PlanPage /></RequireAuth>} />
          <Route path="/itinerary/:id" element={<RequireAuth><ItineraryPage /></RequireAuth>} />
          <Route path="/compare" element={<RequireAuth><ComparePage /></RequireAuth>} />
          <Route path="/chat" element={<RequireAuth><ChatPage /></RequireAuth>} />
          <Route path="/search" element={<RequireAuth><SearchResultPage /></RequireAuth>} />
          <Route path="/history" element={<RequireAuth><HistoryPage /></RequireAuth>} />
          <Route path="/history/:id" element={<RequireAuth><HistoryDetailPage /></RequireAuth>} />
        </Routes>
        {!isLoginPage && <MobileNav />}
      </div>
    </AuthProvider>
  )
}
