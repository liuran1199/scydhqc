<template>
  <div class="mobile-wrap">
    <router-view v-slot="{ Component }">
      <keep-alive include="HomeView">
        <component :is="Component" />
      </keep-alive>
    </router-view>
    <van-tabbar route safe-area-inset-bottom>
      <van-tabbar-item to="/m" icon="shop-o">商品</van-tabbar-item>
      <van-tabbar-item to="/m/orders" icon="orders-o">我的订单</van-tabbar-item>
      <van-tabbar-item to="/m/notice" icon="bookmark-o">取货须知</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<style scoped>
.mobile-wrap {
  max-width: 640px;
  margin: 0 auto;
  min-height: 100dvh;
  background: var(--sc-bg);
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
}
</style>
