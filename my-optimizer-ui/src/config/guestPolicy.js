// What a signed-out visitor can do, mirrored from backend/guest_policy.py.
//
// This copy exists so the UI can disable a control *before* someone spends
// their single run finding out it was refused. It is not the enforcement -
// the server applies the same limits to every request, whatever the client
// believes. When you change a limit, change it in both files.

export const GUEST_QUOTAS = {
  optimize: 1,       // develop one portfolio, with the inputs locked to defaults
  evaluate: 1,       // evaluate one portfolio you already hold
  cash_analysis: 1,  // one historical what-if
};

// One developed + one evaluated.
export const GUEST_MAX_PORTFOLIOS =
  GUEST_QUOTAS.optimize + GUEST_QUOTAS.evaluate;

export const GUEST_ALLOWED_MARKETS = ["US"];
export const GUEST_MAX_HOLDINGS = 5;
export const GUEST_MAX_INITIAL_CASH = 100000;
export const GUEST_MAX_HISTORY_YEARS = 5;
export const GUEST_LOCKS_ADVANCED_INPUTS = true;

/** Earliest start date a guest may analyze, as YYYY-MM-DD. */
export function guestEarliestStartDate(today = new Date()) {
  const earliest = new Date(today);
  earliest.setFullYear(earliest.getFullYear() - GUEST_MAX_HISTORY_YEARS);
  // Keep a day of headroom so a rounding difference against the server's
  // 365-day-per-year arithmetic can't reject a date the UI just offered.
  earliest.setDate(earliest.getDate() + 2);
  return earliest.toISOString().slice(0, 10);
}

export const GUEST_LIMIT_SUMMARY = [
  "Develop 1 portfolio, using a style's recommended settings",
  "Evaluate 1 portfolio you already hold (up to 5 ETFs)",
  "Run 1 cash analysis",
];

/** Copy for the sign-up prompt shown when an allowance runs out. */
export const UPGRADE_PROMPT =
  "Create a free account to keep going - unlimited runs, full control over the " +
  "screening and optimizer inputs, the Canadian universe, and saved portfolios.";
