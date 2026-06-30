import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const backendUrl = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
        secure: false
      }
    }
  },
  resolve: {
    alias: {
      "@subpilot/ui": path.resolve(__dirname, "../../packages/ui/src")
    }
  }
});
