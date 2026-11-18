import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/m" },
    { path: "/m", component: () => import("../mobile/views/HomeView.vue") },
    { path: "/m/orders", component: () => import("../mobile/views/OrdersView.vue") },
    { path: "/m/notice", component: () => import("../mobile/views/NoticeView.vue") },
    { path: "/admin/login", component: () => import("../admin/views/LoginView.vue") },
    { path: "/admin", redirect: "/admin/dashboard" },
  ],
});

export default router;
