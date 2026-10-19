// One place that talks to the FastAPI backend.
//
// Every call went through a hand-rolled fetch before, each with its own error
// unwrapping and none of them sending the user's access token - so the API saw
// every request, signed in or not, as anonymous. This module attaches the token
// and turns the backend's error shapes into one typed error.

import { getAccessToken } from "./auth.js";

// Set VITE_API_URL in .env (and in the Vercel project settings) to point at the
// deployed API. Without it a production build calls localhost and fails for
// every visitor.
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

if (import.meta.env.PROD && !import.meta.env.VITE_API_URL) {
  console.warn(
    "[api] VITE_API_URL is not set, so this build calls http://localhost:8000. " +
      "Set it in the hosting project's environment variables and redeploy."
  );
}

/** An error carrying the HTTP status, so callers can react to 402 vs 429 vs 500. */
export class ApiError extends Error {
  constructor(message, { status, code = null, body = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.body = body;
  }

  /** The guest allowance is spent - the caller should prompt for sign-up. */
  get isQuotaExceeded() {
    return this.status === 402;
  }

  /** The input is outside what a guest may send (market, size, date range). */
  get isGuestRestricted() {
    return this.status === 403;
  }

  get isRateLimited() {
    return this.status === 429;
  }

  /** The user can fix this by changing their input. */
  get isUserFixable() {
    return this.status === 422 || this.status === 400;
  }
}

/** FastAPI returns { detail: string } or { detail: [{msg, loc}, ...] }. */
function readDetail(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null;
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .filter(Boolean)
      .join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return `Request failed (${status})`;
}

/**
 * Call the API. Resolves to the parsed JSON body, or throws an ApiError.
 *
 * Pass { auth: false } for endpoints that never need a token.
 */
export async function apiFetch(path, { method = "GET", body, auth = true, signal } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (auth) {
    const token = await getAccessToken();
    // No token means a guest request - that is a supported state, not an error.
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    if (cause?.name === "AbortError") throw cause;
    throw new ApiError(
      "Could not reach the server. Check your connection and try again.",
      { status: 0 }
    );
  }

  let parsed = null;
  try {
    parsed = await response.json();
  } catch {
    // No JSON body: a 204, or an HTML error page from a proxy. `parsed` stays
    // null and readDetail() falls back to the status code.
  }

  if (!response.ok) {
    throw new ApiError(readDetail(parsed, response.status), {
      status: response.status,
      code: response.headers.get("X-Guest-Quota-Action"),
      body: parsed,
    });
  }

  return parsed;
}

export const api = {
  guestStatus: (signal) => apiFetch("/guest/status", { signal }),
  markets: (signal) => apiFetch("/markets", { signal }),
  profiles: (signal) => apiFetch("/profiles", { signal }),
  profileDefaults: (profile, signal) =>
    apiFetch(`/profiles/${encodeURIComponent(profile)}/defaults`, { signal }),
  optimize: (payload, signal) =>
    apiFetch("/optimize", { method: "POST", body: payload, signal }),
  evaluate: (payload, signal) =>
    apiFetch("/evaluate", { method: "POST", body: payload, signal }),
  cashAnalysis: (payload, signal) =>
    apiFetch("/api/cash-analysis", { method: "POST", body: payload, signal }),
};
