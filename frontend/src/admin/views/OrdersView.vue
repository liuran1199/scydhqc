<template>
  <div>
    <!-- 筛选 -->
    <div class="card bar">
      <el-select v-model="status" placeholder="全部状态" clearable class="w-32" @change="load(1)">
        <el-option label="待备货" value="PENDING" />
        <el-option label="待取货" value="READY" />
        <el-option label="已完成" value="DONE" />
        <el-option label="已取消" value="CANCELLED" />
      </el-select>
      <el-date-picker
        v-model="range"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
      />
      <el-input
        v-model="q"
        placeholder="订单号 / 取货码 / 工号 / 姓名"
        class="w-56"
        clearable
        @keyup.enter="load(1)"
        @clear="load(1)"
      />
      <el-button @click="load(1)">查询</el-button>
      <el-tag
        v-if="pickupFilter"
        closable
        type="primary"
        effect="light"
        @close="clearBatchFilter"
      >
        {{ fmtPickupDate(pickupFilter) }}取货批次
      </el-tag>
      <div class="spacer" />
      <el-button :icon="Document" @click="printPickingList">
        今日备货单{{ batchCount ? `（${batchCount}）` : "" }}
      </el-button>
      <el-button :icon="Printer" @click="viewBatch">{{ batchFilterActive ? "退出本批" : "查看本批" }}</el-button>
      <el-button :icon="Printer" @click="printReceipts">
        打印小票{{ sel.length ? `（选中 ${sel.length}）` : "（本批）" }}
      </el-button>
      <el-button
        type="primary"
        :disabled="!sel.length"
        :loading="readying"
        @click="batchReady"
      >
        批量备货完成{{ sel.length ? `（${sel.length}）` : "" }}
      </el-button>
    </div>

    <!-- 订单表 -->
    <div class="card" v-loading="loading">
      <el-table :data="items" @selection-change="(s: AdminOrder[]) => (sel = s)">
        <el-table-column type="selection" width="44" :selectable="selectable" />
        <el-table-column prop="order_no" label="订单号" width="150" />
        <el-table-column label="订货人" width="130">
          <template #default="{ row }">
            {{ row.user?.name || "未补填" }}
            <span class="empid">（{{ row.user?.empid }}）</span>
          </template>
        </el-table-column>
        <el-table-column label="取货码" width="86">
          <template #default="{ row }">
            <span class="code">{{ row.pickup_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="商品" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.items.map((i) => `${i.p_name}×${i.qty}`).join("；") }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="100" align="right">
          <template #default="{ row }">
            <span class="amount">￥{{ fmtMoney(row.total) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            <el-tag :type="TAG[row.status]" size="small" effect="light">
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下单时间" width="140">
          <template #default="{ row }">
            {{ (row.created_at || "").slice(0, 16).replace("T", " ") }}
          </template>
        </el-table-column>
        <el-table-column label="取货日期" width="120">
          <template #default="{ row }">
            <span :class="{ 'pu-soon': row.pickup_date === batchDate }">
              {{ row.pickup_date ? `${fmtPickupDate(row.pickup_date)}取` : "—" }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'PENDING' || row.status === 'READY'"
              link
              type="danger"
              @click="cancel(row)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有符合条件的订单" :image-size="80" />
        </template>
      </el-table>
      <el-pagination
        class="mt-4"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="20"
        :current-page="page"
        @current-change="load"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Document, Printer } from "@element-plus/icons-vue";
import { api } from "../../api/http";
import { fmtMoney, fmtPickupDate } from "../../shared/format";

interface OrderItem {
  p_name: string;
  p_spec: string;
  p_unit: string;
  qty: number;
}
interface AdminOrder {
  id: number;
  order_no: string;
  status: string;
  status_label: string;
  total: number;
  pickup_code: string;
  pickup_date: string | null;
  created_at: string | null;
  items: OrderItem[];
  user?: { empid: string; name: string | null };
}

const TAG: Record<string, "warning" | "success" | "info" | "danger"> = {
  PENDING: "warning",
  READY: "success",
  DONE: "info",
  CANCELLED: "info",
};
const status = ref("");
const q = ref("");
const range = ref<[string, string] | null>(null);
const items = ref<AdminOrder[]>([]);
const sel = ref<AdminOrder[]>([]);
const total = ref(0);
const page = ref(1);
const loading = ref(false);
const readying = ref(false);

// ── 备货批次：今晚备「明天取货」的单（16 点截单）──
const tomorrow = new Date();
tomorrow.setDate(tomorrow.getDate() + 1);
const batchDate = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;
const batchCount = ref(0);
const pickupFilter = ref<string | null>(null);
const batchFilterActive = computed(() => pickupFilter.value === batchDate);

function printPickingList() {
  window.open(`/admin/print/picking-list?pickup_date=${batchDate}`, "_blank");
}

async function loadBatchCount() {
  try {
    // 与备货单/小票同口径：只数 PENDING/READY（已完成的不算要备的货）
    const d = await api<{ total: number }>(
      `/api/admin/orders?pickup_date=${batchDate}&status=PENDING,READY&page=1`,
    );
    batchCount.value = d.total;
  } catch {
    /* 角标失败不影响主功能 */
  }
}

function viewBatch() {
  pickupFilter.value = batchFilterActive.value ? null : batchDate;
  load(1);
}

function clearBatchFilter() {
  pickupFilter.value = null;
  load(1);
}

function printReceipts() {
  const query = sel.value.length
    ? `ids=${sel.value.map((o) => o.id).join(",")}`
    : `pickup_date=${batchDate}`;
  window.open(`/admin/print/receipts?${query}`, "_blank");
}

function selectable(row: AdminOrder) {
  return row.status === "PENDING" || row.status === "READY"; // READY 也可选，用于补打小票
}

async function load(p = 1) {
  page.value = p;
  const params = new URLSearchParams({ page: String(p) });
  if (status.value) params.set("status", status.value);
  if (q.value) params.set("q", q.value);
  if (pickupFilter.value) params.set("pickup_date", pickupFilter.value);
  if (range.value?.[0]) {
    params.set("date_from", range.value[0]);
    params.set("date_to", range.value[1]);
  }
  loading.value = true;
  try {
    const d = await api<{ items: AdminOrder[]; total: number }>(`/api/admin/orders?${params}`);
    items.value = d.items;
    total.value = d.total;
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "加载失败");
  } finally {
    loading.value = false;
  }
}

async function batchReady() {
  try {
    await ElMessageBox.confirm(
      `确定将选中的 ${sel.value.length} 个订单标记为备货完成吗？教职工将收到取货码可取状态。`,
      "批量备货完成",
      { confirmButtonText: "确定", cancelButtonText: "再想想", type: "warning" },
    );
  } catch {
    return; // 用户放弃
  }
  readying.value = true;
  try {
    const r = await api<{ updated: number; failed: { id: number; detail: string }[] }>(
      "/api/admin/orders/ready",
      { method: "POST", body: JSON.stringify({ ids: sel.value.map((o) => o.id) }) },
    );
    if (r.failed.length) {
      ElMessage.warning(
        `备货完成 ${r.updated} 单，失败 ${r.failed.length} 单（${r.failed[0].detail}）`,
      );
    } else {
      ElMessage.success(`备货完成 ${r.updated} 单`);
    }
    load(page.value);
    loadBatchCount();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "操作失败");
  } finally {
    readying.value = false;
  }
}

async function cancel(row: AdminOrder) {
  let reason: string;
  try {
    const { value } = await ElMessageBox.prompt(
      `确定代取消订单 ${row.order_no} 吗？原因将展示给教职工。`,
      "代取消订单",
      {
        inputPlaceholder: "取消原因（必填）",
        inputValidator: (v: string) => !!v?.trim() || "请填写原因",
        confirmButtonText: "确定取消",
        cancelButtonText: "返回",
        type: "warning",
      },
    );
    reason = value.trim();
  } catch {
    return; // 用户放弃
  }
  try {
    await api(`/api/admin/orders/${row.id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    ElMessage.success("已取消");
    load(page.value);
    loadBatchCount();
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "取消失败");
  }
}

onMounted(() => {
  load(1);
  loadBatchCount();
});
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
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.spacer {
  flex: 1;
}
.empid {
  color: var(--sc-sub);
  font-size: 12px;
}
.code {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.amount {
  font-variant-numeric: tabular-nums;
}
.pu-soon {
  color: var(--el-color-primary);
  font-weight: 600;
}
</style>
