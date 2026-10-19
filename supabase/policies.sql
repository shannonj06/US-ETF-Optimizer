-- Row-level security for the `portfolios` table.
--
-- RUN THIS, then verify it. Without RLS enabled, the anon key that ships in the
-- browser bundle can read and delete every row in the table, for every user.
-- The client-side `.eq("user_id", ...)` filters in src/config/portfolios.js are
-- a second line of defence, not a substitute: anyone can call the REST endpoint
-- directly with the same key and omit the filter.
--
-- Apply in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.
-- Safe to run more than once.

-- ---------------------------------------------------------------------------
-- 1. Shape
-- ---------------------------------------------------------------------------
-- Every row must record its owner, and that owner must be the authenticated
-- user. A nullable user_id would let a row exist that no policy can match -
-- invisible to its creator and deletable by nobody.

alter table public.portfolios
  alter column user_id set not null;

-- Deleting an account should take its portfolios with it.
do $$
begin
  if not exists (
    select 1 from information_schema.table_constraints
    where constraint_name = 'portfolios_user_id_fkey'
      and table_name = 'portfolios'
  ) then
    alter table public.portfolios
      add constraint portfolios_user_id_fkey
      foreign key (user_id) references auth.users (id) on delete cascade;
  end if;
end $$;

-- The list query filters and orders by these.
create index if not exists portfolios_user_id_created_at_idx
  on public.portfolios (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 2. Enable RLS
-- ---------------------------------------------------------------------------
-- Until this runs, every policy below is inert.
alter table public.portfolios enable row level security;

-- Applies the policies to the table owner too, so a mistake is not masked by
-- whichever role happens to run a query.
alter table public.portfolios force row level security;

-- ---------------------------------------------------------------------------
-- 3. Policies: a user sees and changes only their own rows
-- ---------------------------------------------------------------------------
drop policy if exists "Users read their own portfolios" on public.portfolios;
create policy "Users read their own portfolios"
  on public.portfolios
  for select
  to authenticated
  using ((select auth.uid()) = user_id);

-- WITH CHECK on insert stops a client from writing a row owned by someone else.
drop policy if exists "Users create their own portfolios" on public.portfolios;
create policy "Users create their own portfolios"
  on public.portfolios
  for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

-- USING picks the rows that may be updated; WITH CHECK stops an update from
-- reassigning a row to a different owner.
drop policy if exists "Users update their own portfolios" on public.portfolios;
create policy "Users update their own portfolios"
  on public.portfolios
  for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users delete their own portfolios" on public.portfolios;
create policy "Users delete their own portfolios"
  on public.portfolios
  for delete
  to authenticated
  using ((select auth.uid()) = user_id);

-- No policy grants the `anon` role anything, so a signed-out caller holding the
-- publishable key sees an empty table.

-- ---------------------------------------------------------------------------
-- 4. Verify
-- ---------------------------------------------------------------------------
-- rls_enabled must be true and four policies must be listed. If rls_enabled is
-- false, nothing above is in force.

select relname as table_name,
       relrowsecurity as rls_enabled,
       relforcerowsecurity as rls_forced
from pg_class
where oid = 'public.portfolios'::regclass;

select policyname, cmd, roles
from pg_policies
where schemaname = 'public' and tablename = 'portfolios'
order by cmd, policyname;

-- Finally, confirm it end to end in the app: sign in as one user, save a
-- portfolio, then sign in as a second user and open Saved Portfolios. The
-- second user must see none of the first user's rows.
