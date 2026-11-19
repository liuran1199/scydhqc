<template>
  <div class="home">
    <div class="topbar">
      <div class="px-4 pt-4 pb-2 flex items-baseline justify-between">
        <div>
          <h1 class="text-[19px] font-bold tracking-wide">食材服务点</h1>
          <p class="mt-0.5 text-xs text-[var(--sc-sub)]">线上预订 · 备好后自提 · 现场支付</p>
        </div>
        <span v-if="user?.name" class="text-xs text-[var(--sc-sub)]">{{ user.name }}，你好</span>
      </div>
    </div>

    <div class="sticky top-0 z-10 bg-[var(--sc-bg)]/95 backdrop-blur">
      <div class="flex items-center px-3 pt-2">
        <van-search
          v-model="q"
          class="flex-1 !p-1"
          placeholder="搜索食材名称"
          shape="round"
          @search="reload"
          @clear="reload"
        />
      </div>
      <van-tabs v-model:active="activeCat" shrink line-width="20px" @change="reload">
        <van-tab title="全部" :name="0" />
        <van-tab v-for="c in cats" :key="c.id" :title="c.name" :name="c.id" />
      </van-tabs>
    </div>

    <div class="p-3 grid grid-cols-1 gap-2.5">
      <van-list
        v-model:loading="loading"
        v-model:error="loadError"
        :finished="finished"
        :finished-text="products.length ? '没有更多了' : ''"
        error-text="加载失败，点击重试"
        @load="loadMore"
      >
        <ProductCard
          v-for="p in products"
          :key="p.id"
          :p="p"
          :qty="cart.qtyOf(p.id)"
          @change="onQtyChange"
        />
      </van-list>
      <van-empty
        v-if="!loading && finished && !products.length"
        description="没有找到相关食材"
      />
    </div>

    <div v-if="total" class="pb-4 text-center text-xs text-[var(--sc-sub)]">
      共 {{ total }} 件商品
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { showToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { useUserStore } from "../../stores/user";
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
const loadError = ref(false);
const finished = ref(false);
const page = ref(0);
const cart = useCartStore();
const userStore = useUserStore();
const user = userStore.user;

/** 拉下一页并追加（van-list 滚动到底自动触发，首载也由其发起） */
let seq = 0;
async function loadMore() {
  const cur = ++seq;
  loading.value = true;
  const params = new URLSearchParams({ page: String(page.value + 1) });
  if (q.value) params.set("q", q.value);
  if (activeCat.value) params.set("category_id", String(activeCat.value));
  try {
    const d = await api<{ items: ProductRow[]; total: number }>(`/api/products?${params}`);
    if (cur !== seq) return; // 期间已切分类/重新搜索，丢弃过期响应
    total.value = d.total;
    products.value = page.value === 0 ? d.items : [...products.value, ...d.items];
    page.value += 1;
    finished.value = products.value.length >= d.total;
  } catch (e) {
    if (cur === seq) {
      loadError.value = true;
      showToast(e instanceof Error ? e.message : "加载失败");
    }
  } finally {
    if (cur === seq) loading.value = false;
  }
}

/** 搜索 / 切分类：清空重新拉第一页 */
function reload() {
  seq++; // 作废在途请求
  page.value = 0;
  products.value = [];
  total.value = 0;
  finished.value = false;
  loadError.value = false;
  loadMore();
}

function onQtyChange(p: ProductRow, qty: number) {
  if (qty <= 0) {
    cart.remove(p.id);
    return;
  }
  if (cart.qtyOf(p.id) === 0) cart.add(p); // 首次加入需要完整商品信息
  else cart.setQty(p.id, qty);
}

onMounted(async () => {
  try {
    cats.value = await api<{ id: number; name: string }[]>("/api/categories");
  } catch {
    /* 分类失败不阻塞商品列表 */
  }
  // 商品首载由 van-list 挂载检查自动触发 loadMore
});
</script>

<style scoped>
.home {
  padding-bottom: 16px;
}
</style>
