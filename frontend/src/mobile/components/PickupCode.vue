<template>
  <div class="code-card">
    <div class="caption">取货码 · 出示给工作人员</div>
    <div class="digits">{{ code }}</div>
    <div class="qr-box">
      <img v-if="dataUrl" :src="dataUrl" alt="取货二维码" />
      <van-loading v-else color="var(--sc-primary)" />
    </div>
    <p class="hint">扫码或输入取货码核销</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import QRCode from "qrcode";

const props = defineProps<{ code: string; orderNo: string }>();
const dataUrl = ref("");

onMounted(async () => {
  dataUrl.value = await QRCode.toDataURL(`SC:${props.orderNo}:${props.code}`, {
    width: 320,
    margin: 1,
    color: { dark: "#1f2933", light: "#ffffff" },
  });
});
</script>

<style scoped>
.code-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 16px 16px;
  background: var(--sc-card);
  border-radius: 16px;
  box-shadow: 0 2px 8px rgb(31 41 51 / 8%);
}
.caption {
  font-size: 12px;
  color: var(--sc-sub);
  letter-spacing: 1px;
}
.digits {
  margin-top: 8px;
  font-size: 38px;
  font-weight: 700;
  letter-spacing: 0.28em;
  text-indent: 0.28em; /* 平衡末字间距 */
  color: var(--sc-ink);
  font-variant-numeric: tabular-nums;
}
.qr-box {
  margin-top: 12px;
  padding: 10px;
  border: 1px dashed var(--sc-line);
  border-radius: 12px;
  width: 176px;
  height: 176px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.qr-box img {
  width: 100%;
  height: 100%;
}
.hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--sc-sub);
}
</style>
