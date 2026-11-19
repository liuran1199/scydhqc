<template>
  <div class="verify-page">
    <!-- 输入态：6 位取货码 -->
    <template v-if="phase === 'input'">
      <div class="head">
        <h1>取货核销</h1>
        <p>输入老师出示的 6 位取货码</p>
      </div>
      <div class="code-box" @click="showKb = true">
        <span
          v-for="i in 6"
          :key="i"
          class="cell"
          :class="{ filled: i <= code.length, cursor: i === code.length + 1 && showKb }"
        >{{ code[i - 1] || "" }}</span>
      </div>
      <p v-if="searching" class="feedback">查询中…</p>
      <van-number-keyboard
        v-model="code"
        :show="showKb"
        :maxlength="6"
        hide-extra-key
        close-button-text="收起"
        safe-area-inset-bottom
        @blur="showKb = false"
      />
    </template>

    <!-- 订单态：核对后核销 -->
    <template v-else-if="phase === 'order' && order">
      <div class="card">
        <div class="o-code">{{ order.pickup_code }}</div>
        <div class="o-who">
          {{ order.user?.name || "未补填" }}<span>（{{ order.user?.empid }}）</span>
        </div>
        <div class="o-items">
          <div v-for="(i, idx) in order.items" :key="idx" class="o-item">
            <span>{{ i.p_name }}<template v-if="i.p_spec">（{{ i.p_spec }}）</template></span>
            <span>× {{ i.qty }}{{ i.p_unit }}</span>
          </div>
        </div>
        <div class="o-total">合计 <b>￥{{ fmtMoney(order.total) }}</b><i>（取货时支付）</i></div>
        <div v-if="order.status === 'PENDING'" class="o-warn">该单还未标记备货完成，核销即完成取货</div>
      </div>

      <van-button
        v-if="order.status === 'PENDING' || order.status === 'READY'"
        block
        round
        type="primary"
        class="action"
        :loading="completing"
        loading-text="核销中…"
        @click="complete"
      >
        确认取货，核销完成
      </van-button>
      <van-notice-bar v-else-if="order.status === 'DONE'" left-icon="info-o" text="该订单已核销过，无需重复操作" />
      <van-notice-bar v-else left-icon="warning-o" text="该订单已取消，不能核销" />

      <van-button v-if="canComplete" block plain class="action-2" @click="reset">返回重输</van-button>
      <van-button v-else block round type="primary" class="action" @click="reset">继续核销下一单</van-button>
    </template>

    <!-- 成功态 -->
    <template v-else-if="phase === 'done' && order">
      <div class="done">
        <div class="done-icon">✓</div>
        <div class="done-text">已核销取货</div>
        <div class="done-sub">{{ order.order_no }} · ￥{{ fmtMoney(order.total) }}</div>
        <van-button block round type="primary" class="action" @click="reset">继续核销下一单</van-button>
      </div>
    </template>

    <!-- 引导态：非管理员（老师扫了自己的码） -->
    <template v-else-if="phase === 'guest'">
      <div class="guest">
        <div class="guest-icon"><van-icon name="shop-o" /></div>
        <h2>这是取货核销页面</h2>
        <p>
          由食堂工作人员使用。老师无需操作——取货时在窗口出示订单里的
          <b>取货码</b> 或二维码，工作人员核对后即可取货。
        </p>
        <van-button block plain round type="primary" class="g-btn" @click="goLogin">
          我是工作人员，去登录
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { showFailToast } from "vant";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";
import { useAdminStore } from "../../stores/admin";

interface VerifyOrder {
  id: number;
  order_no: string;
  status: string;
  total: number;
  pickup_code: string;
  items: { p_name: string; p_spec: string; p_unit: string; qty: number }[];
  user?: { empid: string; name: string | null };
}

type Phase = "input" | "order" | "done" | "guest";
const route = useRoute();
const router = useRouter();
const phase = ref<Phase>("input");
const code = ref("");
const showKb = ref(true);
const searching = ref(false);
const completing = ref(false);
const order = ref<VerifyOrder | null>(null);
const canComplete = computed(() => order.value?.status === "PENDING" || order.value?.status === "READY");

// 输满 6 位自动查单
watch(code, async (v) => {
  if (v.length !== 6 || searching.value) return;
  searching.value = true;
  showKb.value = false;
  try {
    order.value = await api<VerifyOrder>(`/api/admin/orders/by-code/${v}`);
    phase.value = "order";
  } catch (e) {
    showFailToast(e instanceof Error ? e.message : "查询失败");
    code.value = ""; // 清空重输
    showKb.value = true;
  } finally {
    searching.value = false;
  }
});

