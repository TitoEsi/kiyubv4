-- Retire the IT_PERSONNEL role and rename MAIN_ADMIN to ADMIN.
-- Active roles afterwards: CLIENT, ARCHITECT, ADMIN.
--
-- IT accounts are deleted, not converted. audit_events is append-only, so instead of rewriting
-- history each deleted actor is snapshotted into historical_actors and audit_events.actor_id
-- keeps pointing at the original id.
--
-- Admin keeps project administration (projects table) but only reads design data.

-- 1. Historical identities for deleted accounts --------------------------------------------

create table if not exists public.historical_actors (
  id uuid primary key,
  email text not null,
  full_name text,
  role text not null,
  deleted_at timestamptz not null default now()
);

alter table public.historical_actors enable row level security;

insert into public.historical_actors (id, email, full_name, role)
select p.id, p.email, p.full_name, p.role
from public.profiles p
where p.role = 'IT_PERSONNEL'
on conflict (id) do nothing;

-- 2. Refuse to delete IT accounts that own non-audit data ---------------------------------

do $$
declare
  owned text;
begin
  select string_agg(tbl, ', ') into owned
  from (
    select 'projects' as tbl where exists (
      select 1 from public.projects p join public.historical_actors h on h.id in (p.client_id, p.architect_id))
    union all select 'revisions' where exists (
      select 1 from public.revisions r join public.historical_actors h on h.id = r.created_by)
    union all select 'comments' where exists (
      select 1 from public.comments c join public.historical_actors h on h.id in (c.author_id, c.resolved_by))
    union all select 'approvals' where exists (
      select 1 from public.approvals a join public.historical_actors h on h.id = a.actor_id)
    union all select 'generation_jobs' where exists (
      select 1 from public.generation_jobs g join public.historical_actors h on h.id = g.requested_by)
    union all select 'invitations' where exists (
      select 1 from public.invitations i join public.historical_actors h
        on h.id in (i.architect_id, i.accepted_user_id, i.auth_user_id))
    union all select 'architect_applications.invited_by/accepted_user_id' where exists (
      select 1 from public.architect_applications a join public.historical_actors h
        on h.id in (a.invited_by, a.accepted_user_id))
  ) t;
  if owned is not null then
    raise exception 'IT_PERSONNEL accounts own data in: %. Reassign it before running this migration.', owned;
  end if;
end;
$$;

-- 3. Detach history from live profiles so deleted actors stay referenced -------------------

alter table public.audit_events drop constraint if exists audit_events_actor_id_fkey;
alter table public.architect_applications drop constraint if exists architect_applications_reviewed_by_fkey;

comment on column public.audit_events.actor_id is
  'profiles.id, or historical_actors.id for deleted accounts. Not a foreign key by design.';
comment on column public.architect_applications.reviewed_by is
  'profiles.id, or historical_actors.id for deleted accounts. Not a foreign key by design.';

-- 4. Delete IT accounts (cascades to profiles and their notifications) ---------------------

delete from auth.users u
using public.historical_actors h
where u.id = h.id and h.role = 'IT_PERSONNEL';

delete from public.profiles where role = 'IT_PERSONNEL';

-- 5. Rename MAIN_ADMIN -> ADMIN under the new role constraint ---------------------------------

do $$
declare
  c record;
begin
  for c in
    select conname from pg_constraint
    where conrelid = 'public.profiles'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%role%'
  loop
    execute format('alter table public.profiles drop constraint %I', c.conname);
  end loop;
end;
$$;

update public.profiles set role = 'ADMIN' where role = 'MAIN_ADMIN';

update auth.users
set raw_user_meta_data = jsonb_set(coalesce(raw_user_meta_data, '{}'::jsonb), '{role}', '"ADMIN"')
where raw_user_meta_data->>'role' = 'MAIN_ADMIN';

alter table public.profiles
  add constraint profiles_role_check check (role in ('CLIENT', 'ARCHITECT', 'ADMIN'));

-- 6. Authorization helpers -------------------------------------------------------------------

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select coalesce(public.current_role() = 'ADMIN', false)
$$;

create or replace function public.is_project_participant(pid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.projects p
    where p.id = pid
      and (p.client_id = auth.uid() or p.architect_id = auth.uid())
  )
$$;

