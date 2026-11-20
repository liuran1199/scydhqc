<template>
  <div class="pb-16">
    <van-nav-bar title="确认订单" left-arrow @click-left="router.back()" />

    <div class="p-3">
      <div class="card p-4">
        <div class="section-title">商品清单</div>
        <div
          v-for="i in cart.selectedItems"
          :key="i.product_id"
          class="flex justify-between gap-3 py-2 text-sm"
        >
          <span class="min-w-0">
            {{ i.name }}
            <span class="text-[var(--sc-sub)]">（{{ i.spec }}）</span>
            × {{ i.qty }}{{ i.unit }}
          </span>
          <span class="shrink-0">￥{{ fmtMoney(i.price_sale * i.qty) }}</span>
        </div>
        <div class="flex justify-between pt-3 mt-1 border-t border-[var(--sc-line)] font-bold">
          <span>合计</span>
          <span class="text-[var(--sc-price)]">￥{{ fmtMoney(cart.selectedCents) }}</span>
        </div>
        <p class="mt-2 text-xs text-[var(--sc-sub)]">取货时现场支付，线上不收款。</p>
      </div>

      <div class="card mt-3">
        <van-field
          v-model="remark"
          label="备注"
          placeholder="选填，其他需求请备注"
          maxlength="100"
          show-word-limit
        />
      </div>

      <p class="mt-3 px-2 text-xs leading-5 text-[var(--sc-sub)]">
        每天 {{ cutoffHour }} 点前下单，一般次日可取；遇休息日顺延，以订单状态为准。
        备货完成后到服务点出示取货码自提，现场支付。
      </p>

      <div v-if="notice" class="card mt-3 p-4">
        <div class="section-title">取货须知</div>
        <p class="mt-1 text-xs leading-6 whitespace-pre-line text-[var(--sc-sub)]">{{ notice }}</p>
      </div>

      <div class="mt-4">
        <van-button
          round
          block
          type="primary"
          :loading="submitting"
          loading-text="提交中…"
          @click="submit"
        >
          提交订单
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { showConfirmDialog, showFailToast, showToast, showSuccessToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const cart = useCartStore();
const router = useRouter();
const remark = ref("");
const submitting = ref(false);
// 截单小时以服务端为准；不再承诺具体取货日期，休息日顺延由取货须知说明
const cutoffHour = ref(16);
const notice = ref("");

onMounted(async () => {
  // 直接进本页但没勾任何商品（如手输网址）：回购物车，别让老师提交空单
  if (!cart.selectedItems.length) {
    showToast("请先勾选要结算的商品");
    router.replace("/m/cart");
  }
  try {
    const info = await api<{ cutoff_hour: number }>("/api/pickup-info");
    cutoffHour.value = info.cutoff_hour;
  } catch {
    /* 取不到就用默认 16 点文案 */
  }
  try {
    const n = await api<{ content: string }>("/api/notice");
    notice.value = (n.content || "").trim();
  } catch {
    /* 须知拉不到不拦下单 */
  }
});

/** 服务端 409（加购后改价）：拉最新售价覆盖购物车，请老师核对后重新提交 */
async function resyncPricesAndConfirm() {
  try {
    const latest = await Promise.all(
      cart.selectedItems.map((i) =>
        api<{ id: number; price_sale: number }>(`/api/products/${i.product_id}`)
      )
    );
    cart.syncPrices(latest);
    showConfirmDialog({
      title: "价格已调整",
      message: "部分商品售价已更新，商品清单已按最新价格刷新，请核对后重新提交订单。",
      confirmButtonText: "知道了",
      showCancelButton: false,
    });
  } catch {
    showFailToast("获取最新价格失败，请返回重新进入本页");
  }
}

async function submit() {
  submitting.value = true;
  try {
    const order = await api<{ id: number }>("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        // price_sale 为加购时的价格快照：管理端改价后服务端 409，绝不静默按新价成交
        items: cart.selectedItems.map((i) => ({
          product_id: i.product_id,
          qty: i.qty,
          price_sale: i.price_sale,
        })),
        remark: remark.value,
      }),
    });
    cart.removeSelected(); // 只清本次结算的，未勾选的留在车里
    showSuccessToast("下单成功，备货完成后凭取货码自提");
    router.replace(`/m/order/${order.id}`);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "下单失败";
    if (msg.includes("价格已调整")) {
      await resyncPricesAndConfirm(); // 本页清单立即显示新价，重新提交即成交
      return;
    }
    showFailToast(msg); // 含"已下架请重新确认/库存不足"等服务端校验文案
    if (msg.includes("下架") || msg.includes("库存")) {
      router.replace("/m/cart");
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}
</style>
