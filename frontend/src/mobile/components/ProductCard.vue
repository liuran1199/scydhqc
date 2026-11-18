<template>
  <div class="product-card" @click="$emit('open', p)">
    <div v-if="p.image" class="thumb">
      <img :src="p.image" loading="lazy" alt="" @error="imgFail = true" />
      <div v-if="imgFail" class="thumb-fallback">{{ p.name.slice(0, 1) }}</div>
    </div>
    <div v-else class="thumb">
      <div class="thumb-fallback">{{ p.name.slice(0, 1) }}</div>
    </div>
    <div class="flex-1 min-w-0">
      <router-link :to="'/m/product/' + p.id" class="block">
        <div class="font-medium text-[15px] leading-5 truncate">{{ p.name }}</div>
        <div class="mt-0.5 text-xs text-[--sc-sub] truncate">
          {{ p.spec }}<template v-if="p.spec && p.unit"> · </template>{{ p.unit }}
        </div>
      </router-link>
      <div class="mt-1.5 flex items-end justify-between">
        <div class="leading-none">
          <span class="price">￥{{ fmtMoney(p.price_sale) }}</span>
          <span
            v-if="p.price_original > p.price_sale"
            class="ml-1.5 text-xs text-[--sc-sub] line-through"
          >
            ￥{{ fmtMoney(p.price_original) }}
          </span>
        </div>
        <div class="qty-zone">
          <transition name="qty-pop">
            <div v-if="qty > 0" class="qty-left">
              <van-icon
                name="minus"
                size="22"
                color="var(--sc-primary)"
                class="add-btn"
                role="button"
                aria-label="减少数量"
                @click.stop="$emit('change', p, qty - 1)"
              />
              <span class="qty-val">{{ qty }}</span>
            </div>
          </transition>
          <van-icon
            name="add"
            size="22"
            color="var(--sc-primary)"
            class="add-btn"
            role="button"
            aria-label="加入购物车"
            @click.stop="$emit('change', p, qty + 1)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { fmtMoney } from "../../shared/format";

defineProps<{
  p: {
    id: number;
    name: string;
    spec: string;
    unit: string;
    price_sale: number;
    price_original: number;
    image?: string | null;
  };
  /** 该商品已在购物车的数量（0 时只显示 + 号） */
  qty: number;
}>();
defineEmits<{
  change: [p: { id: number }, qty: number];
  open: [p: { id: number }];
}>();

const imgFail = ref(false);
</script>

<style scoped>
.product-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--sc-card);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgb(31 41 51 / 5%);
}
.thumb {
  position: relative;
  width: 68px;
  height: 68px;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sc-primary-soft);
  color: var(--sc-primary);
  font-size: 26px;
  font-weight: 600;
}
.price {
  color: var(--sc-price);
  font-weight: 700;
  font-size: 17px;
}
.qty-zone {
  display: flex;
  align-items: center;
  position: relative; /* 收起动画以本区域为锚点，防止 − N 飞向视口右下角 */
}
.qty-left {
  display: flex;
  align-items: center;
  margin-right: 4px;
}
.qty-val {
  min-width: 20px;
  text-align: center;
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.add-btn {
  padding: 4px;
  border-radius: 999px;
  background: var(--sc-primary-soft);
}
/* 数量区出现/收起的轻快过渡 */
.qty-pop-enter-active,
.qty-pop-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}
.qty-pop-enter-from,
.qty-pop-leave-to {
  opacity: 0;
  transform: translateX(10px) scale(0.7);
}
.qty-pop-leave-active {
  position: absolute;
  right: 38px;
  bottom: 0;
}
</style>
