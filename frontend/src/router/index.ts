import { createRouter, createWebHistory } from "vue-router";
import { useUserStore } from "../stores/user";
import { useAdminStore } from "../stores/admin";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/m" },
    {
      path: "/m",
      component: () => import("../mobile/MobileLayout.vue"),
      children: [
        { path: "", component: () => import("../mobile/views/HomeView.vue") },
        { path: "orders", component: () => import("../mobile/views/OrdersView.vue") },
        { path: "cart", component: () => import("../mobile/views/CartView.vue") },
        { path: "confirm", component: () => import("../mobile/views/ConfirmView.vue") },
        { path: "order/:id", component: () => import("../mobile/views/OrderDetailView.vue") },
        { path: "product/:id", component: () => import("../mobile/views/ProductView.vue") },
      ],
    },
    { path: "/admin/login", component: () => import("../admin/views/LoginView.vue") },
    {
      path: "/admin",
      component: () => import("../admin/AdminLayout.vue"),
      children: [
        { path: "", redirect: "/admin/dashboard" },
        { path: "dashboard", component: () => import("../admin/views/DashboardView.vue") },
        { path: "products", component: () => import("../admin/views/ProductsView.vue") },
        { path: "orders", component: () => import("../admin/views/OrdersView.vue") },
        { path: "verify", component: () => import("../admin/views/VerifyView.vue") },
        { path: "stats", component: () => import("../admin/views/StatsView.vue") },
        { path: "settings", component: () => import("../admin/views/SettingsView.vue") },
      ],
    },
    // 兜底：失效地址（如已下线的 /m/notice）统一回首页
    { path: "/:pathMatch(.*)*", redirect: "/m" },
  ],
});

router.beforeEach(async (to) => {
  if (to.path.startsWith("/admin")) {
    const a = useAdminStore();
    if (to.path === "/admin/login") return true;
    if (!a.checked) await a.fetch();
    if (!a.admin) return "/admin/login";
    return true;
  }
  if (to.path.startsWith("/m")) {
    const u = useUserStore();
    if (!u.checked) await u.fetch();
    if (!u.user) {
      window.location.href = "/api/auth/cas/login"; // CAS 静默往返
      return false;
    }
  }
  return true;
});

export default router;
