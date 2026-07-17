import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

// Without real values, createClient() throws at import time and takes the whole
// app down to a blank screen. Fall back to a placeholder so the app still loads;
// any actual auth/save call will then fail through its normal error-message UI.
export const supabase = createClient(
    supabaseUrl || "https://placeholder.supabase.co",
    supabaseAnonKey || "placeholder-anon-key"
);