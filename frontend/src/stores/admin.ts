import { defineStore } from "pinia";
import { api } from "../api/http";

export interface AdminInfo {
  id: number;
  username: string;
  role: string;
  name: string;
}

export const useAdminStore = defineStore("admin", {
  state: () => ({ admin: null as AdminInfo | null, checked: false }),
  actions: {
    async fetch() {
      try {
        this.admin = await api<AdminInfo>("/api/admin/auth/me");
      } catch {
        this.admin = null;
      }
      this.checked = true;
    },
    async login(username: string, password: string) {
      this.admin = await api<AdminInfo>("/api/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      this.checked = true;
    },
    async logout() {
      await api("/api/admin/auth/logout", { method: "POST" });
      this.admin = null;
    },
  },
});
