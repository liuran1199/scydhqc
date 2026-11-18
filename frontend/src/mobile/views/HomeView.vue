<template>
  <div class="home">
    <div class="topbar">
      <div class="px-4 pt-4 pb-2 flex items-baseline justify-between">
        <div>
          <h1 class="text-[19px] font-bold tracking-wide">食材服务点</h1>
          <p class="mt-0.5 text-xs text-[--sc-sub]">线上预订 · 备好后自提 · 现场支付</p>
        </div>
        <span v-if="user?.name" class="text-xs text-[--sc-sub]">{{ user.name }}，你好</span>
      </div>
    </div>

    <div class="sticky top-0 z-10 bg-[--sc-bg]/95 backdrop-blur">
      <div class="flex items-center px-3 pt-2">
        <van-search
          v-model="q"
          class="flex-1 !p-1"
          placeholder="搜索食材名称"
          shape="round"
          @search="load(1)"
          @clear="load(1)"
        />
        <button class="cart-entry" aria-label="购物车" @click="router.push('/m/cart')">
          <van-badge :content="cart.count || ''" :show-zero="false">
            <van-icon name="cart-o" size="22" />
          </van-badge>
        </button>
      </div>
      <van-tabs v-model:active="activeCat" shrink line-width="20px" @change="load(1)">
        <van-tab title="全部" :name="0" />
        <van-tab v-for="c in cats" :key="c.id" :title="c.name" :name="c.id" />
      </van-tabs>
    </div>

    <div class="p-3 grid grid-cols-1 gap-2.5">
      <ProductCard v-for="p in products" :key="p.id" :p="p" @add="onAdd" />
      <van-empty v-if="!loading && !products.length" description="没有找到相关食材" />
      <div v-if="loading" class="py-10 text-center">
        <van-loading color="var(--sc-primary)">加载中…</van-loading>
      </div>
    </div>

    <div v-if="total > products.length" class="pb-4 text-center text-xs text-[--sc-sub]">
      已显示 {{ products.length }} / {{ total }} 件，搜索可精确查找
    </div>
    <div v-else-if="total" class="pb-4 text-center text-xs text-[--sc-sub]">
      共 {{ total }} 件商品
    </div>

    <van-dialog
      v-model:show="cartShow"
      title="购物车"
      show-cancel-button
      cancel-button-text="继续逛"
      confirm-button-text="去下单"
      :before-close="onCartClose"
    >
      <div class="max-h-[50vh] overflow-y-auto px-4 py-2">
        <div
          v-for="it in cart.items"
          :key="it.product_id"
          class="flex items-center gap-2 py-2.5 border-b border-[--sc-line] last:border-0"
        >
          <div class="flex-1 min-w-0">
            <div class="text-sm truncate">{{ it.name }}</div>
            <div class="text-xs text-[--sc-sub]">{{ it.spec }} · ￥{{ fmtMoney(it.price_sale) }}/{{ it.unit }}</div>
          </div>
          <van-stepper
            :model-value="it.qty"
            min="0"
            @change="(v: number) => (v === 0 ? cart.remove(it.product_id) : cart.setQty(it.product_id, v))"
          />
        </div>
        <div v-if="!cart.items.length" class="py-6 text-center text-sm text-[--sc-sub]">购物车是空的</div>
      </div>
      <div class="px-4 pb-3 text-right text-sm">
        合计 <span class="price">￥{{ fmtMoney(cart.totalCents) }}</span>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { showToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { useUserStore } from "../../stores/user";
import { fmtMoney } from "../../shared/format";
import ProductCard from "../components/ProductCard.vue";

defineOptions({ name: "HomeView" });

const router = useRouter();

interface ProductRow {
  id: number;
  name: string;
  spec: string;
  unit: string;
  price_sale: number;
  price_original: number;
  image?: string | null;
}

const q = ref("");
const activeCat = ref(0);
const cats = ref<{ id: number; name: string }[]>([]);
const products = ref<ProductRow[]>([]);
const total = ref(0);
const loading = ref(false);
const cartShow = ref(false);
const cart = useCartStore();
const userStore = useUserStore();
const user = userStore.user;

function load(page = 1) {
  const params = new URLSearchParams({ page: String(page) });
  if (q.value) params.set("q", q.value);
  if (activeCat.value) params.set("category_id", String(activeCat.value));
  loading.value = true;
  api<{ items: ProductRow[]; total: number }>(`/api/products?${params}`)
    .then((d) => {
      products.value = d.items;
      total.value = d.total;
    })
    .catch((e: Error) => showToast(e.message))
    .finally(() => (loading.value = false));
}

function onAdd(p: ProductRow) {
  cart.add(p);
  showToast(`已加入购物车（共 ${cart.count} 件）`);
}

function onCartClose(action: string) {
  if (action === "confirm") {
    router.push("/m/cart");
    return false;
  }
  return true;
}

onMounted(async () => {
  try {
    cats.value = await api<{ id: number; name: string }[]>("/api/categories");
  } catch {
    /* 分类失败不阻塞商品列表 */
  }
  load(1);
});
</script>

<style scoped>
.home {
  padding-bottom: 16px;
}
.price {
  color: var(--sc-price);
  font-weight: 700;
}
.cart-entry {
  padding: 6px 4px 6px 8px;
  color: var(--sc-ink);
  background: none;
  border: 0;
}
</style>
