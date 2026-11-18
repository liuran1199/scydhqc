<template>
  <div class="notice-page">
    <van-nav-bar title="取货须知" />
    <div class="px-4 pt-4">
      <div class="card">
        <p class="whitespace-pre-wrap leading-7 text-[15px] text-[--sc-ink]">
          {{ content || "暂无须知内容。" }}
        </p>
      </div>
      <p class="mt-3 text-center text-xs text-[--sc-sub]">后勤处 · 食材服务点</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "../../api/http";

const content = ref("");
onMounted(async () => {
  try {
    const d = await api<{ content: string }>("/api/notice");
    content.value = d.content;
  } catch {
    content.value = "";
  }
});
</script>

<style scoped>
.notice-page {
  min-height: 100dvh;
  background: var(--sc-bg);
}
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 20px 18px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 6%);
}
</style>
