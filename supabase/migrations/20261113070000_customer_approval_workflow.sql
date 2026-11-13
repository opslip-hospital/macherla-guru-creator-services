-- Customer approval workflow for the isolated Creator Services project.
create table if not exists public.customer_requests (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  display_name text,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id)
);
alter table public.customer_requests enable row level security;
drop policy if exists customer_requests_select_self_or_admin on public.customer_requests;
create policy customer_requests_select_self_or_admin
  on public.customer_requests for select to authenticated
  using (user_id = (select auth.uid()) or (select private.is_platform_admin()));
grant select on public.customer_requests to authenticated;
create index if not exists customer_requests_status_created_idx
  on public.customer_requests(status, created_at desc);

create or replace function public.handle_new_creator_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (user_id, display_name, role)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'), 'customer')
  on conflict (user_id) do nothing;
  insert into public.customer_requests(user_id,email,display_name,status)
  values (new.id, lower(new.email), coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'), 'pending')
  on conflict (user_id) do nothing;
  return new;
end;
$$;
revoke all on function public.handle_new_creator_user() from public, anon, authenticated;

insert into public.customer_requests(user_id,email,display_name,status)
select u.id, lower(u.email), p.display_name, 'pending'
from auth.users u
join public.profiles p on p.user_id=u.id
where p.role='customer'
  and not exists (select 1 from public.tenant_memberships m where m.user_id=u.id)
on conflict (user_id) do nothing;

create or replace function private.approve_customer_request(target_user uuid, workspace_name text)
returns uuid language plpgsql security definer set search_path = ''
as $$
declare new_tenant uuid; req public.customer_requests%rowtype;
begin
  if auth.uid() is null or not private.is_platform_admin() then
    raise exception 'not authorized' using errcode='42501';
  end if;
  if target_user is null or workspace_name is null
     or length(btrim(workspace_name)) < 2 or length(btrim(workspace_name)) > 120 then
    raise exception 'invalid customer or workspace name' using errcode='22023';
  end if;
  select * into req from public.customer_requests where user_id=target_user for update;
  if not found or req.status <> 'pending' then
    raise exception 'customer request is not pending' using errcode='P0002';
  end if;
  if exists(select 1 from public.tenant_memberships where user_id=target_user) then
    raise exception 'customer already has a workspace' using errcode='23505';
  end if;
  insert into public.tenants(business_name,status)
  values (btrim(workspace_name),'active') returning id into new_tenant;
  insert into public.tenant_memberships(tenant_id,user_id,membership_role)
  values(new_tenant,target_user,'owner');
  update public.customer_requests
    set status='approved', reviewed_at=now(), reviewed_by=auth.uid()
    where user_id=target_user;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
  values(new_tenant,auth.uid(),'customer_request_approved',
         jsonb_build_object('customer_user_id',target_user,'email',req.email));
  return new_tenant;
end;
$$;
revoke all on function private.approve_customer_request(uuid,text) from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.approve_customer_request(uuid,text) to authenticated;

create or replace function private.reject_customer_request(target_user uuid)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare req public.customer_requests%rowtype;
begin
  if auth.uid() is null or not private.is_platform_admin() then
    raise exception 'not authorized' using errcode='42501';
  end if;
  select * into req from public.customer_requests where user_id=target_user for update;
  if not found or req.status <> 'pending' then
    raise exception 'customer request is not pending' using errcode='P0002';
  end if;
  update public.customer_requests
    set status='rejected', reviewed_at=now(), reviewed_by=auth.uid()
    where user_id=target_user;
  insert into public.audit_events(actor_user_id,event_type,details)
  values(auth.uid(),'customer_request_rejected',
         jsonb_build_object('customer_user_id',target_user,'email',req.email));
  return true;
end;
$$;
revoke all on function private.reject_customer_request(uuid) from public, anon;
grant execute on function private.reject_customer_request(uuid) to authenticated;

create or replace function public.admin_approve_customer(target_user uuid, workspace_name text)
returns uuid language sql security invoker set search_path = ''
as $$ select private.approve_customer_request(target_user,workspace_name); $$;
revoke all on function public.admin_approve_customer(uuid,text) from public, anon;
grant execute on function public.admin_approve_customer(uuid,text) to authenticated;

create or replace function public.admin_reject_customer(target_user uuid)
returns boolean language sql security invoker set search_path = ''
as $$ select private.reject_customer_request(target_user); $$;
revoke all on function public.admin_reject_customer(uuid) from public, anon;
grant execute on function public.admin_reject_customer(uuid) to authenticated;
