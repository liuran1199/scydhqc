<template>
  <div class="mobile-wrap">
    <router-view v-slot="{ Component }">
      <keep-alive include="HomeView">
        <component :is="Component" />
      </keep-alive>
    </router-view>
    <van-tabbar route safe-area-inset-bottom>
      <van-tabbar-item to="/m">
        商品
        <template #icon>
          <van-badge :content="cart.count || ''" :show-zero="false">
            <van-icon name="shop-o" />
          </van-badge>
        </template>
      </van-tabbar-item>
      <van-tabbar-item to="/m/orders" icon="orders-o">我的订单</van-tabbar-item>
      <van-tabbar-item to="/m/notice" icon="bookmark-o">取货须知</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { useCartStore } from "../stores/cart";

const cart = useCartStore();
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
