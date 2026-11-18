import { expect, test } from "@playwright/test";

test("取消链路：下单→用户取消→状态已取消", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/api/auth/dev-login?empid=E002&name=李老师");
  await page.goto("/m");
  await page.getByRole("button", { name: "加入购物车" }).first().click();
  await page.goto("/m/confirm");
  await page.getByRole("button", { name: "提交订单" }).click();
  await page.getByRole("button", { name: "取消订单" }).click();
  await page.getByRole("button", { name: "确认" }).click(); // Vant 默认确认文案
  await expect(page.getByText("已取消").first()).toBeVisible();
  await expect(page.getByText("取消原因", { exact: false }).first()).toBeVisible();
});
