import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import "./styles/isa101.css";   // ISA-101 design tokens (POC blueprint)

// IMPORTANTE: importe seu ThemeProvider custom
import { ThemeProvider } from "./contexts/ThemeContext";
import axios from "axios";
import { APP_VERSION, GIT_HASH, FULL_VERSION, logVersionBanner } from "./version";

// Banner de versão — primeira coisa no console depois do reload.
// Se aqui aparece a versão ANTIGA mesmo após docker compose up, sabemos
// que o problema é cache do navegador / proxy reverso (não da imagem).
logVersionBanner();

// Disponibilizamos no window para inspeção rápida em produção:
//    window.MIS_VERSION  → "1.5.2"
//    window.MIS_BUILD    → "1.5.2 · ab12cd3 · 2026-04-28T14:08:12Z"
declare global {
  interface Window {
    MIS_VERSION?: string;
    MIS_BUILD?: string;
    MIS_GIT?: string;
  }
}
if (typeof window !== "undefined") {
  window.MIS_VERSION = APP_VERSION;
  window.MIS_GIT = GIT_HASH;
  window.MIS_BUILD = FULL_VERSION;
}

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
