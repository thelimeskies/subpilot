import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@subpilot/ui": path.resolve(__dirname, "../../packages/ui/src")
    }
  },
  // Pre-bundle these eagerly so dynamically-imported pages (Redoc) don't trigger
  // a 504 "Outdated Optimize Dep" the first time you visit /developers/api.
  optimizeDeps: {
    include: ["redoc", "styled-components", "yaml"]
  }
});
