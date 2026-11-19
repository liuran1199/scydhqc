/** 金额分 → 元字符串，固定两位小数 */
export function fmtMoney(cents: number): string {
  return (cents / 100).toFixed(2);
}

/** 订单状态 → 中文标签 */
export const STATUS_LABEL: Record<string, string> = {
  PENDING: "待备货",
  READY: "备货完成/待取货",
  DONE: "已取货",
  CANCELLED: "已取消",
};

/** 16 点截单规则（与服务端一致）：16 点前下单次日取，16 点及以后隔日取 */
export function pickupDateFor(now: Date): Date {
  const cutoff = new Date(now);
  cutoff.setHours(16, 0, 0, 0);
  const d = new Date(now);
  d.setDate(d.getDate() + (now.getTime() < cutoff.getTime() ? 1 : 2));
  return d;
}

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

/** 取货日期 → 「11月21日（周六）」；空值返回空串。接受 ISO 日期串或 Date */
export function fmtPickupDate(v: string | Date | null | undefined): string {
  if (!v) return "";
  const d = typeof v === "string" ? new Date(`${v.slice(0, 10)}T00:00:00`) : v;
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}月${d.getDate()}日（${WEEKDAYS[d.getDay()]}）`;
}
