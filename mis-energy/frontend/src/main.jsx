import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' // Verifique se você tem um arquivo index.css na mesma pasta
import axios from 'axios'

// Global Auth / SSO Axios Config
axios.defaults.withCredentials = true;

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const currentPath = window.location.pathname;
      window.location.href = window.location.origin + '/mis-core/login?next=' + encodeURIComponent(currentPath);
    }
    return Promise.reject(error);
  }
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)