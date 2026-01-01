// frontend/src/index.js
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx' // O caminho agora é "./App.jsx"
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)