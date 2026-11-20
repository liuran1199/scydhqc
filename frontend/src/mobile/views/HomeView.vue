<template>
  <div class="home">
    <div class="topbar">
      <div class="px-4 pt-4 flex items-baseline justify-between">
        <h1 class="text-[19px] font-bold tracking-wide">食材服务点</h1>
        <span v-if="user?.name" class="text-xs text-[var(--sc-sub)]">{{ user.name }}，你好</span>
      </div>
      <!-- 功能条：老师进页第一眼最关心的"现在下单什么时候拿" -->
      <div class="px-4 pt-2 pb-3">
        <span class="info-strip">
          <span class="dot" aria-hidden="true"></span>
          今天 {{ cutoffHour }}:00 前下单，一般次日可取
          <span class="mx-1 opacity-40">·</span>
          休息日顺延，备好后自提
        </span>
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
      <!-- 首屏骨架：空白闪一下换成与卡片同构的微光占位 -->
      <template v-if="firstLoading">
        <div v-for="i in 4" :key="i" class="sk-card">
          <div class="sk sk-thumb"></div>
          <div class="flex-1 pt-1">
            <div class="sk sk-line w-3/5"></div>
            <div class="sk sk-line w-2/5 mt-2.5"></div>
          </div>
        </div>
      </template>
      <van-list
        v-show="!firstLoading"
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
          :cat="catName(p.category_id)"
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
import { computed, onMounted, ref } from "vue";
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
  category_id?: number;
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
const cutoffHour = ref(16);

/** 首屏（还没有任何数据时）显示骨架屏 */
const firstLoading = computed(() => loading.value && !products.value.length && !loadError.value);
/** 分类 id → 名称：给占位图形选图标用 */
const catNameMap = computed(() => new Map(cats.value.map((c) => [c.id, c.name])));
function catName(id?: number): string | undefined {
  return id == null ? undefined : catNameMap.value.get(id);
}

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
  api<{ cutoff_hour: number }>("/api/pickup-info")
    .then((d) => (cutoffHour.value = d.cutoff_hour))
    .catch(() => {});
  // 商品首载由 van-list 挂载检查自动触发 loadMore
});
</script>

<style scoped>
.home {
  padding-bottom: 16px;
}
/* 顶部功能条：信息优先，绿色呼吸点提示"正在营业的节奏"，不做装饰横幅 */
.info-strip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--sc-primary-soft);
  color: var(--sc-primary-deep);
  font-size: 12px;
  line-height: 1.4;
}
.dot {
  position: relative;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--sc-primary);
  flex-shrink: 0;
}
.dot::after {
  content: "";
  position: absolute;
  inset: -3px;
  border-radius: 999px;
  background: var(--sc-primary);
  opacity: 0;
  animation: dot-pulse 2.6s ease-out infinite;
}
@keyframes dot-pulse {
  0% { transform: scale(0.5); opacity: 0.3; }
  70% { transform: scale(1.7); opacity: 0; }
  100% { transform: scale(1.7); opacity: 0; }
}
/* 首屏骨架：与卡片同构的微光占位 */
.sk-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--sc-card);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.sk {
  border-radius: 6px;
  background: linear-gradient(100deg, var(--sc-line) 40%, #f2f4ef 50%, var(--sc-line) 60%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.4s ease-in-out infinite;
}
.sk-thumb {
  width: 68px;
  height: 68px;
  border-radius: 10px;
  flex-shrink: 0;
}
.sk-line {
  height: 14px;
}
@keyframes sk-shimmer {
  from { background-position: 120% 0; }
  to { background-position: -80% 0; }
}
</style>
