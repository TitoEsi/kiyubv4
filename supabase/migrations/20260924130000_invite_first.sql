-- Invitation-first projects: invite has no project until the client accepts.
-- Invitation status remains free-text; DECLINED is now a first-class value
-- alongside PENDING / ACCEPTED / EXPIRED / CANCELLED.

alter table public.invitations
  alter column project_id drop not null;

alter table public.invitations
  add column if not exists project_name text;

alter table public.projects
  add column if not exists invitation_id uuid unique references public.invitations (id);

update public.projects p
set invitation_id = i.id
from (
  select distinct on (project_id) id, project_id
  from public.invitations
  where project_id is not null
  order by project_id, (status = 'ACCEPTED') desc, created_at desc
) i
where p.id = i.project_id
  and p.invitation_id is null;

drop policy if exists invitations_assigned on public.invitations;

create policy invitations_own on public.invitations for all
  using (
    public.is_staff()
    or architect_id = auth.uid()
    or accepted_user_id = auth.uid()
    or exists (
      select 1 from public.profiles pr
      where pr.id = auth.uid() and lower(pr.email) = lower(invitations.email)
    )
    or (project_id is not null and public.can_access_project(project_id))
  )
  with check (
    public.is_staff()
    or architect_id = auth.uid()
    or accepted_user_id = auth.uid()
    or exists (
      select 1 from public.profiles pr
      where pr.id = auth.uid() and lower(pr.email) = lower(invitations.email)
    )
    or (project_id is not null and public.can_access_project(project_id))
  );
