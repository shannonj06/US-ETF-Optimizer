// Session-scoped hand-off + persistence for the Cash Analysis page.
//
// Holdings are stored in a single canonical shape everywhere:
//   { ticker: string, weight: number }   where `weight` is a PERCENT (0–100).
// The optimizer / input-portfolio pages store fractions (summing to 1); the
// helpers below convert on the way in so the Cash Analysis editor always speaks
// percent, and it converts back to fractions when calling the API.
//
// sessionStorage (not localStorage) so the hand-off lives for the browsing
// session and clears when the tab closes — matching "persist while navigating
// between sections during the same session."

const KEY_INPUT = "ca.currentInputPortfolio";
const KEY_OPTIMIZED = "ca.latestOptimizedPortfolio";
const KEY_STATE = "ca.analysisState";

function read(key) {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full / unavailable — hand-off is best-effort */
  }
}

// Normalize an arbitrary list of {ticker/ETF, weight/Weight} rows to canonical
// percent holdings. `assumeFraction` scales fraction weights (0–1) to percent.
export function toCanonicalHoldings(rows, { assumeFraction = true } = {}) {
  if (!Array.isArray(rows)) return [];
  const out = [];
  for (const r of rows) {
    const ticker = String(r.ticker ?? r.ETF ?? r.symbol ?? "").trim().toUpperCase();
    if (!ticker) continue;
    let w = Number(r.weight ?? r.Weight ?? r.weightPct ?? 0);
    if (Number.isNaN(w)) w = 0;
    if (assumeFraction && w <= 1.5) w = w * 100; // fraction -> percent
    out.push({ ticker, weight: Number(w.toFixed(4)) });
  }
  return out;
}

// The portfolio currently entered on the "Use ETFs" input page.
export function setCurrentInputPortfolio(holdings) {
  write(KEY_INPUT, { holdings, savedAt: Date.now() });
}
export function getCurrentInputPortfolio() {
  return read(KEY_INPUT)?.holdings ?? null;
}

// The most recently generated optimizer portfolio (a chosen method's weights).
export function setLatestOptimizedPortfolio(holdings, meta = {}) {
  write(KEY_OPTIMIZED, { holdings, meta, savedAt: Date.now() });
}
export function getLatestOptimizedPortfolio() {
  return read(KEY_OPTIMIZED);
}

// Full Cash Analysis form state (source + editor rows + settings) so it survives
// navigation. Deliberately does NOT store the (large) analysis result.
export function saveAnalysisState(state) {
  write(KEY_STATE, state);
}
export function loadAnalysisState() {
  return read(KEY_STATE);
}

// Pull holdings out of a saved-portfolio record (Supabase row) of either type.
export function holdingsFromSavedPortfolio(record) {
  if (!record) return [];
  const results = record.results || {};
  if (record.type === "evaluate" && Array.isArray(results.weights)) {
    return toCanonicalHoldings(results.weights);
  }
  if (record.type === "optimize" && results.methods) {
    const method = results.methods.cvxpy || results.methods.slsqp || results.methods.hrp;
    if (method && Array.isArray(method.weights)) {
      return toCanonicalHoldings(method.weights);
    }
  }
  // Fallback: inputs.etfs (custom builder saved shape).
  if (record.inputs && Array.isArray(record.inputs.etfs)) {
    return toCanonicalHoldings(record.inputs.etfs);
  }
  return [];
}
