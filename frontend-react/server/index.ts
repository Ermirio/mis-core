import express from "express";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const server = createServer(app);

  // Serve static files from dist/public in production
  const staticPath =
    process.env.NODE_ENV === "production"
      ? path.resolve(__dirname, "public")
      : path.resolve(__dirname, "..", "dist", "public");

  app.use(express.static(staticPath));

  // Serve runtime configuration
  app.get("/env-config.js", (_req, res) => {
    const env = {
      VITE_DJANGO_API_URL: process.env.VITE_DJANGO_API_URL || "http://localhost:8001/api",
      VITE_FLASK_API_URL: process.env.VITE_FLASK_API_URL || "http://localhost:5000/api",
    };
    res.set("Content-Type", "application/javascript");
    res.send(`window.env = ${JSON.stringify(env)};`);
  });

  // Handle client-side routing - serve index.html for all routes
  app.get("*", (_req, res) => {
    res.sendFile(path.join(staticPath, "index.html"));
  });

  const port = process.env.PORT || 3000;

  server.listen(port, () => {
    console.log(`Server running on http://localhost:${port}/`);
  });
}

startServer().catch(console.error);
