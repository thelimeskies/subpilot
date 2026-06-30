import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const BACKEND = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@subpilot/ui": path.resolve(__dirname, "../../packages/ui/src")
    }
  },
  server: {
    port: 5175,
    proxy: {
      "/api": {
        target: BACKEND,
        changeOrigin: true,
        secure: false
      }
    }
  }
});
