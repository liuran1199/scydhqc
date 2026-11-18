<template>
  <div>
    <!-- 筛选 -->
    <div class="card bar">
      <el-date-picker
        v-model="range"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :clearable="false"
      />
      <el-button type="primary" @click="load">查询</el-button>
      <div class="spacer" />
      <el-button :icon="Download" @click="exportXlsx">导出核销流水</el-button>
    </div>

    <div v-loading="loading">
      <!-- 汇总 -->
      <div class="tiles" v-if="s">
        <div class="tile">
          <div class="tile-label">订单总数</div>
          <div class="tile-value">{{ s.order_count }}</div>
          <div class="tile-hint">{{ range[0] }} ~ {{ range[1] }} 下单</div>
        </div>
        <div class="tile">
          <div class="tile-label">核销单数</div>
          <div class="tile-value">{{ s.done_count }}</div>
        </div>
        <div class="tile">
          <div class="tile-label">核销金额</div>
          <div class="tile-value money">￥{{ fmtMoney(s.done_amount) }}</div>
          <div class="tile-hint">现场收款合计</div>
        </div>
        <div class="tile">
          <div class="tile-label">状态分布</div>
          <div class="chips">
            <span v-for="st in STATUS_ROWS" :key="st.key" class="chip">
              <i :class="st.cls" />{{ st.label }} {{ s.by_status[st.key] ?? 0 }}
            </span>
          </div>
        </div>
      </div>

      <!-- 商品销量排行 -->
      <div class="card" v-if="s">
        <div class="card-head">
          <div>
            <div class="card-title">商品销量排行</div>
            <div class="card-sub">仅统计已核销订单，按数量取前 10</div>
          </div>
        </div>
        <el-table :data="s.top_products" :show-header="true" stripe>
          <el-table-column type="index" width="56" align="center">
            <template #default="{ $index }">
              <span class="rank" :class="{ top3: $index < 3 }">{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="商品" min-width="200" />
          <el-table-column prop="qty" label="数量" width="120" align="right" />
          <el-table-column label="金额" width="160" align="right">
            <template #default="{ row }">
              <span class="amount">￥{{ fmtMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="该时段暂无核销订单" :image-size="80" />
          </template>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { Download } from "@element-plus/icons-vue";
import { api, download } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface TopProduct {
  name: string;
  qty: number;
  amount: number;
}
interface RangeStats {
  order_count: number;
  done_count: number;
  done_amount: number;
  by_status: Record<string, number>;
  top_products: TopProduct[];
}

const STATUS_ROWS = [
  { key: "PENDING", label: "待备货", cls: "dot pending" },
  { key: "READY", label: "待取货", cls: "dot ready" },
  { key: "DONE", label: "已完成", cls: "dot done" },
  { key: "CANCELLED", label: "已取消", cls: "dot cancelled" },
] as const;

const now = new Date();
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
  now.getDate(),
).padStart(2, "0")}`;
const range = ref<[string, string]>([today, today]);
const s = ref<RangeStats | null>(null);
const loading = ref(false);

async function load() {
  const [f, t] = range.value || [];
  if (!f || !t) {
    ElMessage.warning("请选择日期范围");
    return;
  }
  loading.value = true;
  s.value = null;
  try {
    s.value = await api<RangeStats>(`/api/admin/stats?date_from=${f}&date_to=${t}`);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "查询失败");
  } finally {
    loading.value = false;
  }
}

function exportXlsx() {
  const [f, t] = range.value || [];
  if (!f || !t) {
    ElMessage.warning("请选择日期范围");
    return;
  }
  download(`/api/admin/stats/export?date_from=${f}&date_to=${t}`);
}

onMounted(load);
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.spacer {
  flex: 1;
}
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
  font-size: 24px;
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
.chips {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  font-size: 13px;
  color: var(--sc-ink);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-variant-numeric: tabular-nums;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot.pending {
  background: #b97a24;
}
.dot.ready {
  background: var(--sc-primary);
}
.dot.done {
  background: #8a949d;
}
.dot.cancelled {
  background: #c5ccd2;
}
.card-head {
  margin-bottom: 14px;
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
.rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--sc-sub);
  background: var(--sc-bg);
  font-variant-numeric: tabular-nums;
}
.rank.top3 {
  background: var(--sc-primary-soft);
  color: var(--sc-primary);
  font-weight: 600;
}
.amount {
  font-variant-numeric: tabular-nums;
}
</style>
