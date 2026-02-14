/**
 * index.js - Ponto de entrada da aplicação React
 * 
 * Este arquivo inicializa a aplicação React e renderiza o componente App
 * no elemento root do DOM.
 * 
 * @author Manus AI
 * @version 3.0.0
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/index.css';

// Importações do Bootstrap
import 'bootstrap/dist/css/bootstrap.min.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

