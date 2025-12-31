import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// IMPORTANTE: importe seu ThemeProvider custom
import { ThemeProvider } from "./contexts/ThemeContext";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="light" switchable={false}>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
