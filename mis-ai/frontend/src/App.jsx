import { useState, useEffect } from 'react'
// Mantenha seu import do Router
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import { ThemeProvider } from '@/components/theme-provider'
import Navbar from '@/components/Navbar'
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
const basename = "/prediction-app";

function App() {
  const [selectedLine, setSelectedLine] = useState('')
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [selectedModel, setSelectedModel] = useState(null)

  // Estado para forçar atualização da Navbar quando objetos são criados/editados/excluídos
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleDataChange = () => {
    setRefreshTrigger(prev => prev + 1)
  }

  return (
    <ThemeProvider defaultTheme="system" storageKey="prediction-app-theme">
      {/* Adicione a prop 'basename' ao Router */}
      <Router basename={basename}>
        <div className="min-h-screen bg-background">
          <Navbar
            selectedLine={selectedLine}
            setSelectedLine={setSelectedLine}
            selectedTarget={selectedTarget}
            setSelectedTarget={setSelectedTarget}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            refreshTrigger={refreshTrigger}
          />

          <main className="container mx-auto px-4 py-6">
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
      </Router>
    </ThemeProvider>
  )
}

export default App