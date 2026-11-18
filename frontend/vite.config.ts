import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: { "/api": "http://127.0.0.1:13000", "/uploads": "http://127.0.0.1:13000" },
  },
  build: { outDir: "dist" },
  test: { environment: "node" },
});
