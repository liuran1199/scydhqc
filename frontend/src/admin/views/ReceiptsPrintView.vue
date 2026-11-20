<template>
  <div class="print-page">
    <!-- 工具栏不参与打印 -->
    <div class="toolbar no-print">
      <el-button @click="router.back()">返回</el-button>
      <span class="tb-title">
        订单小票<template v-if="!hasIds">（待备队列）</template> · 共 {{ orders.length }} 张
      </span>
      <el-button type="primary" :disabled="!orders.length" @click="print">打印</el-button>
    </div>

    <div v-if="orders.length" class="slips">
      <div v-for="o in orders" :key="o.id" class="slip">
        <div class="slip-head">
          <span class="s-date">{{ (o.created_at || "").slice(5, 10) }} 下单</span>
          <span class="s-no">{{ o.order_no.slice(-6) }}</span>
        </div>
        <div class="s-code">{{ o.pickup_code }}</div>
        <div class="s-who">{{ o.user?.name || "未补填姓名" }}（{{ o.user?.empid }}）</div>
        <div class="s-items">
          <div v-for="(i, idx) in o.items" :key="idx" class="s-item">
            <span class="s-name">{{ i.p_name }}<i v-if="i.p_spec">（{{ i.p_spec }}）</i></span>
            <span class="s-qty">×{{ i.qty }}{{ i.p_unit }}</span>
          </div>
        </div>
        <div class="s-total">合计 ￥{{ fmtMoney(o.total) }}<span>（取货时支付）</span></div>
        <div v-if="o.remark" class="s-remark">备注：{{ o.remark }}</div>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="当前没有待打印的订单" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface PrintOrder {
  id: number;
  order_no: string;
  status: string;
  total: number;
  remark: string;
  pickup_code: string;
  created_at: string | null;
  items: { p_name: string; p_spec: string; p_unit: string; qty: number }[];
  user?: { empid: string; name: string | null };
}

const route = useRoute();
const router = useRouter();
const orders = ref<PrintOrder[]>([]);
const loading = ref(true);
const hasIds = typeof route.query.ids === "string" && route.query.ids.length > 0;

onMounted(async () => {
  const params = new URLSearchParams();
  if (hasIds) params.set("ids", route.query.ids as string);
  try {
    const d = await api<{ items: PrintOrder[] }>(`/api/admin/orders/receipts?${params}`);
    orders.value = d.items;
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
  margin-bottom: 16px;
}
.tb-title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
}

/* ── 小票：A4 两列排布，虚线裁切 ── */
.slips {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.slip {
  border: 1px dashed #b8bec4;
  border-radius: 4px;
  padding: 10px 14px 12px;
  min-height: 150px;
  display: flex;
  flex-direction: column;
  background: #fff;
  break-inside: avoid;
  page-break-inside: avoid;
}
.slip-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #666;
}
.s-date {
  font-weight: 600;
  color: #333;
}
.s-code {
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 0.28em;
  text-align: center;
  margin: 6px 0 2px;
  padding-left: 0.28em; /* 抵消字距，视觉居中 */
  font-variant-numeric: tabular-nums;
}
.s-who {
  text-align: center;
  font-size: 15px;
  font-weight: 600;
  padding-bottom: 6px;
  border-bottom: 1px solid #e5e8eb;
}
.s-items {
  flex: 1;
  padding: 4px 0;
}
.s-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  line-height: 1.7;
}
.s-item i {
  font-style: normal;
  color: #888;
  font-size: 12px;
}
.s-total {
  font-size: 14px;
  font-weight: 700;
  border-top: 1px solid #e5e8eb;
  padding-top: 5px;
}
.s-total span {
  font-weight: 400;
  font-size: 11px;
  color: #888;
  margin-left: 6px;
}
.s-remark {
  margin-top: 3px;
  font-size: 11px;
  color: #b06000;
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
  .slips {
    gap: 6mm;
  }
  .slip {
    border-color: #999;
    min-height: 58mm; /* A4 竖版两列四行，裁切后约名片两倍大 */
  }
}
</style>
