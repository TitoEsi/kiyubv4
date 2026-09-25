-- Narrow profiles_select: own row, staff, or project participants.
-- Replaces the previous ARCHITECT-can-read-all-profiles policy.

drop policy if exists profiles_select on public.profiles;

create policy profiles_select on public.profiles for select
  using (
    id = auth.uid()
    or public.is_staff()
    or exists (
      select 1 from public.projects p
      where public.can_access_project(p.id)
        and (p.client_id = profiles.id or p.architect_id = profiles.id)
    )
  );
