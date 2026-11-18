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
