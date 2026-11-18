<template>
  <div v-loading="loading">
    <!-- 统计卡 -->
    <div class="tiles">
      <div v-for="t in tiles" :key="t.label" class="tile">
        <div class="tile-label">{{ t.label }}</div>
        <div class="tile-value" :class="t.money ? 'money' : ''">{{ t.value }}</div>
        <div v-if="t.hint" class="tile-hint">{{ t.hint }}</div>
      </div>
    </div>

    <!-- 近 7 日订单 -->
    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">近 7 日订单</div>
          <div class="card-sub">按下单时间统计，柱高为订单数</div>
        </div>
        <div class="legend-dot"><span class="dot" />订单数</div>
      </div>
      <div v-if="d" class="chart" role="img" aria-label="近7日每日订单数柱状图">
        <div v-for="b in d.last7" :key="b.date" class="col" :aria-label="ariaOf(b)">
          <div class="col-plot">
            <span class="val" :class="{ show: b.orders === maxOrders }">{{ b.orders }}</span>
            <div
              class="bar"
              :class="{ zero: !b.orders, peak: b.orders === maxOrders }"
              :style="{ height: barHeight(b.orders) }"
            />
          </div>
          <div class="day" :class="{ today: b.date === todayLabel }">{{ b.date }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface DayBar {
  date: string;
  orders: number;
  sales: number;
}
interface Dashboard {
  today_new: number;
  pending: number;
  ready: number;
  today_done_count: number;
  today_done_amount: number;
  last7: DayBar[];
}

const d = ref<Dashboard | null>(null);
const loading = ref(false);

const tiles = computed(() => {
  if (!d.value) return [];
  return [
    { label: "今日新增订单", value: String(d.value.today_new) },
    { label: "待备货", value: String(d.value.pending) },
    { label: "待取货", value: String(d.value.ready) },
    {
      label: "今日核销金额",
      value: "￥" + fmtMoney(d.value.today_done_amount),
      hint: `共核销 ${d.value.today_done_count} 单`,
      money: true,
    },
  ];
});

const maxOrders = computed(() =>
  d.value ? Math.max(...d.value.last7.map((x) => x.orders)) : 0,
);
const n = new Date();
const todayLabel = `${String(n.getMonth() + 1).padStart(2, "0")}-${String(
  n.getDate(),
).padStart(2, "0")}`;

function barHeight(n: number) {
  const max = Math.max(maxOrders.value, 1);
  return n ? `${Math.max((n / max) * 100, 4)}%` : "3px";
}
function ariaOf(b: DayBar) {
  return `${b.date}：${b.orders} 单，核销金额 ￥${fmtMoney(b.sales)}`;
}

onMounted(async () => {
  loading.value = true;
  try {
    d.value = await api<Dashboard>("/api/admin/stats/dashboard");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.tiles {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.tile {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 18px 20px 16px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.tile-label {
  font-size: 13px;
  color: var(--sc-sub);
}
.tile-value {
  margin-top: 6px;
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.tile-value.money {
  color: var(--sc-price);
}
.tile-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sc-sub);
}
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 18px 20px 20px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
}
.card-sub {
  margin-top: 3px;
  font-size: 12px;
  color: var(--sc-sub);
}
.legend-dot {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--sc-sub);
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--sc-chart);
}
.chart {
  display: flex;
  align-items: stretch;
  gap: 8px;
  height: 200px;
  border-bottom: 1px solid var(--sc-line);
  padding-bottom: 0;
}
.col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: default;
}
.col-plot {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}
.bar {
  width: 26px;
  max-width: 70%;
  border-radius: 4px 4px 0 0;
  background: var(--sc-chart);
  transition: filter 0.15s;
}
.bar.zero {
  background: var(--sc-line);
}
.col:hover .bar:not(.zero) {
  filter: brightness(0.85);
}
.val {
  font-size: 12px;
  color: var(--sc-sub);
  margin-bottom: 4px;
  opacity: 0;
  font-variant-numeric: tabular-nums;
}
.col:hover .val,
.val.show {
  opacity: 1;
}
.col:hover .val {
  color: var(--sc-ink);
}
.day {
  margin-top: 8px;
  font-size: 12px;
  color: var(--sc-sub);
  font-variant-numeric: tabular-nums;
  padding-bottom: 2px;
}
.day.today {
  color: var(--sc-ink);
  font-weight: 600;
}
</style>
