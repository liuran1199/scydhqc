<template>
  <div class="pb-6">
    <van-tabs v-model:active="tab" shrink sticky line-width="20px" @change="reload">
      <van-tab v-for="(label, s) in TABS" :key="s" :title="label" :name="s" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <div class="p-3 grid gap-2.5">
        <van-list
          v-model:loading="loading"
          v-model:error="loadError"
          :finished="finished"
          :finished-text="orders.length ? '没有更多了' : ''"
          error-text="加载失败，点击重试"
          @load="loadMore"
        >
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
                <template v-if="o.pickup_date && (o.status === 'PENDING' || o.status === 'READY')">
                  {{ fmtPickupDate(o.pickup_date) }}取货 ·
                </template>
                {{ (o.created_at || "").slice(5, 16).replace("T", " ") }}
              </span>
              <span class="font-bold">￥{{ fmtMoney(o.total) }}</span>
            </div>
          </div>
        </van-list>

        <van-empty
          v-if="!loading && finished && !orders.length"
          description="暂无订单"
        />
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { showFailToast } from "vant";
import { api } from "../../api/http";
import { fmtMoney, fmtPickupDate } from "../../shared/format";

interface OrderRow {
  id: number;
  order_no: string;
  status: string;
  status_label: string;
  total: number;
  pickup_date: string | null;
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
const loadError = ref(false);
const finished = ref(false);
const refreshing = ref(false);
const page = ref(0);
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

/** 拉下一页并追加（van-list 滚动到底自动触发，首载也由其发起） */
let seq = 0;
async function loadMore() {
  const cur = ++seq;
  loading.value = true;
  const params = new URLSearchParams({ page: String(page.value + 1) });
  if (tab.value) params.set("status", tab.value);
  try {
    const d = await api<{ items: OrderRow[]; total: number }>(`/api/orders?${params}`);
    if (cur !== seq) return; // 期间已切 tab / 下拉刷新，丢弃过期响应
    orders.value = page.value === 0 ? d.items : [...orders.value, ...d.items];
    page.value += 1;
    finished.value = orders.value.length >= d.total;
  } catch {
    if (cur === seq) {
      loadError.value = true;
      showFailToast("订单加载失败");
    }
  } finally {
    if (cur === seq) {
      loading.value = false;
      refreshing.value = false;
    }
  }
}

/** 切状态 tab / 下拉刷新：清空重拉第一页 */
function reload() {
  seq++; // 作废在途请求
  page.value = 0;
  orders.value = [];
  finished.value = false;
  loadError.value = false;
  loadMore();
}

function onRefresh() {
  reload();
}
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
