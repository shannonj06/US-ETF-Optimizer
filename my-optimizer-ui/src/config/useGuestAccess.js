// Live view of what the current visitor has left.
//
// The counts come from the server (GET /guest/status), not from anything the
// browser stores, because the allowance is metered per network - opening a
// private window does not grant a second preview. Pages call `refresh()` after
// a run so the banner updates without a reload.

import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { useAuth } from "./auth.js";
import { GUEST_QUOTAS } from "./guestPolicy.js";

const FULL_ALLOWANCE = { ...GUEST_QUOTAS };

export function useGuestAccess() {
  const { isGuest, loading: authLoading } = useAuth();
  const [remaining, setRemaining] = useState(FULL_ALLOWANCE);
  const [loaded, setLoaded] = useState(false);
  // Bumping this re-runs the effect; a plain `refresh()` that called setState
  // directly would cascade renders.
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    // A signed-in user is not metered, and nothing needs fetching.
    if (authLoading || !isGuest) return undefined;

    const controller = new AbortController();
    let active = true;

    api
      .guestStatus(controller.signal)
      .then((status) => {
        if (active) setRemaining(status?.remaining ?? FULL_ALLOWANCE);
      })
      .catch(() => {
        // The API being unreachable shouldn't blank the UI. Assume the full
        // allowance; the server still refuses anything over it.
        if (active) setRemaining(FULL_ALLOWANCE);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [authLoading, isGuest, reloadToken]);

  const refresh = useCallback(() => setReloadToken((n) => n + 1), []);

  /** How many of `action` are left. Infinity for a signed-in user. */
  const left = useCallback(
    (action) => (isGuest ? (remaining?.[action] ?? 0) : Infinity),
    [isGuest, remaining]
  );

  const canUse = useCallback((action) => left(action) > 0, [left]);

  return {
    isGuest,
    loading: authLoading || (isGuest && !loaded),
    remaining: isGuest ? remaining : null,
    left,
    canUse,
    refresh,
  };
}
