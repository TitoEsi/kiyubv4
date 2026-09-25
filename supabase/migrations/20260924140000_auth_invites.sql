-- Auth invitation onboarding: profile names, invite Auth user link, architect applications.

alter table public.profiles
  add column if not exists full_name text;

alter table public.invitations
  add column if not exists auth_user_id uuid references public.profiles (id);

create table if not exists public.architect_applications (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  full_name text not null,
  information text,
  status text not null default 'PENDING_APPROVAL',
  invited_by uuid not null references public.profiles (id),
  reviewed_by uuid references public.profiles (id),
  reviewed_at timestamptz,
  rejection_reason text,
  token_hash text unique,
  expires_at timestamptz,
  accepted_user_id uuid references public.profiles (id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists architect_applications_email_idx on public.architect_applications (lower(email));
create index if not exists architect_applications_status_idx on public.architect_applications (status);

alter table public.architect_applications enable row level security;

drop policy if exists architect_applications_staff on public.architect_applications;
create policy architect_applications_staff on public.architect_applications for all
  using (public.is_staff())
  with check (public.is_staff());
