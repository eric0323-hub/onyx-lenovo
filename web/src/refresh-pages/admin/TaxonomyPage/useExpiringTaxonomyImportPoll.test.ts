/**
 * @jest-environment jsdom
 */
import { act, renderHook } from "@testing-library/react";
import {
  isTaxonomyImportPollActive,
  useExpiringTaxonomyImportPoll,
} from "./useExpiringTaxonomyImportPoll";

describe("useExpiringTaxonomyImportPoll", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date("2026-06-06T00:00:00.000Z"));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("marks the post-upload poll as active until the timeout expires", () => {
    const { result } = renderHook(() => useExpiringTaxonomyImportPoll(1000));

    expect(result.current.queuedPollActive).toBe(false);

    act(() => {
      result.current.startQueuedPoll();
    });

    expect(result.current.queuedPollActive).toBe(true);

    act(() => {
      jest.advanceTimersByTime(999);
    });

    expect(result.current.queuedPollActive).toBe(true);

    act(() => {
      jest.advanceTimersByTime(1);
    });

    expect(result.current.queuedPollActive).toBe(false);
  });
});

describe("isTaxonomyImportPollActive", () => {
  it("treats expired and missing deadlines as inactive", () => {
    expect(isTaxonomyImportPollActive(null, 100)).toBe(false);
    expect(isTaxonomyImportPollActive(100, 100)).toBe(false);
    expect(isTaxonomyImportPollActive(101, 100)).toBe(true);
  });
});
