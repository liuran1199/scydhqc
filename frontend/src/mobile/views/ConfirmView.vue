<template>
  <div class="pb-16">
    <van-nav-bar title="确认订单" left-arrow @click-left="router.back()" />

    <div class="p-3">
      <div class="card p-4">
        <div class="section-title">商品清单</div>
        <div
          v-for="i in cart.items"
          :key="i.product_id"
          class="flex justify-between gap-3 py-2 text-sm"
        >
          <span class="min-w-0">
            {{ i.name }}
            <span class="text-[--sc-sub]">（{{ i.spec }}）</span>
            × {{ i.qty }}{{ i.unit }}
          </span>
          <span class="shrink-0">￥{{ fmtMoney(i.price_sale * i.qty) }}</span>
        </div>
        <div class="flex justify-between pt-3 mt-1 border-t border-[--sc-line] font-bold">
          <span>合计</span>
          <span class="text-[--sc-price]">￥{{ fmtMoney(cart.totalCents) }}</span>
        </div>
        <p class="mt-2 text-xs text-[--sc-sub]">取货时现场支付，线上不收款。</p>
      </div>

      <div class="card mt-3">
        <van-field
          v-model="remark"
          label="备注"
          placeholder="选填，如：周五下午取"
          maxlength="100"
          show-word-limit
        />
      </div>

      <p class="mt-3 px-2 text-xs leading-5 text-[--sc-sub]">
        提交后请等待后勤备货，状态变为「待取货」即可到服务点取货，
        取货时出示取货码，现场支付。
      </p>

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
import { ref } from "vue";
import { useRouter } from "vue-router";
import { showConfirmDialog, showFailToast, showSuccessToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const cart = useCartStore();
const router = useRouter();
const remark = ref("");
const submitting = ref(false);

/** 服务端 409（加购后改价）：拉最新售价覆盖购物车，请老师核对后重新提交 */
async function resyncPricesAndConfirm() {
  try {
    const latest = await Promise.all(
      cart.items.map((i) =>
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
        items: cart.items.map((i) => ({
          product_id: i.product_id,
          qty: i.qty,
          price_sale: i.price_sale,
        })),
        remark: remark.value,
      }),
    });
    cart.clear();
    showSuccessToast("下单成功，备货完成后凭取货码到服务点自提");
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
