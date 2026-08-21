import { jsxLocPlugin } from "@builder.io/vite-plugin-jsx-loc";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "path";
import { defineConfig } from "vite";
import { vitePluginManusRuntime } from "vite-plugin-manus-runtime";

const plugins = [react(), tailwindcss(), jsxLocPlugin(), vitePluginManusRuntime()];

// =============================================================================
// Versionamento determinístico — gravado no bundle via `define`
// =============================================================================
// Por que isso existe:
//   No deploy offline tínhamos um bug crítico em que a imagem buildada não era
//   a mesma que rodava no servidor OT (tag :v15.0 era reutilizada em cima de
//   build antigo). Para diagnosticar visualmente, expomos versão+hash+build no
//   bundle, e replicamos no backend/nginx via /version.json.
//
// Ordem de prioridade (build-time):
//   1. ENV var VITE_APP_VERSION   (CI / docker --build-arg)
//   2. ENV var MIS_VERSION         (idem; usado pelo compose)
//   3. package.json#version
// =============================================================================

function safeGitHash(): string {
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim();
  } catch {
    return "no-git";
  }
}

function pkgVersion(): string {
  try {
    const pkg = JSON.parse(
      readFileSync(path.resolve(import.meta.dirname, "package.json"), "utf-8"),
    );
    return pkg.version || "0.0.0";
  } catch {
    return "0.0.0";
  }
}

const APP_VERSION =
  process.env.VITE_APP_VERSION ||
  process.env.MIS_VERSION ||
  pkgVersion();

const GIT_HASH = process.env.VITE_GIT_HASH || safeGitHash();
const BUILD_TIME = process.env.VITE_BUILD_TIME || new Date().toISOString();

export default defineConfig({
  plugins,
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  envDir: path.resolve(import.meta.dirname, ".."),
  root: path.resolve(import.meta.dirname, "client"),
  // base relativo permite servir tanto em http://host:8080/mis-core/
  // quanto em https://hub/mis-core/ atrás de proxy reverso.
  base: "/mis-core/",
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
    __GIT_HASH__: JSON.stringify(GIT_HASH),
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
  },
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
    // Hash longo no nome de arquivo evita colisão entre versões antigas/novas
    // do mesmo bundle no cache do navegador / nginx.
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  server: {
    port: 3000,
    strictPort: false,
    host: true,
    allowedHosts: ["localhost", "127.0.0.1"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/flask-api": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
    },
    fs: {
      strict: true,
      deny: ["**/.*"],
    },
  },
});
