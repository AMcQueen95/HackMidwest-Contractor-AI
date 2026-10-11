-- Run once in the Supabase SQL editor. Application requests use the authenticated
-- user's JWT, so row-level security applies even when called by our backend.
begin;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);
create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null check (length(trim(name)) between 1 and 120),
  created_at timestamptz not null default now()
);
create index if not exists companies_owner_idx on public.companies(owner_id);
create table if not exists public.company_state (
  company_id uuid primary key references public.companies(id) on delete cascade,
  revision text not null,
  payload text not null -- Fernet-encrypted books/imports/Plaid access tokens; server key required
);

alter table public.profiles enable row level security;
alter table public.companies enable row level security;
alter table public.company_state enable row level security;

drop policy if exists own_profile on public.profiles;
create policy own_profile on public.profiles for select to authenticated using (id = auth.uid());
drop policy if exists own_companies on public.companies;
create policy own_companies on public.companies for all to authenticated
  using (owner_id = auth.uid()) with check (owner_id = auth.uid());
drop policy if exists own_company_state on public.company_state;
create policy own_company_state on public.company_state for all to authenticated
  using (exists (select 1 from public.companies c where c.id = company_id and c.owner_id = auth.uid()))
  with check (exists (select 1 from public.companies c where c.id = company_id and c.owner_id = auth.uid()));

revoke all on public.profiles, public.companies, public.company_state from anon;
grant select on public.profiles to authenticated;
grant select, insert, update, delete on public.companies, public.company_state to authenticated;

create or replace function public.create_account_profile()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles(id) values (new.id) on conflict do nothing;
  return new;
end;
$$;
revoke all on function public.create_account_profile() from public, anon, authenticated;
drop trigger if exists on_toolbelt_account_created on auth.users;
create trigger on_toolbelt_account_created after insert on auth.users
  for each row execute function public.create_account_profile();
insert into public.profiles(id) select id from auth.users on conflict do nothing;

commit;
