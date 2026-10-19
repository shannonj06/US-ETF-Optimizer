// Guest-mode UI: the "what you have left" banner and the sign-up prompt shown
// when an allowance runs out.
//
// Both render nothing for a signed-in user, so a page can drop them in
// unconditionally.

import { Link } from "react-router-dom";
import {
  GUEST_LIMIT_SUMMARY,
  UPGRADE_PROMPT,
} from "../config/guestPolicy.js";

const ACTION_LABELS = {
  optimize: "portfolio optimization",
  evaluate: "portfolio evaluation",
  cash_analysis: "cash analysis",
};

function plural(count, noun) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/**
 * A compact banner naming what the guest has left for this page's action.
 *
 * action - one of "optimize" | "evaluate" | "cash_analysis"
 */
export function GuestAllowanceBanner({ isGuest, left, action }) {
  if (!isGuest) return null;

  const remaining = left(action);
  const label = ACTION_LABELS[action] ?? "run";

  if (remaining <= 0) {
    return (
      <div className="guest-banner guest-banner-spent" role="status">
        <strong>Guest preview used.</strong>{" "}
        <span>You&rsquo;ve used your {label}. {UPGRADE_PROMPT}</span>
        <Link className="guest-cta" to="/CreateAccount">Create a free account</Link>
      </div>
    );
  }

  return (
    <div className="guest-banner" role="status">
      <strong>Guest preview.</strong>{" "}
      <span>
        {plural(remaining, label)} remaining. Settings are locked to each
        style&rsquo;s recommended values.
      </span>
      <Link className="guest-cta" to="/CreateAccount">Create a free account</Link>
    </div>
  );
}

/** Replaces the results area once the guest has nothing left for this action. */
export function GuestUpgradePrompt({ isGuest, left, action }) {
  if (!isGuest || left(action) > 0) return null;
  return (
    <div className="guest-upgrade">
      <h2>That&rsquo;s the end of the guest preview</h2>
      <p>{UPGRADE_PROMPT}</p>
      <div className="guest-upgrade-actions">
        <Link className="guest-cta" to="/CreateAccount">Create a free account</Link>
        <Link className="guest-cta-secondary" to="/Login">Sign in</Link>
      </div>
    </div>
  );
}

/** The full allowance, listed. Used on the Guest landing page. */
export function GuestLimitsList() {
  return (
    <ul className="guest-limits">
      {GUEST_LIMIT_SUMMARY.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}

/**
 * Renders an ApiError in the way its status deserves: a spent allowance gets a
 * sign-up link rather than a red error message.
 */
export function ApiErrorMessage({ error }) {
  if (!error) return null;

  const isQuota = error.isQuotaExceeded || error.status === 402;
  const isRestricted = error.isGuestRestricted || error.status === 403;

  if (isQuota || isRestricted) {
    return (
      <div className="guest-banner guest-banner-spent" role="alert">
        <span>{error.message}</span>
        <Link className="guest-cta" to="/CreateAccount">Create a free account</Link>
      </div>
    );
  }

  return (
    <p className="error-message" role="alert">
      {error.message}
    </p>
  );
}
