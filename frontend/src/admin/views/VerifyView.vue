<template>
  <div class="verify-wrap">
    <div class="card">
      <div class="hint">
        光标定位在输入框后，直接用扫码枪扫教职工的取货二维码，
        或手动输入 6 位取货码后回车
      </div>
      <el-input
        ref="inputRef"
        v-model="code"
        size="large"
        placeholder="扫码 / 输入 6 位取货码"
        @keyup.enter="lookup"
      >
        <template #prepend>取货码</template>
        <template #append>
          <el-button :loading="looking" @click="lookup">查询</el-button>
        </template>
      </el-input>
    </div>

    <el-dialog v-model="orderVisible" title="核销确认" width="460" @closed="resetInput">
      <div v-if="order" class="detail">
        <div class="code-line">
          <span class="code">{{ order.pickup_code }}</span>
          <el-tag :type="order.status === 'READY' ? 'success' : TAG[order.status] || 'danger'">
            {{ order.status_label }}
          </el-tag>
        </div>
        <div class="row">
          <span class="label">订单号</span><span>{{ order.order_no }}</span>
        </div>
        <div class="row">
          <span class="label">教职工</span>
          <span>{{ order.user?.name || "未补填" }}（{{ order.user?.empid }}）</span>
        </div>
        <el-divider class="my-3" />
        <div v-for="(i, idx) in order.items" :key="idx" class="row">
          <span>{{ i.p_name }}<span class="spec">（{{ i.p_spec }}）</span> × {{ i.qty }}{{ i.p_unit }}</span>
          <span class="num">￥{{ fmtMoney(i.subtotal) }}</span>
        </div>
        <el-divider class="my-3" />
        <div class="row total-row">
          <span>应收金额（现场收取）</span>
          <span class="total">￥{{ fmtMoney(order.total) }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="orderVisible = false">关闭</el-button>
        <el-button
          type="primary"
          size="large"
          :loading="verifying"
          :disabled="!order?.verifiable"
          @click="confirm"
        >
          确认核销
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

interface VerifyItem {
  p_name: string;
  p_spec: string;
  p_unit: string;
  qty: number;
  subtotal: number;
}
interface VerifyOrder {
  id: number;
  order_no: string;
  pickup_code: string;
  status: string;
  status_label: string;
  total: number;
  verifiable: boolean;
  items: VerifyItem[];
  user?: { empid: string; name: string | null };
}

const TAG: Record<string, "warning" | "info" | "danger"> = {
  PENDING: "warning",
  DONE: "info",
  CANCELLED: "danger",
};

const code = ref("");
const inputRef = ref<{ focus: () => void } | null>(null);
const order = ref<VerifyOrder | null>(null);
const orderVisible = ref(false);
const looking = ref(false);
const verifying = ref(false);

function resetInput() {
  code.value = "";
  nextTick(() => inputRef.value?.focus());
}

async function lookup() {
  const raw = code.value.trim();
  if (!raw) return;
  looking.value = true;
  try {
    const d = await api<{ order: VerifyOrder }>(`/api/admin/verify/${encodeURIComponent(raw)}`);
    order.value = d.order;
    orderVisible.value = true;
    if (!d.order.verifiable) {
      ElMessage.warning(
        `当前状态「${d.order.status_label}」不可核销` +
          (d.order.status === "PENDING" ? "，请先在订单管理做备货完成" : ""),
      );
    }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "查询失败");
    resetInput();
  } finally {
    looking.value = false;
  }
}

async function confirm() {
  if (!order.value) return;
  verifying.value = true;
  try {
    await api(`/api/admin/verify/${encodeURIComponent(order.value.pickup_code)}`, {
      method: "POST",
    });
    ElMessage.success(`核销成功，应收 ￥${fmtMoney(order.value.total)}`);
    orderVisible.value = false;
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "核销失败");
    orderVisible.value = false;
  } finally {
    verifying.value = false;
  }
}

onMounted(resetInput);
</script>

<style scoped>
.verify-wrap {
  max-width: 640px;
  margin: 0 auto;
}
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.hint {
  font-size: 13px;
  color: var(--sc-sub);
  margin-bottom: 12px;
  line-height: 1.7;
}
.detail {
  font-size: 14px;
  line-height: 1.6;
}
.code-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.code {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.28em;
  text-indent: 0.28em;
  font-variant-numeric: tabular-nums;
}
.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 3px 0;
}
.label {
  color: var(--sc-sub);
}
.spec {
  color: var(--sc-sub);
}
.num {
  font-variant-numeric: tabular-nums;
}
.total-row {
  font-weight: 600;
}
.total {
  font-size: 22px;
  font-weight: 700;
  color: var(--sc-price);
  font-variant-numeric: tabular-nums;
}
</style>
