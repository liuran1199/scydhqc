<template>
  <div v-if="p" class="pb-24">
    <van-nav-bar title="商品详情" left-arrow @click-left="router.back()" />
    <div class="p-4">
      <van-swipe
        v-if="imgs.length"
        class="rounded-xl overflow-hidden bg-[--sc-primary-soft]"
      >
        <van-swipe-item v-for="(u, i) in imgs" :key="i">
          <img
            :src="u"
            class="w-full block"
            style="aspect-ratio: 1; object-fit: cover"
            alt=""
          />
        </van-swipe-item>
        <template #indicator="{ active }">
          <div v-if="imgs.length > 1" class="swipe-counter">{{ active + 1 }}/{{ imgs.length }}</div>
        </template>
      </van-swipe>
      <div v-else class="fallback-tile rounded-xl">{{ p.name.slice(0, 1) }}</div>

      <div class="mt-4 flex items-end gap-2">
        <span class="text-[26px] leading-none font-bold text-[--sc-price]">
          ￥{{ fmtMoney(p.price_sale) }}
        </span>
        <span
          v-if="p.price_original > p.price_sale"
          class="text-sm text-[--sc-sub] line-through"
        >
          ￥{{ fmtMoney(p.price_original) }}
        </span>
      </div>

      <h3 class="mt-2 text-lg font-semibold leading-6">{{ p.name }}</h3>

      <div class="mt-3 card">
        <div class="row">
          <span class="label">规格</span><span>{{ p.spec || "—" }}</span>
        </div>
        <div class="row">
          <span class="label">单位</span><span>{{ p.unit }}</span>
        </div>
        <div v-if="p.brand" class="row">
          <span class="label">品牌</span><span>{{ p.brand }}</span>
        </div>
        <div v-if="p.origin" class="row">
          <span class="label">产地</span><span>{{ p.origin }}</span>
        </div>
      </div>

      <p class="mt-4 text-xs leading-5 text-[--sc-sub]">
        下单后由服务点备货，备货完成后可随时凭取货码到店自提，现场支付。
      </p>
    </div>

    <van-action-bar>
      <van-action-bar-icon
        icon="cart-o"
        text="购物车"
        :badge="cart.count || ''"
        :color="cart.count ? 'var(--sc-primary)' : undefined"
        @click="router.push('/m/cart')"
      />
      <van-action-bar-button type="primary" plain text="加入购物车" @click="add" />
      <van-action-bar-button type="primary" text="立即购买" @click="buy" />
    </van-action-bar>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { showSuccessToast, showToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const route = useRoute();
const router = useRouter();
const cart = useCartStore();
const p = ref<{
  id: number;
  name: string;
  spec: string;
  unit: string;
  brand?: string;
  origin?: string;
  price_sale: number;
  price_original: number;
  image?: string | null;
  images?: string[];
} | null>(null);

/** 图集：images 优先，旧数据只有封面时兜底单图 */
const imgs = computed(() =>
  p.value?.images?.length ? p.value.images : p.value?.image ? [p.value.image] : [],
);

/** 加入购物车：留在本页，角标与提示即反馈（主流电商详情页行为） */
function add() {
  if (!p.value) return;
  cart.add(p.value);
  showSuccessToast("已加入购物车");
}

/** 立即购买：本单加购后直接进入确认页 */
function buy() {
  if (!p.value) return;
  cart.add(p.value);
  router.push("/m/confirm");
}

onMounted(async () => {
  try {
    p.value = await api(`/api/products/${route.params.id}`);
  } catch (e) {
    showToast(e instanceof Error ? e.message : "加载失败");
    router.replace("/m");
  }
});
</script>

<style scoped>
.fallback-tile {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sc-primary-soft);
  color: var(--sc-primary);
  font-size: 64px;
  font-weight: 600;
}
.swipe-counter {
  position: absolute;
  right: 12px;
  bottom: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgb(0 0 0 / 45%);
  color: #fff;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.card {
  background: var(--sc-card);
  border-radius: 12px;
  padding: 4px 14px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.row {
  display: flex;
  gap: 16px;
  padding: 10px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--sc-line);
}
.row:last-child {
  border-bottom: 0;
}
.label {
  width: 3em;
  color: var(--sc-sub);
}
</style>
