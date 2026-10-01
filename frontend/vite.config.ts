import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "trailing-slash-redirect",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url === "/birthday") {
            res.writeHead(301, { Location: "/birthday/" });
            res.end();
            return;
          }
          next();
        });
      },
    },
  ],
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
        headers: {
          "Remote-User": "kiskaadee", // mock Authelia ForwardAuth locally
        },
      },
    },
  },
});
