-- Per-user display unit. Geometry is always stored in meters; this is presentation only.
alter table public.profiles
  add column if not exists measurement_unit text not null default 'm';

alter table public.profiles
  drop constraint if exists profiles_measurement_unit_check;

alter table public.profiles
  add constraint profiles_measurement_unit_check
  check (measurement_unit in ('m', 'ft', 'cm', 'mm', 'in'));

-- Comment pin coordinate space. NULL = legacy plan-feet pins; 'metric' = meters.
alter table public.comments
  add column if not exists coord_units text;
