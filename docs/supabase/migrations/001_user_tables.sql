-- GymBro User SSOT (Supabase)
-- 001: Create user_profiles / user_settings / user_entitlements
--
-- Notes
-- - Do not hardcode any keys/secrets in this file.
-- - Naming follows snake_case to align with client constants.
-- - SSOT: Supabase Postgres for user profile/settings/entitlements.

begin;

-- Epoch milliseconds helper (used by last_updated).
create or replace function public.unix_timestamp_ms() returns bigint
language sql stable as $$
  select (extract(epoch from now()) * 1000)::bigint;
$$;

-- Unified updated_at trigger function (idempotent).
create or replace function public.update_updated_at_column() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- user_profiles: public profile + training preference + minimal stats
create table if not exists public.user_profiles (
  user_id uuid not null,
  display_name text,
  avatar_url text,
  bio text,
  gender text,
  height_cm real,
  weight_kg real,
  fitness_level integer,
  fitness_goals jsonb not null default '[]'::jsonb,
  workout_days jsonb not null default '[]'::jsonb,
  total_workout_count integer not null default 0,
  weekly_active_minutes integer not null default 0,
  likes_received integer not null default 0,
  is_anonymous boolean not null default false,
  last_updated bigint not null default public.unix_timestamp_ms(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_profiles_pkey primary key (user_id),
  constraint user_profiles_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade
);

drop trigger if exists update_user_profiles_updated_at on public.user_profiles;
create trigger update_user_profiles_updated_at
before update on public.user_profiles
for each row execute function public.update_updated_at_column();

-- user_settings: privacy/notification/AI memory + device-like preferences that are user-bound
create table if not exists public.user_settings (
  user_id uuid not null,
  theme_mode text not null default 'system',
  language_code text not null default 'zh',
  measurement_system text not null default 'metric',
  notifications_enabled boolean not null default true,
  sounds_enabled boolean not null default true,
  location_sharing_enabled boolean not null default false,
  data_sharing_enabled boolean not null default false,
  allow_workout_sharing boolean not null default false,
  auto_backup_enabled boolean not null default false,
  backup_frequency integer not null default 7,
  last_backup_time bigint not null default 0,
  ai_memory_enabled boolean not null default false,
  last_updated bigint not null default public.unix_timestamp_ms(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_settings_pkey primary key (user_id),
  constraint user_settings_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade
);

drop trigger if exists update_user_settings_updated_at on public.user_settings;
create trigger update_user_settings_updated_at
before update on public.user_settings
for each row execute function public.update_updated_at_column();

-- user_entitlements: subscription tier + expiry + feature flags (gate source)
create table if not exists public.user_entitlements (
  user_id uuid not null,
  tier text not null default 'free',
  expires_at bigint,
  flags jsonb not null default '{}'::jsonb,
  last_updated bigint not null default public.unix_timestamp_ms(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_entitlements_pkey primary key (user_id),
  constraint user_entitlements_user_id_fkey foreign key (user_id) references auth.users(id) on delete cascade
);

drop trigger if exists update_user_entitlements_updated_at on public.user_entitlements;
create trigger update_user_entitlements_updated_at
before update on public.user_entitlements
for each row execute function public.update_updated_at_column();

commit;
