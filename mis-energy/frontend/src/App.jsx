import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
// import { Sidebar } from '@/components/Sidebar'
import { Sidebar } from '@/components/Sidebar.jsx';
import { Header } from '@/components/Header'
import { Dashboard } from '@/components/Dashboard'
import { Gateways } from '@/components/Gateways'
import { Equipments } from '@/components/Equipments'
import { Settings } from '@/components/Settings'
import { EnergyDashboard } from '@/pages/EnergyDashboard'
import { Toaster } from '@/components/ui/toaster'
import IntroVideo from '@/components/IntroVideo'
import './App.css'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showIntro, setShowIntro] = useState(true)

  // Show intro video on first load
  if (showIntro) {
    return <IntroVideo onComplete={() => setShowIntro(false)} />
  }

  return (
    <>
      <Router basename="/mis-energy">
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-900 dark:to-slate-800">
          <div className="flex">
            {/* Sidebar */}
            <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />

            {/* Main Content */}
            <div className="flex-1 flex flex-col min-h-screen">
              {/* Header */}
              <Header sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

              {/* Page Content */}
              <main className="flex-1 p-6">
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/analytics" element={<EnergyDashboard />} />
                  <Route path="/gateways" element={<Gateways />} />
                  <Route path="/equipments" element={<Equipments />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </main>
            </div>
          </div>
        </div>
      </Router>
      <Toaster />
    </>
  )
}

export default App

