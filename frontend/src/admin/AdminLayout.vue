<template>
  <el-container class="h-screen">
    <el-aside width="216px" class="side">
      <div class="brand">
        <div class="brand-mark">食</div>
        <div class="min-w-0">
          <div class="brand-name">食材服务点</div>
          <div class="brand-sub">预订管理后台</div>
        </div>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        class="side-menu"
        background-color="transparent"
        text-color="rgba(255,255,255,0.66)"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><Odometer /></el-icon>工作台
        </el-menu-item>
        <el-menu-item index="/admin/products">
          <el-icon><Goods /></el-icon>商品管理
        </el-menu-item>
        <el-menu-item index="/admin/orders">
          <el-icon><Tickets /></el-icon>订单管理
        </el-menu-item>
        <el-menu-item index="/admin/verify">
          <el-icon><CircleCheck /></el-icon>核销
        </el-menu-item>
        <el-menu-item index="/admin/stats">
          <el-icon><DataAnalysis /></el-icon>统计对账
        </el-menu-item>
        <el-menu-item v-if="store.admin?.role === 'super'" index="/admin/settings">
          <el-icon><Setting /></el-icon>系统设置
        </el-menu-item>
      </el-menu>
      <div class="side-foot">后勤管理处</div>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div class="topbar-title">{{ pageTitle }}</div>
        <el-dropdown @command="onCommand">
          <span class="who">
            <span class="avatar">{{ avatarChar }}</span>
            <span class="ml-2">{{ store.admin?.name || store.admin?.username }}</span>
            <el-icon class="ml-1"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowDown,
  CircleCheck,
  DataAnalysis,
  Goods,
  Odometer,
  Setting,
  SwitchButton,
  Tickets,
} from "@element-plus/icons-vue";
import { useAdminStore } from "../stores/admin";

const TITLES: Record<string, string> = {
  "/admin/dashboard": "工作台",
  "/admin/products": "商品管理",
  "/admin/orders": "订单管理",
  "/admin/verify": "核销",
  "/admin/stats": "统计对账",
  "/admin/settings": "系统设置",
};

const store = useAdminStore();
const route = useRoute();
const router = useRouter();

const pageTitle = computed(() => TITLES[route.path] || "管理后台");
const avatarChar = computed(
  () => (store.admin?.name || store.admin?.username || "管").slice(0, 1),
);

function onCommand(cmd: string) {
  if (cmd !== "logout") return;
  store.logout();
  router.push("/admin/login");
}
</script>

<style scoped>
.side {
  background: #1c3b2a;
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 18px 16px;
}
.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: var(--sc-primary);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.brand-name {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.brand-sub {
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
  margin-top: 1px;
}
.side-menu {
  border-right: none;
  flex: 1;
  padding: 4px 10px;
}
.side-menu :deep(.el-menu-item) {
  border-radius: 8px;
  margin: 2px 0;
  height: 44px;
}
.side-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
}
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--sc-primary);
}
.side-foot {
  padding: 14px;
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
  text-align: center;
}
.topbar {
  background: var(--sc-card);
  border-bottom: 1px solid var(--sc-line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}
.topbar-title {
  font-size: 15px;
  font-weight: 600;
}
.who {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 14px;
  color: var(--sc-ink);
  outline: none;
}
.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--sc-primary-soft);
  color: var(--sc-primary);
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.main {
  background: var(--sc-bg);
}
</style>
