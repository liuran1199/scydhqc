<template>
  <div class="p-4">
    <div class="card">
      <h2 class="text-lg font-semibold">食材服务点</h2>
      <p class="mt-1 text-sm text-[--sc-sub]">线上预订 · 备货后到店自提 · 现场支付</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: "HomeView" });
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 20px 18px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 6%);
}
</style>
