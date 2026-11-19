<template>
  <div class="cart-page">
    <van-nav-bar title="购物车" />

    <div class="p-3">
      <van-empty v-if="!cart.items.length" description="购物车是空的" image="search">
        <van-button round type="primary" size="small" @click="router.replace('/m')">
          去逛逛
        </van-button>
      </van-empty>

      <div class="grid gap-2.5">
        <div
          v-for="i in cart.items"
          :key="i.product_id"
          class="flex items-center gap-2.5 p-3 card"
          @click="cart.setChecked(i.product_id, !i.checked)"
        >
          <van-checkbox
            :model-value="i.checked"
            checked-color="var(--sc-primary)"
            icon-size="18px"
            @update:model-value="(v: boolean) => cart.setChecked(i.product_id, v)"
            @click.stop
          />
          <img
            v-if="i.image"
            :src="i.image"
            class="thumb"
            loading="lazy"
            alt=""
            @click.stop="router.push(`/m/product/${i.product_id}`)"
          />
          <div
            v-else
            class="thumb no-img"
            @click.stop="router.push(`/m/product/${i.product_id}`)"
          >
            {{ i.name.slice(0, 1) }}
          </div>

          <div class="flex-1 min-w-0">
            <div
              class="name"
              @click.stop="router.push(`/m/product/${i.product_id}`)"
            >
              {{ i.name }}
            </div>
            <div class="mt-1.5 flex items-end justify-between gap-2">
              <div class="min-w-0">
                <div class="price">
                  ￥{{ fmtMoney(i.price_sale)
                  }}<span class="unit">/{{ i.unit }}</span>
                </div>
                <div class="spec">{{ i.spec }}</div>
              </div>
              <!-- stepper 区点击不冒泡：调数量不该误触整行勾选 -->
              <div @click.stop>
                <van-stepper
                  :model-value="i.qty"
                  min="0"
                  theme="green"
                  @change="
                    (q: number) =>
                      q === 0 ? cart.remove(i.product_id) : cart.setQty(i.product_id, q)
                  "
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 结算栏叠在底部导航上方（淘宝/京东式两段底栏），全选 + 合计只算勾选项 -->
    <van-submit-bar
      v-if="cart.items.length"
      class="checkout-bar"
      :price="cart.selectedCents"
      :disabled="!cart.selectedCount"
      :button-text="`去结算(${cart.selectedCount})`"
      button-color="var(--sc-primary)"
      @submit="checkout"
    >
      <van-checkbox
        :model-value="allChecked"
        checked-color="var(--sc-primary)"
        icon-size="18px"
        @update:model-value="(v: boolean) => cart.toggleAll(v)"
        @click.stop
      >
        全选
      </van-checkbox>
    </van-submit-bar>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { showToast } from "vant";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const cart = useCartStore();
const router = useRouter();

const allChecked = computed(
  () => cart.items.length > 0 && cart.items.every((i) => i.checked),
);

function checkout() {
  if (!cart.selectedCount) {
    showToast("请先勾选要结算的商品");
    return;
  }
  router.push("/m/confirm");
}
</script>

<style scoped>
.card {
  background: var(--sc-card);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.cart-page {
  /* 给叠在导航栏上方的结算栏留出滚动余量（导航高度由外层 mobile-wrap 补足） */
  padding-bottom: 66px;
}
.thumb {
  width: 72px;
  height: 72px;
  border-radius: 10px;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--sc-primary-soft);
}
.no-img {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sc-primary);
  font-size: 24px;
  font-weight: 600;
}
.name {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.price {
  color: var(--sc-price);
  font-weight: 600;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}
.unit {
  color: var(--sc-sub);
  font-weight: 400;
  font-size: 12px;
}
.spec {
  margin-top: 2px;
  font-size: 12px;
  color: var(--sc-sub);
}
.checkout-bar {
  /* 底部导航高 50px（ vant Tabbar 默认）+ 安全区；结算栏紧贴其上 */
  bottom: calc(50px + env(safe-area-inset-bottom));
  z-index: 2;
}
</style>
