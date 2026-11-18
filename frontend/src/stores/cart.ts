import { defineStore } from "pinia";

export interface CartItem {
  product_id: number;
  name: string;
  spec: string;
  unit: string;
  price_sale: number; // 分
  image?: string | null;
  qty: number;
}

const KEY = "sc_cart";

function load(): CartItem[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export const useCartStore = defineStore("cart", {
  state: () => ({ items: load() }),
  getters: {
    count: (s) => s.items.reduce((a, i) => a + i.qty, 0),
    totalCents: (s) => s.items.reduce((a, i) => a + i.price_sale * i.qty, 0),
  },
  actions: {
    save() {
      localStorage.setItem(KEY, JSON.stringify(this.items));
    },
    add(p: {
      id: number;
      name: string;
      spec: string;
      unit: string;
      price_sale: number;
      image?: string | null;
    }) {
      const f = this.items.find((i) => i.product_id === p.id);
      if (f) f.qty += 1;
      else
        this.items.push({
          product_id: p.id,
          name: p.name,
          spec: p.spec,
          unit: p.unit,
          price_sale: p.price_sale,
          image: p.image,
          qty: 1,
        });
      this.save();
    },
    setQty(pid: number, qty: number) {
      const q = Math.min(999, qty);
      this.items =
        q <= 0
          ? this.items.filter((i) => i.product_id !== pid)
          : this.items.map((i) => (i.product_id === pid ? { ...i, qty: q } : i));
      this.save();
    },
    remove(pid: number) {
      this.items = this.items.filter((i) => i.product_id !== pid);
      this.save();
    },
    clear() {
      this.items = [];
      this.save();
    },
    /** 管理端改价后，用最新售价覆盖购物车旧价；返回发生变化的条数 */
    syncPrices(products: { id: number; price_sale: number }[]): number {
      let changed = 0;
      this.items = this.items.map((i) => {
        const latest = products.find((p) => p.id === i.product_id);
        if (latest && latest.price_sale !== i.price_sale) {
          changed += 1;
          return { ...i, price_sale: latest.price_sale };
        }
        return i;
      });
      if (changed > 0) this.save();
      return changed;
    },
  },
});
