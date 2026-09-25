alter table public.profiles
  add column if not exists suspended boolean not null default false;

alter table public.profiles
  add column if not exists deleted_at timestamptz;
