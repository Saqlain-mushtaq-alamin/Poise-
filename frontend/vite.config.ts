import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://tauri.app/develop/#prevent-vite-from-obscuring-rust-errors
export default defineConfig(async () => ({
  plugins: [react()],

  // Tauri expects a fixed port, fails if that port is not available
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // Tell vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },

  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
}));
