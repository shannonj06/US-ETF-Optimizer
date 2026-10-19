// Saved portfolios, stored in Supabase and owned by the user who created them.
//
// Ownership is enforced in two places on purpose:
//
//  1. Row-level security in the database (see supabase/policies.sql). This is
//     the real boundary - it holds no matter what any client sends.
//  2. The explicit `.eq("user_id", ...)` filters below. RLS being switched off
//     for a table is a silent failure: the queries keep working and simply
//     start returning everyone's rows. These filters mean that a
//     misconfiguration shows up as "my list is empty", not as a data leak.
//
// Never remove the filters on the grounds that RLS already covers it.

import { supabase } from "./supabaseClient.js";

class NotSignedInError extends Error {
  constructor() {
    super("You must be signed in to save portfolios. Creating an account is free.");
    this.name = "NotSignedInError";
  }
}

async function requireUser() {
  const { data, error } = await supabase.auth.getUser();
  if (error || !data?.user) throw new NotSignedInError();
  return data.user;
}

export async function savePortfolio(name, type, inputs, results) {
  const user = await requireUser();
  const { data, error } = await supabase
    .from("portfolios")
    .insert({ name, type, inputs, results, user_id: user.id })
    .select()
    .single();
  if (error) throw error;
  return data;
}

export async function listPortfolios() {
  const user = await requireUser();
  const { data, error } = await supabase
    .from("portfolios")
    .select()
    .eq("user_id", user.id)          // belt and braces alongside RLS
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data;
}

export async function deletePortfolio(id) {
  const user = await requireUser();
  const { error } = await supabase
    .from("portfolios")
    .delete()
    .eq("id", id)
    .eq("user_id", user.id);         // a row you don't own is not yours to delete
  if (error) throw error;
}

export { NotSignedInError };
