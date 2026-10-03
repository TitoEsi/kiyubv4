alter table public.profiles
  add column if not exists terms_accepted_at timestamptz,
  add column if not exists privacy_accepted_at timestamptz;

update public.profiles
  set terms_accepted_at = coalesce(terms_accepted_at, created_at, now()),
      privacy_accepted_at = coalesce(privacy_accepted_at, created_at, now());
