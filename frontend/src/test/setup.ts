/**
 * Vitest bootstrap.
 *
 * Loads @testing-library/jest-dom matchers (toBeInTheDocument, etc.) and
 * runs a jsdom polyfill for browser APIs the UI code touches. Executed
 * before every test file via `vitest.config.ts::setupFiles`.
 */

import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount React components between tests so DOM assertions stay isolated.
afterEach(() => {
  cleanup();
});

// jsdom doesn't ship a ResizeObserver — some Recharts / RTL utilities poke it.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
