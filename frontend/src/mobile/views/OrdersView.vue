<template>
  <div class="pb-6">
    <van-tabs v-model:active="tab" shrink sticky line-width="20px" @change="load">
      <van-tab v-for="(label, s) in TABS" :key="s" :title="label" :name="s" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="load">
      <div class="p-3 grid gap-2.5">
        <div
          v-for="o in orders"
          :key="o.id"
          class="card"
          @click="router.push(`/m/order/${o.id}`)"
        >
          <div class="flex justify-between items-center">
            <span class="text-xs text-[--sc-sub]">{{ o.order_no }}</span>
            <span class="status" :class="statusClass(o.status)">{{ o.status_label }}</span>
          </div>
          <div class="mt-1.5 text-sm leading-5">{{ itemsText(o) }}</div>
          <div class="mt-1.5 flex justify-between items-center">
            <span class="text-xs text-[--sc-sub]">
              {{ (o.created_at || "").slice(5, 16).replace("T", " ") }}
            </span>
            <span class="font-bold">￥{{ fmtMoney(o.total) }}</span>
          </div>
        </div>

        <van-empty v-if="!loading && !orders.length" description="暂无订单" />
        <div v-if="loading" class="py-10 text-center">
          <van-loading color="var(--sc-primary)">加载中…</van-loading>
        </div>
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface OrderRow {
  id: number;
  order_no: string;
  status: string;
  status_label: string;
  total: number;
  created_at: string | null;
  items: { p_name: string; qty: number }[];
}

const TABS: Record<string, string> = {
  "": "全部",
  PENDING: "待备货",
  READY: "待取货",
  DONE: "已完成",
};
const tab = ref("");
const orders = ref<OrderRow[]>([]);
const loading = ref(false);
const refreshing = ref(false);
const router = useRouter();

function itemsText(o: OrderRow) {
  return o.items.map((i) => `${i.p_name}×${i.qty}`).join("；");
}

function statusClass(s: string) {
  if (s === "DONE") return "st-done";
  if (s === "CANCELLED") return "st-cancelled";
  if (s === "READY") return "st-ready";
  return "st-pending";
}

async function load() {
  loading.value = true;
  const params = tab.value ? `?status=${tab.value}` : "";
  try {
    const d = await api<{ items: OrderRow[] }>(`/api/orders${params}`);
    orders.value = d.items;
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.status {
  font-size: 12px;
  font-weight: 600;
}
.st-pending {
  color: #b97a24;
}
.st-ready {
  color: var(--sc-primary);
}
.st-done {
  color: var(--sc-sub);
}
.st-cancelled {
  color: #a0aaB3;
  text-decoration: line-through;
}
</style>
