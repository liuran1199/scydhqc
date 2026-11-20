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
