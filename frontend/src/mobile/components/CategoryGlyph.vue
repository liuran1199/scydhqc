<template>
  <div class="glyph" :style="{ background: g.bg, color: g.fg }">
    <!-- 手绘线性图标：统一 1.6 描边、圆角端点，与整体克制气质一致 -->
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
         stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path v-for="(d, i) in g.paths" :key="i" :d="d" />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

/** 分类名 → 线条图标 + 柔和底色。分类是后台可增改的，按名称关键词匹配，
 *  未命中落到中性购物篮，保证任何分类都有体面的占位。 */
const props = defineProps<{ name?: string | null }>();

interface Glyph {
  paths: string[];
  bg: string;
  fg: string;
}

const MATCHERS: [RegExp, Glyph][] = [
  // 调味酱料：一滴酱，琥珀暖色
  [/酱|调味|蘸|醋/, {
    paths: ["M12 3.5c3.2 3.9 6 6.9 6 10.2a6 6 0 1 1-12 0c0-3.3 2.8-6.3 6-10.2Z"],
    bg: "#faeee0", fg: "#bd7a3c",
  }],
  // 豆类粥料：一碗热粥，陶土色
  [/豆|粥|粉|杂粮/, {
    paths: ["M4 13h16", "M5.5 13a6.5 6.5 0 0 0 13 0",
            "M9.6 9.2c0-1.6 1.3-1.6 1.3-3.2", "M13.4 9.2c0-1.6 1.3-1.6 1.3-3.2"],
    bg: "#f3ecdf", fg: "#9c7b4f",
  }],
  // 粮油米面：麦穗，谷色
  [/粮|米|面|油/, {
    paths: ["M12 21v-8", "M12 13c-3.2 0-4.4-1.8-4.4-4.4 2.6 0 4.4 1.2 4.4 4.4Z",
            "M12 13c3.2 0 4.4-1.8 4.4-4.4-2.6 0-4.4 1.2-4.4 4.4Z",
            "M12 8.4C9.8 8.4 8.8 7 8.8 5c2 0 3.2 1 3.2 3.4Z",
            "M12 8.4c2.2 0 3.2-1.4 3.2-3.4-2 0-3.2 1-3.2 3.4Z", "M12 4.8V3"],
    bg: "#faf3d9", fg: "#b3923f",
  }],
  // 糖蜜蛋品：一枚蛋，蛋壳粉
  [/蛋|糖|蜜/, {
    paths: ["M12 3.5c3.6 0 6.5 5.6 6.5 10.3a6.5 6.5 0 0 1-13 0C5.5 9.1 8.4 3.5 12 3.5Z"],
    bg: "#f9ece5", fg: "#bd7050",
  }],
  // 香料干调：一叶香料，中性叶绿（与藏蓝主色不抢）
  [/香|椒|茴|八|桂|麻/, {
    paths: ["M5 19C5 10.5 11 5 20 4.5 20.5 13.5 15 19 5 19Z", "M5 19c3.5-4.5 7-8 12-11"],
    bg: "#edf2ee", fg: "#5b7a67",
  }],
];
const FALLBACK: Glyph = {
  paths: ["M4.5 9.5h15L18 19a2 2 0 0 1-2 1.8H8A2 2 0 0 1 6 19L4.5 9.5Z",
          "M9 9.3c0-3.6 6-3.6 6 0"],
  bg: "#eef0ec", fg: "#75808a",
};

const g = computed(() => {
  const n = props.name || "";
  return MATCHERS.find(([re]) => re.test(n))?.[1] ?? FALLBACK;
});
</script>

<style scoped>
.glyph {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.glyph svg {
  width: 34px;
  height: 34px;
}
</style>
