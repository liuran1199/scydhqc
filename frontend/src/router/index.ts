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
        // 确认订单/商品详情是过程页，自带底部操作条，隐藏全局导航避免重叠；
        // 购物车是主导航页：保留底部导航，结算栏叠在导航栏上方（淘宝/京东惯例）
        { path: "cart", component: () => import("../mobile/views/CartView.vue") },
        { path: "confirm", component: () => import("../mobile/views/ConfirmView.vue"), meta: { hideTabbar: true } },
        { path: "order/:id", component: () => import("../mobile/views/OrderDetailView.vue") },
        { path: "product/:id", component: () => import("../mobile/views/ProductView.vue"), meta: { hideTabbar: true } },
      ],
    },
    { path: "/admin/login", component: () => import("../admin/views/LoginView.vue") },
    // 打印页：独立全屏（不在管理布局内，打印时不带侧边栏）
    {
      path: "/admin/print/receipts",
      component: () => import("../admin/views/ReceiptsPrintView.vue"),
    },
    {
      path: "/admin/print/picking-list",
      component: () => import("../admin/views/PickingListPrintView.vue"),
    },
    // 窗口核销：手机竖屏独立页（扫码/输码两个入口都落这里）
    {
      path: "/admin/verify",
      component: () => import("../admin/views/VerifyView.vue"),
    },
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
