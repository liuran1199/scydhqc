import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://127.0.0.1:13100" },
  retries: 0,
  workers: 1, // 共享 SQLite 状态，串行更稳
  reporter: "list",
});
