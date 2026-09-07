/**
 * Tests for the number / date formatters. These helpers are pure, so
 * a couple of well-chosen inputs is enough to prevent regressions.
 */

import { describe, expect, test } from "vitest";
import {
  fmtBytes,
  fmtCompactCurrency,
  fmtInt,
  fmtPercentValue,
  fmtSigned,
  fmtSignedPercent,
} from "./format";

describe("fmtInt", () => {
  test("formats large numbers with thousand separators", () => {
    expect(fmtInt(1_234_567)).toBe("1,234,567");
  });
  test("returns em dash for null / NaN / undefined", () => {
    expect(fmtInt(null)).toBe("—");
    expect(fmtInt(undefined)).toBe("—");
    expect(fmtInt(NaN)).toBe("—");
  });
});

describe("fmtCompactCurrency", () => {
  test("scales to K / M / B", () => {
    expect(fmtCompactCurrency(950)).toBe("950");
    expect(fmtCompactCurrency(12_500)).toBe("12.5K");
    expect(fmtCompactCurrency(3_400_000)).toBe("3.40M");
    expect(fmtCompactCurrency(2_100_000_000)).toBe("2.10B");
  });

  test("attaches the requested symbol", () => {
    expect(fmtCompactCurrency(1_500_000, "$")).toBe("$1.50M");
    expect(fmtCompactCurrency(2_000, "\u20B9")).toBe("\u20B92.0K");
  });
});

describe("fmtSigned", () => {
  test("adds an explicit plus for positives, keeps native minus for negatives", () => {
    expect(fmtSigned(3.14)).toBe("+3.14");
    expect(fmtSigned(-3.14)).toBe("-3.14");
    expect(fmtSigned(0)).toBe("0");
  });
});

describe("fmtSignedPercent + fmtPercentValue", () => {
  test("signed variant prefixes positive numbers", () => {
    expect(fmtSignedPercent(12.4)).toBe("+12.4%");
    expect(fmtSignedPercent(-2.5)).toBe("-2.5%");
  });
  test("plain variant does not force a sign", () => {
    expect(fmtPercentValue(12.4)).toBe("12.4%");
    expect(fmtPercentValue(null)).toBe("—");
  });
});

describe("fmtBytes", () => {
  test("scales up through units", () => {
    expect(fmtBytes(512)).toBe("512 B");
    expect(fmtBytes(2048)).toBe("2 KB");
    expect(fmtBytes(1024 * 1024 * 5)).toBe("5 MB");
  });
});
