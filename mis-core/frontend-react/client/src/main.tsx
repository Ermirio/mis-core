import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// IMPORTANTE: importe seu ThemeProvider custom
import { ThemeProvider } from "./contexts/ThemeContext";
import axios from "axios";

// === Configuração Global do SSO / JWT / Axios ===
axios.defaults.withCredentials = true;

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      if (window.location.pathname !== '/login') {
        localStorage.removeItem('user'); // Exemplo
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="light" switchable={false}>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
