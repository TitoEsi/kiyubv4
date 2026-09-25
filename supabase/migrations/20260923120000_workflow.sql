-- KIYUB workflow schema. Reproduces the existing ORM on Postgres + Auth.
-- profiles.id = auth.users.id. No password hashes in application tables.

create extension if not exists "pgcrypto";

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text unique not null,
  role text not null check (role in ('CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL')),
  approved boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, role, approved)
  values (
    new.id,
    coalesce(new.email, ''),
    coalesce(new.raw_user_meta_data->>'role', 'CLIENT'),
    coalesce((new.raw_user_meta_data->>'approved')::boolean, true)
  )
  on conflict (id) do update
    set email = excluded.email;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  client_id uuid references public.profiles (id),
  architect_id uuid references public.profiles (id),
  status text not null default 'DRAFT',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.client_briefs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid unique not null references public.projects (id) on delete cascade,
  questionnaire jsonb not null default '{}'::jsonb,
  specification jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.site_constraints (
  id uuid primary key default gen_random_uuid(),
  project_id uuid unique not null references public.projects (id) on delete cascade,
  lot_shape text,
  lot_width double precision,
  lot_depth double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.design_documents (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  stage text not null default 'CLIENT_BRIEF',
  current_revision_id uuid,
  working_scene_document jsonb,
  working_updated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.revisions (
  id uuid primary key default gen_random_uuid(),
  design_document_id uuid not null references public.design_documents (id) on delete cascade,
  version integer not null,
  source_revision_id uuid references public.revisions (id),
  scene_document jsonb not null default '{}'::jsonb,
  floor_plan jsonb not null default '{}'::jsonb,
  created_by uuid not null references public.profiles (id),
  source_type text not null,
  created_at timestamptz not null default now(),
  unique (design_document_id, version)
);

create table if not exists public.generation_jobs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  requested_by uuid not null references public.profiles (id),
  source_revision_id uuid,
  source_brief_id uuid,
  specification jsonb not null default '{}'::jsonb,
  status text not null default 'PENDING',
  result_candidate_id uuid,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.ai_candidates (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  generation_job_id uuid references public.generation_jobs (id),
  revision_id uuid not null references public.revisions (id),
  selected_by_client boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.comments (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  stage text,
  revision_id uuid references public.revisions (id),
  author_id uuid not null references public.profiles (id),
  object_id text,
  body text not null,
  x double precision,
  y double precision,
  created_at timestamptz not null default now()
);

create table if not exists public.approvals (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  revision_id uuid references public.revisions (id),
  actor_id uuid not null references public.profiles (id),
  kind text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references public.profiles (id),
  project_id uuid references public.projects (id),
  revision_id uuid,
  event_type text not null,
  target text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  project_id uuid references public.projects (id),
  kind text not null,
  message text not null,
  read boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.invitations (
  id uuid primary key default gen_random_uuid(),
  architect_id uuid not null references public.profiles (id),
  project_id uuid not null references public.projects (id) on delete cascade,
  email text not null,
  status text not null default 'PENDING',
  token_hash text unique not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  accepted_at timestamptz,
  accepted_user_id uuid references public.profiles (id)
);

create table if not exists public.inquiries (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null,
  message text not null,
  created_at timestamptz not null default now()
);

create index if not exists projects_client_id_idx on public.projects (client_id);
create index if not exists projects_architect_id_idx on public.projects (architect_id);
create index if not exists generation_jobs_project_id_idx on public.generation_jobs (project_id);
create index if not exists revisions_document_id_idx on public.revisions (design_document_id);
create index if not exists ai_candidates_project_id_idx on public.ai_candidates (project_id);
create index if not exists comments_project_id_idx on public.comments (project_id);
create index if not exists notifications_user_id_idx on public.notifications (user_id);
create index if not exists invitations_token_hash_idx on public.invitations (token_hash);
create index if not exists audit_events_project_id_idx on public.audit_events (project_id);

create trigger projects_updated_at before update on public.projects
  for each row execute function public.set_updated_at();
create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger briefs_updated_at before update on public.client_briefs
  for each row execute function public.set_updated_at();
create trigger site_updated_at before update on public.site_constraints
  for each row execute function public.set_updated_at();
create trigger docs_updated_at before update on public.design_documents
  for each row execute function public.set_updated_at();

create or replace function public.current_role()
returns text language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid()
$$;

create or replace function public.is_staff()
returns boolean language sql stable security definer set search_path = public as $$
  select public.current_role() in ('MAIN_ADMIN', 'IT_PERSONNEL')
$$;

create or replace function public.can_access_project(pid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select public.is_staff()
    or exists (
      select 1 from public.projects p
      where p.id = pid
        and (p.client_id = auth.uid() or p.architect_id = auth.uid())
    )
$$;

alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.client_briefs enable row level security;
alter table public.site_constraints enable row level security;
alter table public.design_documents enable row level security;
alter table public.revisions enable row level security;
alter table public.generation_jobs enable row level security;
alter table public.ai_candidates enable row level security;
alter table public.comments enable row level security;
alter table public.approvals enable row level security;
alter table public.audit_events enable row level security;
alter table public.notifications enable row level security;
alter table public.invitations enable row level security;
alter table public.inquiries enable row level security;

create policy profiles_select on public.profiles for select
  using (id = auth.uid() or public.is_staff() or public.current_role() = 'ARCHITECT');
create policy profiles_update_own on public.profiles for update
  using (id = auth.uid() or public.is_staff());

create policy projects_select on public.projects for select
  using (public.can_access_project(id));
create policy projects_write_assigned on public.projects for all
  using (public.can_access_project(id) or public.is_staff())
  with check (public.can_access_project(id) or public.is_staff());

create policy briefs_all on public.client_briefs for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy site_all on public.site_constraints for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy docs_all on public.design_documents for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy revisions_all on public.revisions for all
  using (exists (select 1 from public.design_documents d where d.id = design_document_id and public.can_access_project(d.project_id)))
  with check (exists (select 1 from public.design_documents d where d.id = design_document_id and public.can_access_project(d.project_id)));
create policy jobs_all on public.generation_jobs for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy candidates_all on public.ai_candidates for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy comments_all on public.comments for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy approvals_all on public.approvals for all
  using (public.can_access_project(project_id))
  with check (public.can_access_project(project_id));
create policy audit_select on public.audit_events for select
  using (public.is_staff() or public.current_role() = 'ARCHITECT' and public.can_access_project(project_id));
create policy notifications_own on public.notifications for all
  using (user_id = auth.uid() or public.is_staff())
  with check (user_id = auth.uid() or public.is_staff());
create policy invitations_assigned on public.invitations for all
  using (public.can_access_project(project_id) or public.is_staff())
  with check (public.can_access_project(project_id) or public.is_staff());
create policy inquiries_insert on public.inquiries for insert with check (true);
create policy inquiries_select_staff on public.inquiries for select using (public.is_staff());
