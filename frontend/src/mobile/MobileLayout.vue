<template>
  <div class="mobile-wrap">
    <router-view v-slot="{ Component }">
      <keep-alive include="HomeView">
        <component :is="Component" />
      </keep-alive>
    </router-view>
    <van-tabbar v-if="!route.meta.hideTabbar" :model-value="activeTab" safe-area-inset-bottom @change="onTabChange">
      <van-tabbar-item icon="shop-o">商品</van-tabbar-item>
      <van-tabbar-item>
        购物车
        <template #icon>
          <van-badge :content="cart.count || ''" :show-zero="false">
            <van-icon name="cart-o" />
          </van-badge>
        </template>
      </van-tabbar-item>
      <van-tabbar-item icon="orders-o">我的订单</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useCartStore } from "../stores/cart";

const cart = useCartStore();
const route = useRoute();
const router = useRouter();

const TAB_TO = ["/m", "/m/cart", "/m/orders"];

// 不用 vant 的 route 模式：它按 matched 前缀判断激活，在 /m/orders 会把
// 「商品」(/m) 误判为当前项，点击被忽略，导致订单页回不到商品页。
// 这里自行精确匹配路由 → 高亮，点击由 @change 显式跳转。
const activeTab = computed(() => {
  if (route.path === "/m") return 0;
  if (route.path === "/m/cart") return 1;
  if (route.path === "/m/orders" || /^\/m\/order\/\d+/.test(route.path)) return 2;
  return -1; // 确认订单 / 商品详情等过程页：不高亮任何 tab
});

function onTabChange(i: number | string) {
  const to = TAB_TO[Number(i)];
  if (to && to !== route.path) router.push(to); // 已在当前页时跳过重复导航
}
</script>

<style scoped>
.mobile-wrap {
  max-width: 640px;
  margin: 0 auto;
  min-height: 100dvh;
  background: var(--sc-bg);
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
}
</style>
