import { useState, useEffect } from 'react'
// Mantenha seu import do Router
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import { ThemeProvider } from '@/components/theme-provider'
// import Navbar from '@/components/Navbar' // Removido em favor da Sidebar
import Sidebar from '@/components/Sidebar'
import Header from '@/components/Header'
import IntroVideo from '@/components/IntroVideo'
import Dashboard from '@/pages/Dashboard'
import LineManagement from '@/pages/LineManagement'
import TargetManagement from '@/pages/TargetManagement'
import ModelManagement from '@/pages/ModelManagement'
import DataCollection from '@/pages/DataCollection'
import PredictionView from '@/pages/PredictionView'
import DetailedAnalysis from '@/pages/DetailedAnalysis'
import OPCConfiguration from '@/pages/OPCConfiguration'
import './App.css'

// Defina o basename aqui (corresponde ao 'base' do Vite e 'location' do Nginx)
const basename = "/mis-ai";

function App() {
  const [showIntro, setShowIntro] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const [selectedLine, setSelectedLine] = useState('')
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [selectedModel, setSelectedModel] = useState(null)

  // Estado para forçar atualização quando objetos são criados/editados/excluídos
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleDataChange = () => {
    setRefreshTrigger(prev => prev + 1)
  }

  if (showIntro) {
    return <IntroVideo onComplete={() => setShowIntro(false)} />
  }

  return (
    <ThemeProvider defaultTheme="system" storageKey="prediction-app-theme">
      {/* Adicione a prop 'basename' ao Router */}
      <Router basename={basename}>
        <div className="flex min-h-screen bg-background">
          <Sidebar
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          />

          <div
            className="flex-1 flex flex-col transition-all duration-300 ease-in-out"
            style={{ marginLeft: sidebarCollapsed ? '80px' : '280px' }}
          >
            <Header
              selectedLine={selectedLine}
              setSelectedLine={setSelectedLine}
              selectedTarget={selectedTarget}
              setSelectedTarget={setSelectedTarget}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              refreshTrigger={refreshTrigger}
            />

            <main className="flex-1 p-6 overflow-x-hidden">
              <Routes>
                {/* As rotas internas continuam as mesmas, ex: path="/dashboard" */}
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route
                  path="/dashboard"
                  element={
                    <Dashboard
                      selectedLine={selectedLine}
                      selectedTarget={selectedTarget}
                      selectedModel={selectedModel}
                    />
                  }
                />
                <Route
                  path="/lines"
                  element={
                    <LineManagement
                      onDataChange={handleDataChange}
                    />
                  }
                />
                <Route
                  path="/targets"
                  element={
                    <TargetManagement
                      selectedLine={selectedLine}
                      setSelectedTarget={setSelectedTarget}
                      onDataChange={handleDataChange}
                    />
                  }
                />
                <Route
                  path="/models"
                  element={
                    <ModelManagement
                      selectedTarget={selectedTarget}
                      setSelectedModel={setSelectedModel}
                      onDataChange={handleDataChange}
                    />
                  }
                />
                <Route
                  path="/data"
                  element={
                    <DataCollection
                      selectedLine={selectedLine}
                      selectedTarget={selectedTarget}
                    />
                  }
                />
                <Route
                  path="/prediction"
                  element={
                    <PredictionView
                      selectedLine={selectedLine}
                      selectedTarget={selectedTarget}
                      selectedModel={selectedModel}
                    />
                  }
                />
                <Route
                  path="/analysis"
                  element={
                    <DetailedAnalysis
                      selectedLine={selectedLine}
                    />
                  }
                />
                <Route
                  path="/opc"
                  element={
                    <OPCConfiguration
                      selectedLine={selectedLine}
                    />
                  }
                />
              </Routes>
            </main>

            <Toaster />
          </div>
        </div>
      </Router>
    </ThemeProvider>
  )
}

export default App