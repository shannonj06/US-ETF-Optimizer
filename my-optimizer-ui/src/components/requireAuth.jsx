// Route guard for pages that need an account.
//
// Saved portfolios live in Supabase and are scoped to their owner, so there is
// nothing for a guest to see on /saved. Guarding the route means a guest gets
// an explanation and a sign-up link instead of an empty list or a row of
// permission errors.

import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../config/auth.js";

/**
 * Wraps protected routes.
 *
 * redirect - when set, guests are sent there instead of seeing the explanation.
 */
function RequireAuth({ redirect = null, children }) {
  const { isGuest, loading } = useAuth();
  const location = useLocation();

  // Render nothing until the session resolves, so a signed-in user reloading
  // the page never sees the sign-in prompt flash first.
  if (loading) return null;

  if (isGuest) {
    if (redirect) {
      return <Navigate to={redirect} replace state={{ from: location.pathname }} />;
    }
    return (
      <div className="auth-required">
        <h1>Sign in to see this</h1>
        <p>
          Saved portfolios are tied to your account, so there is nothing to show
          in guest mode. Creating an account is free and keeps everything you
          build.
        </p>
        <div className="guest-upgrade-actions">
          <Link className="guest-cta" to="/CreateAccount">Create a free account</Link>
          <Link className="guest-cta-secondary" to="/Login">Sign in</Link>
        </div>
      </div>
    );
  }

  return children ?? <Outlet />;
}

export default RequireAuth;
