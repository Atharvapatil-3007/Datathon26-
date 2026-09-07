/**
 * DatasetPicker: renders empty / populated / error states.
 *
 * The `api` module is fully mocked so no network I/O happens during tests.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

// The component pulls in api + format helpers via the "@" alias, so mocking
// through the same alias keeps the import graph consistent.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      listDatasets: vi.fn(),
    },
  };
});

import { api } from "@/lib/api";
import { DatasetPicker } from "./DatasetPicker";
import type { DatasetSummary } from "@/lib/types";

const mockList = api.listDatasets as unknown as ReturnType<typeof vi.fn>;

function fakeRow(overrides: Partial<DatasetSummary> = {}): DatasetSummary {
  return {
    id: "id-1",
    filename: "sample.csv",
    original_filename: "sample.csv",
    source_type: "file",
    file_format: "csv",
    mime_type: "text/csv",
    file_size: 123,
    storage_path: null,
    row_count: 42,
    column_count: 4,
    status: "validated",
    schema: null,
    metadata: null,
    warnings: [],
    errors: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    user_id: null,
    ...overrides,
  } as DatasetSummary;
}

beforeEach(() => {
  mockList.mockReset();
});

describe("DatasetPicker", () => {
  test("renders the empty state when no datasets are returned", async () => {
    mockList.mockResolvedValueOnce([]);

    render(<DatasetPicker onSelect={() => {}} label="Pick a dataset" />);

    expect(await screen.findByText(/No other datasets available/i)).toBeInTheDocument();
  });

  test("filters out the excluded dataset and lists the rest", async () => {
    mockList.mockResolvedValueOnce([
      fakeRow({ id: "me", original_filename: "mine.csv" }),
      fakeRow({ id: "other", original_filename: "other.csv" }),
    ]);

    render(
      <DatasetPicker
        excludeId="me"
        onSelect={() => {}}
        label="Pick a dataset"
      />,
    );

    expect(await screen.findByText("other.csv")).toBeInTheDocument();
    expect(screen.queryByText("mine.csv")).not.toBeInTheDocument();
  });

  test("invokes onSelect when a row is clicked", async () => {
    mockList.mockResolvedValueOnce([
      fakeRow({ id: "id-42", original_filename: "target.csv" }),
    ]);
    const onSelect = vi.fn();

    render(<DatasetPicker onSelect={onSelect} label="Pick a dataset" />);

    const button = await screen.findByRole("button", { name: /target\.csv/i });
    await userEvent.click(button);
    await waitFor(() => expect(onSelect).toHaveBeenCalledTimes(1));
    expect(onSelect.mock.calls[0][0].id).toBe("id-42");
  });
});
