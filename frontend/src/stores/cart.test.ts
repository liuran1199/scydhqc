import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

// node 环境无 localStorage，注入内存实现
beforeAll(() => {
  const store: Record<string, string> = {};
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
    removeItem: (k: string) => {
      delete store[k];
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
  });
});

describe("cart store", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("加购与合计（分）", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    c.add(P as never);
    c.add(P as never);
    c.add({ ...P, id: 2, price_sale: 250 } as never);
    expect(c.count).toBe(3);
    expect(c.totalCents).toBe(6620 * 2 + 250);
  });

  it("改数量、删除、清空", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    c.add(P as never);
    c.setQty(1, 5);
    expect(c.totalCents).toBe(6620 * 5);
    c.setQty(1, 0); // 数量 0 视为删除
    expect(c.count).toBe(0);
    c.add(P as never);
    c.remove(1);
    expect(c.count).toBe(0);
    c.add(P as never);
    c.clear();
    expect(c.count).toBe(0);
  });

  it("qtyOf：按商品 id 查已加数量，未加过为 0（首页 stepper 用）", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    expect(c.qtyOf(1)).toBe(0); // 未加过
    c.add(P as never);
    c.add(P as never);
    expect(c.qtyOf(1)).toBe(2);
    c.remove(1);
    expect(c.qtyOf(1)).toBe(0); // 删除后回到 0
  });

  it("localStorage 持久化", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    c.add(P as never);
    const c2 = useCartStore(); // 新实例读同一 storage
    expect(c2.count).toBe(1);
  });
});

describe("cart 勾选模型（电商惯例：结算只算勾选项）", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("新加购默认勾选", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    c.add(P as never);
    expect(c.items[0].checked).toBe(true);
    expect(c.selectedCount).toBe(1);
    expect(c.selectedCents).toBe(6620);
  });

  it("取消勾选后合计与结算件数只算勾选项，总数不变", async () => {
    const { useCartStore } = await import("./cart");
    const c = useCartStore();
    c.add({ id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 } as never);
    c.add({ id: 2, name: "豆油", spec: "5L", unit: "桶", price_sale: 5000 } as never);
    c.setChecked(1, false);
    expect(c.count).toBe(2); // 购物车总数（tabbar 角标）不受勾选影响
    expect(c.selectedCount).toBe(1);
    expect(c.selectedCents).toBe(5000);
    expect(c.selectedItems.map((i) => i.product_id)).toEqual([2]);
  });

  it("全选 / 全不选", async () => {
    const { useCartStore } = await import("./cart");
    const c = useCartStore();
    c.add({ id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 } as never);
    c.add({ id: 2, name: "豆油", spec: "5L", unit: "桶", price_sale: 5000 } as never);
    c.toggleAll(false);
    expect(c.selectedCents).toBe(0);
    c.toggleAll(true);
    expect(c.selectedCents).toBe(6620 + 5000);
  });

  it("下单后 removeSelected 只清勾选项，未勾选留车", async () => {
    const { useCartStore } = await import("./cart");
    const c = useCartStore();
    c.add({ id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 } as never);
    c.add({ id: 2, name: "豆油", spec: "5L", unit: "桶", price_sale: 5000 } as never);
    c.setChecked(1, false);
    c.removeSelected();
    expect(c.items.map((i) => i.product_id)).toEqual([1]);
    expect(c.items[0].checked).toBe(false); // 留车项保持原勾选状态
  });

  it("旧版 localStorage（无 checked 字段）加载后默认全选", async () => {
    localStorage.setItem(
      "sc_cart",
      JSON.stringify([{ product_id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620, qty: 2 }]),
    );
    const { useCartStore } = await import("./cart");
    const c = useCartStore();
    expect(c.selectedCount).toBe(2);
    expect(c.selectedCents).toBe(6620 * 2);
  });
});

describe("cart syncPrices（改价后重确认，I-7）", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("用最新售价覆盖购物车旧价并持久化", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    c.add(P as never);
    const changed = c.syncPrices([{ id: 1, price_sale: 7000 }]);
    expect(changed).toBe(1);
    expect(c.items[0].price_sale).toBe(7000);
    expect(c.totalCents).toBe(7000);
    expect(localStorage.getItem("sc_cart")).toContain("7000");
  });

  it("价格未变或商品不在返回中时不动、不误报", async () => {
    const { useCartStore } = await import("./cart");
    const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };
    const c = useCartStore();
    c.add(P as never);
    expect(c.syncPrices([{ id: 1, price_sale: 6620 }, { id: 9, price_sale: 100 }])).toBe(0);
    expect(c.items[0].price_sale).toBe(6620);
  });
});
