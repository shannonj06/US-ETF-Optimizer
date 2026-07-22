import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

/** True only when both Supabase env vars are present at build time. */
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

const NOT_CONFIGURED = {
  message:
    "Supabase is not configured. Set VITE_SUPABASE_URL and " +
    "VITE_SUPABASE_PUBLISHABLE_KEY, then rebuild.",
};

// Every stubbed call resolves to this. `data.user` is present so the
// `const { data: { user } } = await supabase.auth.getUser()` destructure in
// config/portfolios.js doesn't throw.
const STUB_RESULT = { data: { user: null }, error: NOT_CONFIGURED };

// createClient() throws when the URL/key are missing, and because this module is
// imported at startup that blanks the entire app with no console error. Fall back
// to a chainable stub so the UI always mounts and only the auth/database actions
// fail — with an explanatory message instead of a white screen.
const stubClient = new Proxy(function () {}, {
  get(_target, prop) {
    if (prop === "then") return (resolve) => resolve(STUB_RESULT);
    return stubClient;
  },
  apply() {
    return stubClient;
  },
});

if (!isSupabaseConfigured) {
  console.warn(`[supabase] ${NOT_CONFIGURED.message} Auth and saved portfolios are disabled.`);
}

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : stubClient;