// 扫码落地：非管理员先看引导页（老师扫了自己的码）；管理员带 code 直接进订单态
onMounted(async () => {
  const adminStore = useAdminStore();
  if (!adminStore.checked) await adminStore.fetch();
  if (!adminStore.admin) {
    phase.value = "guest";
    return;
  }
  const c = typeof route.query.code === "string" ? route.query.code.replace(/\D/g, "").slice(0, 6) : "";
  if (c.length === 6) {
    code.value = c; // 触发 watch 查单
  }
});

// 工作人员从引导页去登录，登录完带回原地址（含取货码）
function goLogin() {
  router.push({ path: "/admin/login", query: { redirect: route.fullPath } });
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
    showFailToast(e instanceof Error ? e.message : "核销失败");
  } finally {
    completing.value = false;
  }
}

function reset() {
  code.value = "";
  order.value = null;
  phase.value = "input";
  showKb.value = true;
}
</script>

<style scoped>
.verify-page {
  min-height: 100vh;
  max-width: 480px;
  margin: 0 auto;
  padding: 48px 20px 24px;
  background: var(--sc-bg, #f5f6f7);
  display: flex;
  flex-direction: column;
}
.head {
  text-align: center;
  margin-bottom: 28px;
}
.head h1 {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.head p {
  margin-top: 6px;
  font-size: 13px;
  color: var(--sc-sub, #8a9199);
}

/* ── 6 格取货码 ── */
.code-box {
  display: flex;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.cell {
  width: 46px;
  height: 56px;
  border-bottom: 2px solid #d3d8dd;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.cell.filled {
  border-color: var(--sc-ink, #2b333d);
}
.cell.cursor {
  border-color: var(--el-color-primary, #1f7a4d);
  animation: blink 1.1s step-end infinite;
}
.feedback {
  text-align: center;
  margin-top: 18px;
  font-size: 13px;
  color: var(--sc-sub, #8a9199);
}
@keyframes blink {
  50% { border-color: #d3d8dd; }
}

/* ── 订单卡 ── */
.card {
  background: var(--sc-card, #fff);
  border-radius: 14px;
  padding: 22px 20px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 6%);
}
.o-code {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: 0.22em;
  padding-left: 0.22em;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.o-who {
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  padding: 6px 0 12px;
  border-bottom: 1px solid var(--sc-line, #eceff2);
}
.o-who span {
  font-size: 12px;
  color: var(--sc-sub, #8a9199);
  font-weight: 400;
}
.o-items {
  padding: 8px 0;
}
.o-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  line-height: 1.9;
}
.o-total {
  border-top: 1px solid var(--sc-line, #eceff2);
  padding-top: 10px;
  font-size: 14px;
  display: flex;
  justify-content: flex-end;
  align-items: baseline;
  gap: 4px;
}
.o-total b {
  font-size: 18px;
  color: var(--sc-price, #c0392b);
}
.o-total i {
  font-style: normal;
  font-size: 11px;
  color: var(--sc-sub, #8a9199);
}
.o-warn {
  margin-top: 10px;
  padding: 7px 10px;
  border-radius: 6px;
  background: #fdf6ec;
  color: #b06000;
  font-size: 12px;
  text-align: center;
}
.action {
  margin-top: 20px;
}
.action-2 {
  margin-top: 10px;
}

/* ── 成功态 ── */
.done {
  text-align: center;
  padding-top: 10vh;
}
.done-icon {
  width: 84px;
  height: 84px;
  margin: 0 auto 18px;
  border-radius: 50%;
  background: var(--el-color-primary, #1f7a4d);
  color: #fff;
  font-size: 44px;
  line-height: 84px;
  font-weight: 700;
}
.done-text {
  font-size: 20px;
  font-weight: 700;
}
.done-sub {
  margin: 8px 0 36px;
  font-size: 13px;
  color: var(--sc-sub, #8a9199);
  font-variant-numeric: tabular-nums;
}

/* ── 引导态（非管理员） ── */
.guest {
  text-align: center;
  padding: 14vh 16px 0;
}
.guest-icon {
  width: 84px;
  height: 84px;
  margin: 0 auto 18px;
  border-radius: 50%;
  background: #eef3f0;
  color: var(--el-color-primary, #1f7a4d);
  font-size: 40px;
  line-height: 84px;
}
.guest h2 {
  font-size: 19px;
  font-weight: 700;
}
.guest p {
  margin: 12px 0 40px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--sc-sub, #8a9199);
}
.guest p b {
  color: var(--sc-ink, #2b333d);
}
.g-btn {
  max-width: 280px;
  margin: 0 auto;
}
</style>
