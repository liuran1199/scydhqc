<template>
  <div class="verify-desktop">
    <el-card class="box">
      <template #header>
        <div class="head">
          <span>核销取货</span>
          <span class="head-tip">输入老师出示的 6 位取货码，回车或点击查询</span>
        </div>
      </template>

      <!-- 输入态 -->
      <div v-if="phase === 'input'" class="input-row">
        <el-input
          v-model="code"
          class="code-input"
          size="large"
          maxlength="6"
          placeholder="取货码"
          autofocus
          :disabled="searching"
          @input="onInput"
          @keyup.enter="query"
        />
        <el-button size="large" type="primary" :loading="searching" @click="query">查询</el-button>
      </div>

      <!-- 订单态：核对后核销 -->
      <template v-else-if="phase === 'order' && order">
        <div class="o-top">
          <span class="o-code">{{ order.pickup_code }}</span>
          <el-tag :type="statusTagType(order.status)" size="large">{{ order.status_label }}</el-tag>
        </div>
        <div class="o-who">
          订货人：<b>{{ order.user?.name || "未补填" }}</b>
          <span class="o-empid">（{{ order.user?.empid }}）</span>
        </div>

        <el-table :data="order.items" size="default" class="o-table">
          <el-table-column label="商品" min-width="220">
            <template #default="{ row }">
              {{ row.p_name }}<template v-if="row.p_spec">（{{ row.p_spec }}）</template>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="110" align="right">
            <template #default="{ row }">× {{ row.qty }}{{ row.p_unit }}</template>
          </el-table-column>
        </el-table>

        <div class="o-total">
          合计（取货时支付）<b>￥{{ fmtMoney(order.total) }}</b>
        </div>

        <el-alert
          v-if="order.status === 'PENDING'"
          class="o-alert"
          type="warning"
          :closable="false"
          title="该单还未标记备货完成，核销即完成取货"
        />
        <el-alert
          v-else-if="order.status === 'DONE'"
          class="o-alert"
          type="info"
          :closable="false"
          title="该订单已核销过，无需重复操作"
        />
        <el-alert
          v-else-if="order.status === 'CANCELLED'"
          class="o-alert"
          type="error"
          :closable="false"
          title="该订单已取消，不能核销"
        />

        <div class="o-actions">
          <el-button
            v-if="canComplete"
            size="large"
            type="primary"
            :loading="completing"
            @click="complete"
          >
            确认取货，核销完成
          </el-button>
          <el-button size="large" @click="reset">返回重输</el-button>
        </div>
      </template>

      <!-- 成功态 -->
      <el-result
        v-else-if="phase === 'done' && order"
        icon="success"
        title="已核销取货"
        :sub-title="`${order.order_no} · ￥${fmtMoney(order.total)}`"
      >
        <template #extra>
          <el-button type="primary" size="large" @click="reset">继续核销下一单</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface VerifyOrder {
  id: number;
  order_no: string;
  status: string;
  status_label: string;
  total: number;
  pickup_code: string;
  items: { p_name: string; p_spec: string; p_unit: string; qty: number }[];
  user?: { empid: string; name: string | null };
}

type Phase = "input" | "order" | "done";
const route = useRoute();
const phase = ref<Phase>("input");
const code = ref("");
const searching = ref(false);
const completing = ref(false);
const order = ref<VerifyOrder | null>(null);
const canComplete = computed(() => ["PENDING", "READY"].includes(order.value?.status ?? ""));

function statusTagType(status: string) {
  return { PENDING: "warning", READY: "success", DONE: "info", CANCELLED: "danger" }[status] ?? "info";
}

function onInput(v: string) {
  code.value = v.replace(/\D/g, "").slice(0, 6);
  if (code.value.length === 6) query(); // 输满 6 位自动查单
}

async function query() {
  if (code.value.length !== 6 || searching.value) return;
  searching.value = true;
  try {
    order.value = await api<VerifyOrder>(`/api/admin/orders/by-code/${code.value}`);
    phase.value = "order";
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "查询失败");
  } finally {
    searching.value = false;
  }
}

async function complete() {
  if (!order.value) return;
  completing.value = true;
  try {
    order.value = await api<VerifyOrder>("/api/admin/orders/complete", {
      method: "POST",
      body: JSON.stringify({ code: order.value.pickup_code }),
    });
    phase.value = "done";
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "核销失败");
  } finally {
    completing.value = false;
  }
}

function reset() {
  code.value = "";
  order.value = null;
  phase.value = "input";
}

onMounted(() => {
  const c = typeof route.query.code === "string" ? route.query.code.replace(/\D/g, "").slice(0, 6) : "";
  if (c.length === 6) {
    code.value = c;
    query();
  }
});
</script>

<style scoped>
.verify-desktop {
  display: flex;
  justify-content: center;
  padding: 8px 0 32px;
}
.box {
  width: 640px;
  max-width: 100%;
}
.head {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.head-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: normal;
}
.input-row {
  display: flex;
  gap: 12px;
}
.code-input {
  width: 260px;
}
.code-input :deep(input) {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.35em;
  font-variant-numeric: tabular-nums;
}
.o-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.o-code {
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 0.18em;
  font-variant-numeric: tabular-nums;
}
.o-who {
  margin: 6px 0 14px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.o-who b {
  font-size: 15px;
  color: var(--el-text-color-primary);
}
.o-empid {
  font-size: 12px;
}
.o-total {
  display: flex;
  justify-content: flex-end;
  align-items: baseline;
  gap: 8px;
  padding-top: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.o-total b {
  font-size: 20px;
  color: var(--sc-price, #c0392b);
}
.o-alert {
  margin-top: 14px;
}
.o-actions {
  margin-top: 18px;
  display: flex;
  justify-content: center;
}
</style>
