import { defineStore } from "pinia";

export interface CartItem {
  product_id: number;
  name: string;
  spec: string;
  unit: string;
  price_sale: number; // 分
  image?: string | null;
  qty: number;
  checked: boolean; // 购物车勾选状态：结算只算勾选项（电商惯例）
}

const KEY = "sc_cart";

function load(): CartItem[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
    // 旧数据没有 checked 字段：默认全选，避免升级后出现"购物车有货却结不了账"
    return (Array.isArray(raw) ? raw : []).map((i) => ({ ...i, checked: i.checked ?? true }));
  } catch {
    return [];
  }
}

export const useCartStore = defineStore("cart", {
  state: () => ({ items: load() }),
  getters: {
    /** 购物车总件数（底部导航角标用），与勾选无关 */
    count: (s) => s.items.reduce((a, i) => a + i.qty, 0),
    totalCents: (s) => s.items.reduce((a, i) => a + i.price_sale * i.qty, 0),
    /** 勾选的条目（确认订单页只结算这些） */
    selectedItems: (s) => s.items.filter((i) => i.checked),
    /** 勾选件数（去结算按钮文案用） */
    selectedCount: (s) => s.items.reduce((a, i) => a + (i.checked ? i.qty : 0), 0),
    selectedCents: (s) => s.items.reduce((a, i) => a + (i.checked ? i.price_sale * i.qty : 0), 0),
    /** 某商品已加数量（首页商品卡 stepper 显示用），未加过为 0 */
    qtyOf: (s) => (pid: number) => s.items.find((i) => i.product_id === pid)?.qty ?? 0,
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
      if (f) f.qty += 1; // 已在车里的只加数量，保留原勾选状态
      else
        this.items.push({
          product_id: p.id,
          name: p.name,
          spec: p.spec,
          unit: p.unit,
          price_sale: p.price_sale,
          image: p.image,
          qty: 1,
          checked: true, // 新加购默认勾选（各电商一致）
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
    setChecked(pid: number, v: boolean) {
      this.items = this.items.map((i) => (i.product_id === pid ? { ...i, checked: v } : i));
      this.save();
    },
    toggleAll(v: boolean) {
      this.items = this.items.map((i) => ({ ...i, checked: v }));
      this.save();
    },
    /** 下单成功后只清掉已结算（勾选）的条目，未勾选的留在车里 */
    removeSelected() {
      this.items = this.items.filter((i) => !i.checked);
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
