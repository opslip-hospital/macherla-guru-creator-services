-- Initial tenant-isolated schema for Macherla Guru Creator Services.
-- Applied to the dedicated Supabase project: gigthhrovhktrpghpnya.
-- The existing Macherla Guru YouTube AI Manager project was not modified.

create schema if not exists private;

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  role text not null default 'customer' check (role in ('customer','admin')),
  created_at timestamptz not null default now()
);
create table public.tenants (
  id uuid primary key default gen_random_uuid(),
  business_name text not null,
  status text not null default 'pending' check (status in ('pending','active','suspended','closed')),
  created_at timestamptz not null default now()
);
create table public.tenant_memberships (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  membership_role text not null default 'owner' check (membership_role in ('owner','member')),
  created_at timestamptz not null default now(),
  primary key (tenant_id, user_id)
);
create table private.youtube_connections (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  channel_id text not null,
  channel_title text,
  encrypted_refresh_token bytea not null,
  granted_scopes text[] not null default '{}',
  connected_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (tenant_id, channel_id)
);
create table public.upload_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  connection_id uuid references private.youtube_connections(id) on delete set null,
  video_title text,
  status text not null default 'draft' check (status in ('draft','uploaded_private','awaiting_approval','scheduled','published','failed','cancelled')),
  youtube_video_id text,
  scheduled_for timestamptz,
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table public.content_metadata (
  id uuid primary key default gen_random_uuid(),
  upload_job_id uuid not null references public.upload_jobs(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  title text,
  description text,
  tags text[] not null default '{}',
  hashtags text[] not null default '{}',
  caption text,
  prepared_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create table public.service_tickets (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  subject text not null,
  message text not null,
  status text not null default 'open' check (status in ('open','in_progress','waiting_customer','resolved','closed')),
  created_at timestamptz not null default now()
);
create table public.audit_events (
  id bigint generated always as identity primary key,
  tenant_id uuid references public.tenants(id) on delete set null,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create table public.billing_accounts (
  tenant_id uuid primary key references public.tenants(id) on delete cascade,
  plan_code text not null default 'trial',
  subscription_status text not null default 'pending' check (subscription_status in ('pending','trialing','active','past_due','cancelled')),
  billing_customer_ref text,
  updated_at timestamptz not null default now()
);

create or replace function public.is_platform_admin()
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.profiles p
    where p.user_id = (select auth.uid()) and p.role = 'admin');
$$;
create or replace function public.is_tenant_member(target_tenant uuid)
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from public.tenant_memberships m
    where m.tenant_id = target_tenant and m.user_id = (select auth.uid()));
$$;

alter table public.profiles enable row level security;
alter table public.tenants enable row level security;
alter table public.tenant_memberships enable row level security;
alter table public.upload_jobs enable row level security;
alter table public.content_metadata enable row level security;
alter table public.service_tickets enable row level security;
alter table public.audit_events enable row level security;
alter table public.billing_accounts enable row level security;
alter table private.youtube_connections enable row level security;

create policy "profiles_select_self_or_admin" on public.profiles
for select to authenticated using (user_id = (select auth.uid()) or (select public.is_platform_admin()));
create policy "tenants_select_member_or_admin" on public.tenants
for select to authenticated using ((select public.is_tenant_member(id)) or (select public.is_platform_admin()));
create policy "memberships_select_self_or_admin" on public.tenant_memberships
for select to authenticated using (user_id = (select auth.uid()) or (select public.is_platform_admin()));
create policy "uploads_select_member_or_admin" on public.upload_jobs
for select to authenticated using ((select public.is_tenant_member(tenant_id)) or (select public.is_platform_admin()));
create policy "metadata_select_member_or_admin" on public.content_metadata
for select to authenticated using ((select public.is_tenant_member(tenant_id)) or (select public.is_platform_admin()));
create policy "tickets_select_member_or_admin" on public.service_tickets
for select to authenticated using ((select public.is_tenant_member(tenant_id)) or (select public.is_platform_admin()));
create policy "tickets_insert_member" on public.service_tickets
for insert to authenticated with check ((select public.is_tenant_member(tenant_id)));
create policy "audit_select_admin_only" on public.audit_events
for select to authenticated using ((select public.is_platform_admin()));
create policy "billing_select_member_or_admin" on public.billing_accounts
for select to authenticated using ((select public.is_tenant_member(tenant_id)) or (select public.is_platform_admin()));

revoke all on schema private from public, anon, authenticated;
revoke all on all tables in schema private from public, anon, authenticated;
grant usage on schema public to authenticated;
grant select on public.profiles, public.tenants, public.tenant_memberships,
  public.upload_jobs, public.content_metadata, public.service_tickets,
  public.audit_events, public.billing_accounts to authenticated;
grant insert on public.service_tickets to authenticated;
revoke insert, update, delete on public.profiles, public.tenants,
  public.tenant_memberships, public.upload_jobs, public.content_metadata,
  public.audit_events, public.billing_accounts from anon, authenticated;
revoke update, delete on public.service_tickets from anon, authenticated;
grant execute on function public.is_platform_admin() to authenticated;
grant execute on function public.is_tenant_member(uuid) to authenticated;