create or replace function public.can_view_project(pid uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select public.is_admin() or public.is_project_participant(pid)
$$;

-- 7. Policies: replace every is_staff()/can_access_project() dependency ----------------------

drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles for select
  using (
    id = auth.uid()
    or public.is_admin()
    or exists (
      select 1 from public.projects p
      where public.is_project_participant(p.id)
        and (p.client_id = profiles.id or p.architect_id = profiles.id)
    )
  );

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles for update
  using (id = auth.uid() or public.is_admin());

drop policy if exists projects_select on public.projects;
create policy projects_select on public.projects for select
  using (public.can_view_project(id));

-- Project administration (create, assign) stays with Admin; participants keep their writes.
drop policy if exists projects_write_assigned on public.projects;
create policy projects_write_assigned on public.projects for all
  using (public.is_project_participant(id) or public.is_admin())
  with check (public.is_project_participant(id) or public.is_admin());

-- Design data: Admin reads, only project participants write.
drop policy if exists briefs_all on public.client_briefs;
create policy briefs_select on public.client_briefs for select
  using (public.can_view_project(project_id));
create policy briefs_write on public.client_briefs for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists site_all on public.site_constraints;
create policy site_select on public.site_constraints for select
  using (public.can_view_project(project_id));
create policy site_write on public.site_constraints for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists docs_all on public.design_documents;
create policy docs_select on public.design_documents for select
  using (public.can_view_project(project_id));
create policy docs_write on public.design_documents for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists revisions_all on public.revisions;
create policy revisions_select on public.revisions for select
  using (exists (
    select 1 from public.design_documents d
    where d.id = design_document_id and public.can_view_project(d.project_id)));
create policy revisions_write on public.revisions for all
  using (exists (
    select 1 from public.design_documents d
    where d.id = design_document_id and public.is_project_participant(d.project_id)))
  with check (exists (
    select 1 from public.design_documents d
    where d.id = design_document_id and public.is_project_participant(d.project_id)));

drop policy if exists jobs_all on public.generation_jobs;
create policy jobs_select on public.generation_jobs for select
  using (public.can_view_project(project_id));
create policy jobs_write on public.generation_jobs for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists candidates_all on public.ai_candidates;
create policy candidates_select on public.ai_candidates for select
  using (public.can_view_project(project_id));
create policy candidates_write on public.ai_candidates for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists comments_all on public.comments;
create policy comments_select on public.comments for select
  using (public.can_view_project(project_id));
create policy comments_write on public.comments for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists approvals_all on public.approvals;
create policy approvals_select on public.approvals for select
  using (public.can_view_project(project_id));
create policy approvals_write on public.approvals for all
  using (public.is_project_participant(project_id))
  with check (public.is_project_participant(project_id));

drop policy if exists audit_select on public.audit_events;
create policy audit_select on public.audit_events for select
  using (
    public.is_admin()
    or (public.current_role() in ('ARCHITECT', 'CLIENT') and public.is_project_participant(project_id))
  );

drop policy if exists notifications_own on public.notifications;
create policy notifications_own on public.notifications for all
  using (user_id = auth.uid() or public.is_admin())
  with check (user_id = auth.uid() or public.is_admin());

drop policy if exists invitations_assigned on public.invitations;
drop policy if exists invitations_own on public.invitations;
create policy invitations_own on public.invitations for all
  using (
    public.is_admin()
    or architect_id = auth.uid()
    or accepted_user_id = auth.uid()
    or exists (
      select 1 from public.profiles pr
      where pr.id = auth.uid() and lower(pr.email) = lower(invitations.email)
    )
    or (project_id is not null and public.is_project_participant(project_id))
  )
  with check (
    public.is_admin()
    or architect_id = auth.uid()
    or accepted_user_id = auth.uid()
    or exists (
      select 1 from public.profiles pr
      where pr.id = auth.uid() and lower(pr.email) = lower(invitations.email)
    )
    or (project_id is not null and public.is_project_participant(project_id))
  );

drop policy if exists inquiries_select_staff on public.inquiries;
create policy inquiries_select_admin on public.inquiries for select using (public.is_admin());

drop policy if exists architect_applications_staff on public.architect_applications;
create policy architect_applications_admin on public.architect_applications for all
  using (public.is_admin())
  with check (public.is_admin());

drop policy if exists historical_actors_admin on public.historical_actors;
create policy historical_actors_admin on public.historical_actors for select
  using (public.is_admin());

-- 8. Retire the old helpers now that no policy depends on them --------------------------------

drop function if exists public.can_access_project(uuid);
drop function if exists public.is_staff();
