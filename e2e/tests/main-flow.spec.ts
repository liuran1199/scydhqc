import { expect, test } from "@playwright/test";

test("主链路：登录→下单→备货→核销", async ({ page, browser }) => {
  // 教职工登录（dev 旁路）并下单
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/api/auth/dev-login?empid=E001&name=王老师");
  await page.goto("/m");
  await page.getByPlaceholder("搜索食材名称").fill("五常大米");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "加入购物车" }).first().click();
  await page.goto("/m/confirm");
  await page.getByPlaceholder("选填，如：周五下午取").fill("E2E 备注");
  await page.getByRole("button", { name: "提交订单" }).click();
  await expect(page.getByText("取货码", { exact: false }).first()).toBeVisible();

  const code = (await page.locator(".digits").first().innerText()).trim();

  // 管理员备货
  const admin = await browser.newPage();
  await admin.setViewportSize({ width: 1440, height: 900 });
  await admin.goto("/admin/login");
  await admin.getByPlaceholder("用户名").fill("admin");
  await admin.getByPlaceholder("密码").fill("admin123");
  await admin.getByRole("button", { name: "登 录" }).click();
  await admin.waitForURL("**/admin/dashboard"); // 等登录完成再跳转，避免打断登录请求
  await admin.goto("/admin/orders");
  await admin.getByPlaceholder("订单号 / 取货码 / 工号 / 姓名").fill(code);
  await admin.keyboard.press("Enter");
  await admin.locator(".el-table__row").first().locator(".el-checkbox").click();
  await admin.getByRole("button", { name: /批量备货完成/ }).click();
  await admin.getByRole("button", { name: "确定" }).click(); // 二次确认
  await expect(admin.locator(".el-message").getByText("备货完成", { exact: false })).toBeVisible();

  // 核销
  await admin.goto("/admin/verify");
  await admin.getByPlaceholder("扫码 / 输入 6 位取货码").fill(code);
  await admin.keyboard.press("Enter");
  await expect(admin.getByText("应收金额", { exact: false })).toBeVisible();
  await admin.getByRole("button", { name: "确认核销" }).click();
  await expect(admin.locator(".el-message").getByText("核销成功", { exact: false })).toBeVisible();

  // 教职工端看到已完成
  await page.goto("/m/orders");
  await page.getByRole("tab", { name: "已完成" }).click();
  const row = page.locator(".card").filter({ hasText: "五常大米" }).first();
  await expect(row).toBeVisible();
  await expect(row.locator(".st-done")).toHaveText("已完成");
  await admin.close();
});
