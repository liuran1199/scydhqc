<template>
  <div class="pb-32">
    <van-nav-bar title="购物车" left-arrow @click-left="router.back()" />
    <div class="p-3">
      <van-empty
        v-if="!cart.items.length"
        description="购物车是空的"
        image="search"
      >
        <van-button round type="primary" size="small" @click="router.replace('/m')">
          去逛逛
        </van-button>
      </van-empty>

      <div class="grid gap-2.5">
        <div
          v-for="i in cart.items"
          :key="i.product_id"
          class="flex items-center gap-3 p-3 card"
        >
          <div class="flex-1 min-w-0">
            <div class="font-medium text-[15px] truncate">{{ i.name }}</div>
            <div class="mt-0.5 text-xs text-[--sc-sub]">
              {{ i.spec }} · ￥{{ fmtMoney(i.price_sale) }}/{{ i.unit }}
            </div>
          </div>
          <van-stepper
            :model-value="i.qty"
            min="0"
            theme="green"
            @change="(q: number) => (q === 0 ? cart.remove(i.product_id) : cart.setQty(i.product_id, q))"
          />
        </div>
      </div>
    </div>

    <van-submit-bar
      v-if="cart.count"
      :price="cart.totalCents"
      label="合计："
      button-text="去下单"
      button-color="var(--sc-primary)"
      @submit="router.push('/m/confirm')"
    />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const cart = useCartStore();
const router = useRouter();
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
</style>
