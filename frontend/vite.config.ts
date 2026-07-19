import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// SurfaceOS WebUI serves the repo `assets/` folder statically at `/`, so the
// production build lands there with relative asset URLs. During `npm run dev`
// the board API is proxied from the ADB tunnel on port 17000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../assets"),
    assetsDir: "static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/state": "http://127.0.0.1:17000",
      "/stream": "http://127.0.0.1:17000",
      "/confirm": "http://127.0.0.1:17000",
      "/calibrate": "http://127.0.0.1:17000",
      "/ingest": "http://127.0.0.1:17000",
      "/api": "http://127.0.0.1:17000",
    },
  },
});
