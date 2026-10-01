import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "/birthday/",
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
  server: {
    proxy: {
      "/birthday/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
