/**
 * Local-storage helpers used by the AI Assistant.
 *
 * The assistant is rule-based — it produces answers by reading from the
 * most recently completed analysis result. We stash the minimum context
 * needed here so the assistant works even after a full page reload.
 *
 * NOTHING sensitive is stored — just IDs, display names and structured
 * analysis output already visible to the user in the UI.
 */

import type { AnalysisMode, AnalysisResult } from "./types";

const K_DATASET_ID = "finsight.last_dataset_id";
const K_DATASET_NAME = "finsight.last_dataset_name";
const K_ANALYSIS_MODE = "finsight.last_analysis_mode";
const K_ANALYSIS_RESULT = "finsight.last_analysis_result";

/* -------------------------------------------------------------------------
 * Dataset tracking
 * ------------------------------------------------------------------------- */
export function rememberDataset(id: string, displayName?: string) {
  try {
    window.localStorage.setItem(K_DATASET_ID, id);
    if (displayName) window.localStorage.setItem(K_DATASET_NAME, displayName);
  } catch {
    // localStorage may be unavailable in private mode — silently ignore.
  }
}

export function getLastDatasetId(): string | null {
  try {
    return window.localStorage.getItem(K_DATASET_ID);
  } catch {
    return null;
  }
}

export function getLastDatasetName(): string | null {
  try {
    return window.localStorage.getItem(K_DATASET_NAME);
  } catch {
    return null;
  }
}

/* -------------------------------------------------------------------------
 * Analysis result tracking (per-session, small enough to cache locally)
 * ------------------------------------------------------------------------- */
export function rememberAnalysis(mode: AnalysisMode, result: AnalysisResult) {
  try {
    window.localStorage.setItem(K_ANALYSIS_MODE, mode);
    window.localStorage.setItem(K_ANALYSIS_RESULT, JSON.stringify(result));
  } catch {
    // Silently ignore quota / disabled storage.
  }
}

export function getLastAnalysisMode(): AnalysisMode | null {
  try {
    const v = window.localStorage.getItem(K_ANALYSIS_MODE) as AnalysisMode | null;
    return v ?? null;
  } catch {
    return null;
  }
}

export function getLastAnalysisResult(): AnalysisResult | null {
  try {
    const raw = window.localStorage.getItem(K_ANALYSIS_RESULT);
    if (!raw) return null;
    return JSON.parse(raw) as AnalysisResult;
  } catch {
    return null;
  }
}

export function clearAssistantContext() {
  try {
    window.localStorage.removeItem(K_DATASET_ID);
    window.localStorage.removeItem(K_DATASET_NAME);
    window.localStorage.removeItem(K_ANALYSIS_MODE);
    window.localStorage.removeItem(K_ANALYSIS_RESULT);
  } catch {
    /* ignore */
  }
}
