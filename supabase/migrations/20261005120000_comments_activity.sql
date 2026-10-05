-- Comment threads, resolution, edit tracking; version submission marker; immutable project activity.

alter table public.comments add column if not exists parent_id uuid references public.comments (id);
alter table public.comments add column if not exists updated_at timestamptz;
alter table public.comments add column if not exists resolved_at timestamptz;
alter table public.comments add column if not exists resolved_by uuid references public.profiles (id);
alter table public.comments add column if not exists resolution_note text;
alter table public.comments add column if not exists resolution_revision_id uuid references public.revisions (id);
create index if not exists comments_parent_id_idx on public.comments (parent_id);

alter table public.revisions add column if not exists submitted_at timestamptz;

-- Project Activity (audit_events) is append-only.
create or replace function public.audit_events_immutable()
returns trigger
language plpgsql
as $$
begin
  -- An idempotent upsert that rewrites identical values is harmless; any real change is not.
  if tg_op = 'UPDATE' and row(new.*) is not distinct from row(old.*) then
    return new;
  end if;
  raise exception 'audit_events is append-only; % is not allowed', tg_op;
end;
$$;

drop trigger if exists audit_events_no_update on public.audit_events;
create trigger audit_events_no_update
  before update or delete on public.audit_events
  for each row execute function public.audit_events_immutable();

drop policy if exists audit_select on public.audit_events;
create policy audit_select on public.audit_events for select
  using (
    public.is_staff()
    or (public.current_role() in ('ARCHITECT', 'CLIENT') and public.can_access_project(project_id))
  );
