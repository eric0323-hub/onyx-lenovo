import { useCallback, useEffect, useState } from "react";

export const TAXONOMY_IMPORT_POST_UPLOAD_POLL_MS = 60_000;

export function isTaxonomyImportPollActive(
  queuedPollUntil: number | null,
  now: number
) {
  return queuedPollUntil !== null && now < queuedPollUntil;
}

export function useExpiringTaxonomyImportPoll(
  pollWindowMs = TAXONOMY_IMPORT_POST_UPLOAD_POLL_MS
) {
  const [queuedPollUntil, setQueuedPollUntil] = useState<number | null>(null);
  const queuedPollActive = isTaxonomyImportPollActive(
    queuedPollUntil,
    Date.now()
  );

  useEffect(() => {
    if (queuedPollUntil === null) {
      return;
    }

    const remainingMs = queuedPollUntil - Date.now();
    if (remainingMs <= 0) {
      setQueuedPollUntil(null);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setQueuedPollUntil(null);
    }, remainingMs);

    return () => window.clearTimeout(timeoutId);
  }, [queuedPollUntil]);

  const startQueuedPoll = useCallback(() => {
    setQueuedPollUntil(Date.now() + pollWindowMs);
  }, [pollWindowMs]);

  const stopQueuedPoll = useCallback(() => {
    setQueuedPollUntil(null);
  }, []);

  return {
    queuedPollActive,
    startQueuedPoll,
    stopQueuedPoll,
  };
}
