// Session state, shared by every page.
//
// The app has three states, and most of the UI cares about the difference:
//   - loading    : we haven't heard back from Supabase yet
//   - signed in  : full access
//   - guest      : browsing without an account, under the limits in guestPolicy.js
//
// "Guest" is simply "no session". There is no guest token: the API recognizes a
// signed-out caller by the absence of an Authorization header and meters them
// by IP. That means the guest allowance is per browser/network, not per tab -
// clearing site data does not reset it.

import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient.js";

/** The current access token, or null when signed out. */
export async function getAccessToken() {
  try {
    const { data } = await supabase.auth.getSession();
    return data?.session?.access_token ?? null;
  } catch {
    // Supabase unconfigured (stub client) or storage blocked - treat as guest.
    return null;
  }
}

/** The signed-in user, or null. */
export async function getUser() {
  try {
    const { data } = await supabase.auth.getUser();
    return data?.user ?? null;
  } catch {
    return null;
  }
}

export async function signOut() {
  try {
    await supabase.auth.signOut();
  } catch {
    /* already signed out, or Supabase unconfigured */
  }
}

/**
 * Subscribe to the session.
 *
 * Returns { user, isGuest, loading }. `isGuest` is deliberately false while
 * loading, so a page never flashes the guest banner at a signed-in user before
 * their session resolves.
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        setUser(data?.session?.user ?? null);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
        setLoading(false);
      });

    // Keeps every open tab in step: signing in or out in one updates the rest.
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => {
      active = false;
      data?.subscription?.unsubscribe?.();
    };
  }, []);

  return { user, isGuest: !loading && !user, loading };
}
