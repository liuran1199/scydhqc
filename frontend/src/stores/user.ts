import { defineStore } from "pinia";
import { api } from "../api/http";

export interface UserInfo {
  empid: string;
  name: string | null;
  phone: string | null;
}

export const useUserStore = defineStore("user", {
  state: () => ({ user: null as UserInfo | null, checked: false }),
  actions: {
    async fetch() {
      try {
        this.user = await api<UserInfo>("/api/auth/me");
      } catch {
        this.user = null;
      }
      this.checked = true;
    },
  },
});
