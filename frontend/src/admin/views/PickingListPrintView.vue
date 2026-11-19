<template>
  <div class="print-page">
    <!-- 工具栏不参与打印 -->
    <div class="toolbar no-print">
      <el-button @click="router.back()">返回</el-button>
      <span class="tb-title">
        备货清单<template v-if="batch">（{{ fmtPickupDate(batch) }}取货批次）</template>
        · {{ d.total_orders }} 单 · {{ d.total_kinds }} 个品种
      </span>
      <el-button type="primary" :disabled="!d.total_orders" @click="print">打印</el-button>
    </div>

    <div v-if="d.total_orders || !loading" class="sheet">
      <header class="head">
        <h1>备货清单</h1>
        <p class="sub">
          <b>{{ fmtPickupDate(batch) }}</b> 取货批次 · 共 {{ d.total_orders }} 单
          · {{ d.total_kinds }} 个品种 · 合计 {{ d.total_qty }} 件
        </p>
        <p class="meta">生成于 {{ generatedAt }} · 16:00 截单后本批不再增加订单</p>
      </header>

      <!-- 第一部分：按商品汇总（拣货主表，备妥列供打勾） -->
      <table class="tbl">
        <thead>
          <tr>
            <th class="w-no">#</th>
            <th>商品名称</th>
            <th class="w-spec">规格</th>
            <th class="w-unit">单位</th>
            <th class="w-qty">数量</th>
            <th class="w-check">备妥</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in d.summary" :key="i">
            <td class="c-muted">{{ i + 1 }}</td>
            <td class="name">{{ r.p_name }}</td>
            <td class="c-muted">{{ r.p_spec || "—" }}</td>
            <td class="c-muted">{{ r.p_unit || "—" }}</td>
            <td class="qty">{{ r.qty }}</td>
            <td class="check"></td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="4">合计</td>
            <td class="qty">{{ d.total_qty }}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>

      <!-- 第二部分：按订单核对（另起一页） -->
      <section class="detail">
        <h2>按订单核对</h2>
        <table class="tbl">
          <thead>
            <tr>
              <th class="w-code">取货码</th>
              <th class="w-who">订货人</th>
              <th>商品</th>
              <th class="w-qty">件数</th>
              <th class="w-remark">备注</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in d.orders" :key="o.id">
              <td class="code">{{ o.pickup_code }}</td>
              <td>
                {{ o.user?.name || "未补填" }}
                <span class="c-muted">{{ o.user?.empid }}</span>
              </td>
              <td class="items">
                <div v-for="(i, idx) in o.items" :key="idx">
                  {{ i.p_name }}<template v-if="i.p_spec">（{{ i.p_spec }}）</template>
                  × {{ i.qty }}
                </div>
              </td>
              <td class="qty">{{ o.items.reduce((s, i) => s + i.qty, 0) }}</td>
              <td class="remark">{{ o.remark || "" }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
    <el-empty v-else-if="!loading" description="该批次没有待备货的订单" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api } from "../../api/http";
import { fmtPickupDate } from "../../shared/format";

interface SummaryRow {
  p_name: string;
  p_spec: string;
  p_unit: string;
  qty: number;
}
interface DetailOrder {
  id: number;
  pickup_code: string;
  remark: string;
  items: { p_name: string; p_spec: string; qty: number }[];
  user?: { empid: string; name: string | null };
}
interface PickingList {
  batch: string;
  total_orders: number;
  total_kinds: number;
  total_qty: number;
  summary: SummaryRow[];
  orders: DetailOrder[];
}

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const batch = ref("");
const d = ref<PickingList>({
  batch: "", total_orders: 0, total_kinds: 0, total_qty: 0, summary: [], orders: [],
});
const generatedAt = new Date()
  .toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
  .replace(/\//g, "-");

onMounted(async () => {
  const params = new URLSearchParams();
  if (typeof route.query.pickup_date === "string") params.set("pickup_date", route.query.pickup_date);
  try {
    const r = await api<PickingList>(`/api/admin/orders/picking-list?${params}`);
    d.value = r;
    batch.value = r.batch;
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
});

function print() {
  window.print();
}
</script>

<style scoped>
.print-page {
  min-height: 100vh;
  background: var(--sc-bg, #f5f6f7);
  padding: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 210mm;
  margin: 0 auto 16px;
}
.tb-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
}

/* ── 纸面：屏幕上居中模拟 A4，打印时全幅 ── */
.sheet {
  max-width: 210mm;
  margin: 0 auto;
  background: #fff;
  padding: 10mm 12mm;
  box-shadow: 0 1px 6px rgb(31 41 51 / 12%);
}
.head h1 {
  font-size: 22px;
  letter-spacing: 0.35em;
  padding-left: 0.35em; /* 抵消字距，视觉居中 */
  text-align: center;
  margin: 4px 0 6px;
}
.head .sub {
  text-align: center;
  font-size: 13px;
  margin-bottom: 2px;
}
.head .meta {
  text-align: center;
  font-size: 10px;
  color: #999;
  margin-bottom: 12px;
}

/* ── 表格：黑白打印友好，靠字重和边框分层 ── */
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.tbl th {
  border-bottom: 2px solid #333;
  padding: 5px 6px;
  text-align: left;
  font-size: 12px;
  letter-spacing: 0.08em;
}
.tbl td {
  border-bottom: 1px solid #ccc;
  padding: 7px 6px;
  vertical-align: top;
}
.tbl tfoot td {
  border-top: 1.5px solid #333;
  border-bottom: none;
  font-weight: 700;
  padding-top: 6px;
}
.name {
  font-weight: 600;
}
.qty {
  text-align: right;
  font-size: 15px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.c-muted {
  color: #777;
  font-size: 12px;
}
.w-no { width: 24px; }
.w-spec { width: 22%; }
.w-unit { width: 48px; }
.w-qty { width: 52px; }
.w-check { width: 16mm; }
.w-code { width: 70px; }
.w-who { width: 20%; }
.w-remark { width: 18%; }
.check {
  border-left: 1px solid #ccc;
  border-right: 1px solid #ccc;
}
.code {
  font-weight: 700;
  letter-spacing: 0.08em;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.items div {
  line-height: 1.6;
}
.remark {
  font-size: 11px;
  color: #555;
}

/* 第二部分另起一页；跨页时表头自动重复 */
.detail {
  break-before: page;
  margin-top: 0;
}
.detail h2 {
  font-size: 16px;
  letter-spacing: 0.25em;
  padding-left: 0.25em;
  text-align: center;
  margin: 4px 0 10px;
}
.tbl tr {
  break-inside: avoid;
}

@media print {
  @page {
    size: A4 portrait;
    margin: 8mm;
  }
  .print-page {
    padding: 0;
    background: #fff;
  }
  .no-print {
    display: none !important;
  }
  .sheet {
    max-width: none;
    padding: 0;
    box-shadow: none;
  }
}
</style>
