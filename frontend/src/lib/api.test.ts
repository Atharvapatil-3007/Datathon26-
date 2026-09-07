/**
 * Tests for the fetch client wrapper. We stub `globalThis.fetch` to
 * exercise the error-mapping logic without a running backend.
 */

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { api, ApiError } from "./api";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = vi.fn();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function jsonResponse(status: number, body: unknown, ok = status < 400) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  }) as Response & { ok: typeof ok };
}

describe("api client", () => {
  test("returns parsed JSON on 200", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse(200, [{ id: "a", original_filename: "a.csv" }]),
    );
    const rows = await api.listDatasets();
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("a");
  });

  test("wraps 404 responses in an ApiError with backend code", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse(404, {
        success: false,
        error: {
          code: "DATASET_NOT_FOUND",
          message: "no such dataset",
        },
      }),
    );

    await expect(api.getDataset("missing")).rejects.toMatchObject({
      name: "ApiError",
      code: "DATASET_NOT_FOUND",
      status: 404,
    });
  });

  test("wraps native fetch failures as NETWORK_ERROR", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new TypeError("Failed to fetch"),
    );

    try {
      await api.listDatasets();
      throw new Error("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).code).toBe("NETWORK_ERROR");
      expect((err as ApiError).status).toBe(0);
    }
  });

  test("resolves undefined for 204 No Content", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response(null, { status: 204 }),
    );
    await expect(api.deleteDataset("x")).resolves.toBeUndefined();
  });
});
