<template>
  <div v-if="o" class="pb-8">
    <van-nav-bar title="订单详情" left-arrow @click-left="router.back()" />

    <div class="p-3 grid gap-3">
      <div v-if="o.status === 'READY' || o.status === 'PENDING'">
        <PickupCode :code="o.pickup_code" />
        <p v-if="o.pickup_date" class="mt-2 text-center text-sm">
          取货日期：<b>{{ fmtPickupDate(o.pickup_date) }}</b>
        </p>
        <p v-if="o.status === 'PENDING'" class="mt-1 text-center text-xs text-[--sc-sub]">
          正在备货，备货完成后即可到店取货
        </p>
      </div>

      <div class="card p-4">
        <div class="flex justify-between items-center">
          <span class="font-bold" :class="o.status === 'CANCELLED' ? 'text-[--sc-sub]' : ''">
            {{ o.status_label }}
          </span>
          <span class="text-xs text-[--sc-sub]">{{ o.order_no }}</span>
        </div>
        <div class="mt-2 text-sm">
          <div v-for="(i, idx) in o.items" :key="idx" class="flex justify-between gap-3 py-1.5">
            <span class="min-w-0">
              {{ i.p_name }}
              <span class="text-[--sc-sub]">（{{ i.p_spec }}）</span>
              × {{ i.qty }}{{ i.p_unit }}
            </span>
            <span class="shrink-0">￥{{ fmtMoney(i.subtotal) }}</span>
          </div>
          <div class="flex justify-between pt-2.5 mt-1 border-t border-[--sc-line] font-bold">
            <span>合计（取货时支付）</span>
            <span class="text-[--sc-price]">￥{{ fmtMoney(o.total) }}</span>
          </div>
          <div v-if="o.remark" class="mt-2 text-xs text-[--sc-sub]">备注：{{ o.remark }}</div>
          <div v-if="o.status === 'CANCELLED'" class="mt-2 text-xs text-[#c05050]">
            取消原因：{{ o.cancel_reason }}
          </div>
        </div>
      </div>

      <van-button
        v-if="o.status === 'PENDING' || o.status === 'READY'"
        block
        round
        type="default"
        @click="cancel"
      >
        取消订单
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { showConfirmDialog, showFailToast, showSuccessToast } from "vant";
import { api } from "../../api/http";
import { fmtMoney, fmtPickupDate } from "../../shared/format";
import PickupCode from "../components/PickupCode.vue";

interface OrderDetail {
  id: number;
  order_no: string;
  status: string;
  status_label: string;
  total: number;
  remark: string;
  pickup_code: string;
  pickup_date: string | null;
  cancel_reason: string;
  items: { p_name: string; p_spec: string; p_unit: string; qty: number; subtotal: number }[];
}

const route = useRoute();
const router = useRouter();
const o = ref<OrderDetail | null>(null);

async function load() {
  try {
    o.value = await api<OrderDetail>(`/api/orders/${route.params.id}`);
  } catch (e) {
    showFailToast(e instanceof Error ? e.message : "加载失败");
    router.replace("/m/orders");
  }
}

async function cancel() {
  try {
    await showConfirmDialog({ title: "取消订单", message: "确定取消这个订单吗？" });
  } catch {
    return; // 用户放弃
  }
  try {
    await api(`/api/orders/${route.params.id}/cancel`, { method: "POST" });
    showSuccessToast("已取消");
    load();
  } catch (e) {
    showFailToast(e instanceof Error ? e.message : "取消失败");
  }
}

onMounted(load);
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
</style>
