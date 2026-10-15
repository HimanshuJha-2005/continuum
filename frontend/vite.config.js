import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/chat": "http://localhost:8000",
      "/trace": "http://localhost:8000",
      "/memory": "http://localhost:8000",
      "/agents": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
