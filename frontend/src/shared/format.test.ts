import { describe, expect, it } from "vitest";
import { fmtMoney } from "./format";

describe("fmtMoney", () => {
  it("分转元保留两位", () => {
    expect(fmtMoney(770)).toBe("7.70");
    expect(fmtMoney(13000)).toBe("130.00");
    expect(fmtMoney(5)).toBe("0.05");
  });
});
