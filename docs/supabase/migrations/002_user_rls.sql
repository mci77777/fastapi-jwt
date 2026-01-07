-- GymBro User SSOT (Supabase)
-- 002: Enable RLS + policies for user_profiles / user_settings / user_entitlements
--
-- Goal
-- - authenticated: can only SELECT/INSERT/UPDATE own rows (auth.uid() == user_id)
-- - service_role: backend can read/write all rows (for /v1/me aggregation)
-- - anonymous: disabled by default (no grants / no policies)
--
-- Notes
-- - Use (select auth.uid()) to avoid per-row auth.uid() evaluation (see docs/RLS_PERFORMANCE_OPTIMIZATION.md).

begin;

-- Enable RLS
alter table if exists public.user_profiles enable row level security;
alter table if exists public.user_settings enable row level security;
alter table if exists public.user_entitlements enable row level security;

-- Grant permissions (RLS still applies to authenticated; service_role can bypass or use policies)
grant select, insert, update on public.user_profiles to authenticated;
grant select, insert, update on public.user_settings to authenticated;
grant select, insert, update on public.user_entitlements to authenticated;

grant all on public.user_profiles to service_role;
grant all on public.user_settings to service_role;
grant all on public.user_entitlements to service_role;

-- user_profiles policies
drop policy if exists user_profiles_select_own on public.user_profiles;
drop policy if exists user_profiles_insert_own on public.user_profiles;
drop policy if exists user_profiles_update_own on public.user_profiles;
drop policy if exists user_profiles_service_all on public.user_profiles;

create policy user_profiles_select_own on public.user_profiles
  for select to authenticated
  using (user_id::text = (select auth.uid()::text));

create policy user_profiles_insert_own on public.user_profiles
  for insert to authenticated
  with check (user_id::text = (select auth.uid()::text));

create policy user_profiles_update_own on public.user_profiles
  for update to authenticated
  using (user_id::text = (select auth.uid()::text))
  with check (user_id::text = (select auth.uid()::text));

create policy user_profiles_service_all on public.user_profiles
  for all to service_role
  using (true)
  with check (true);

-- user_settings policies
drop policy if exists user_settings_select_own on public.user_settings;
drop policy if exists user_settings_insert_own on public.user_settings;
drop policy if exists user_settings_update_own on public.user_settings;
drop policy if exists user_settings_service_all on public.user_settings;

create policy user_settings_select_own on public.user_settings
  for select to authenticated
  using (user_id::text = (select auth.uid()::text));

create policy user_settings_insert_own on public.user_settings
  for insert to authenticated
  with check (user_id::text = (select auth.uid()::text));

create policy user_settings_update_own on public.user_settings
  for update to authenticated
  using (user_id::text = (select auth.uid()::text))
  with check (user_id::text = (select auth.uid()::text));

create policy user_settings_service_all on public.user_settings
  for all to service_role
  using (true)
  with check (true);

-- user_entitlements policies
drop policy if exists user_entitlements_select_own on public.user_entitlements;
drop policy if exists user_entitlements_insert_own on public.user_entitlements;
drop policy if exists user_entitlements_update_own on public.user_entitlements;
drop policy if exists user_entitlements_service_all on public.user_entitlements;

create policy user_entitlements_select_own on public.user_entitlements
  for select to authenticated
  using (user_id::text = (select auth.uid()::text));

create policy user_entitlements_insert_own on public.user_entitlements
  for insert to authenticated
  with check (user_id::text = (select auth.uid()::text));

create policy user_entitlements_update_own on public.user_entitlements
  for update to authenticated
  using (user_id::text = (select auth.uid()::text))
  with check (user_id::text = (select auth.uid()::text));

create policy user_entitlements_service_all on public.user_entitlements
  for all to service_role
  using (true)
  with check (true);

commit;
