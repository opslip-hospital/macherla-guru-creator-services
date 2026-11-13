-- Keep SECURITY DEFINER helpers outside the exposed public API schema.
create or replace function private.is_platform_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $function$
  select exists (
    select 1
    from public.profiles p
    where p.user_id = (select auth.uid())
      and p.role = 'admin'
  );
$function$;

create or replace function private.is_tenant_member(target_tenant uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $function$
  select exists (
    select 1
    from public.tenant_memberships m
    where m.tenant_id = target_tenant
      and m.user_id = (select auth.uid())
  );
$function$;

grant usage on schema private to authenticated;
revoke all on function private.is_platform_admin() from public, anon;
revoke all on function private.is_tenant_member(uuid) from public, anon;
grant execute on function private.is_platform_admin() to authenticated;
grant execute on function private.is_tenant_member(uuid) to authenticated;

drop policy if exists audit_select_admin_only on public.audit_events;
create policy audit_select_admin_only on public.audit_events
  for select to authenticated
  using ((select private.is_platform_admin()));

drop policy if exists billing_select_member_or_admin on public.billing_accounts;
create policy billing_select_member_or_admin on public.billing_accounts
  for select to authenticated
  using (
    (select private.is_tenant_member(billing_accounts.tenant_id))
    or (select private.is_platform_admin())
  );

drop policy if exists metadata_select_member_or_admin on public.content_metadata;
create policy metadata_select_member_or_admin on public.content_metadata
  for select to authenticated
  using (
    (select private.is_tenant_member(content_metadata.tenant_id))
    or (select private.is_platform_admin())
  );

drop policy if exists profiles_select_self_or_admin on public.profiles;
create policy profiles_select_self_or_admin on public.profiles
  for select to authenticated
  using (
    user_id = (select auth.uid())
    or (select private.is_platform_admin())
  );

drop policy if exists tickets_insert_member on public.service_tickets;
create policy tickets_insert_member on public.service_tickets
  for insert to authenticated
  with check ((select private.is_tenant_member(service_tickets.tenant_id)));

drop policy if exists tickets_select_member_or_admin on public.service_tickets;
create policy tickets_select_member_or_admin on public.service_tickets
  for select to authenticated
  using (
    (select private.is_tenant_member(service_tickets.tenant_id))
    or (select private.is_platform_admin())
  );

drop policy if exists memberships_select_self_or_admin on public.tenant_memberships;
create policy memberships_select_self_or_admin on public.tenant_memberships
  for select to authenticated
  using (
    user_id = (select auth.uid())
    or (select private.is_platform_admin())
  );

drop policy if exists tenants_select_member_or_admin on public.tenants;
create policy tenants_select_member_or_admin on public.tenants
  for select to authenticated
  using (
    (select private.is_tenant_member(tenants.id))
    or (select private.is_platform_admin())
  );

drop policy if exists uploads_select_member_or_admin on public.upload_jobs;
create policy uploads_select_member_or_admin on public.upload_jobs
  for select to authenticated
  using (
    (select private.is_tenant_member(upload_jobs.tenant_id))
    or (select private.is_platform_admin())
  );

-- Old public-schema RPC helpers are no longer referenced by any policy.
revoke all on function public.is_platform_admin() from public, anon, authenticated;
revoke all on function public.is_tenant_member(uuid) from public, anon, authenticated;
drop function public.is_platform_admin();
drop function public.is_tenant_member(uuid);

-- Add indexes for foreign-key lookups reported by the performance advisor.
create index if not exists audit_events_actor_user_id_idx on public.audit_events(actor_user_id);
create index if not exists audit_events_tenant_id_idx on public.audit_events(tenant_id);
create index if not exists content_metadata_prepared_by_idx on public.content_metadata(prepared_by);
create index if not exists content_metadata_tenant_id_idx on public.content_metadata(tenant_id);
create index if not exists content_metadata_upload_job_id_idx on public.content_metadata(upload_job_id);
create index if not exists service_tickets_tenant_id_idx on public.service_tickets(tenant_id);
create index if not exists tenant_memberships_user_id_idx on public.tenant_memberships(user_id);
create index if not exists upload_jobs_approved_by_idx on public.upload_jobs(approved_by);
create index if not exists upload_jobs_connection_id_idx on public.upload_jobs(connection_id);
create index if not exists upload_jobs_tenant_id_idx on public.upload_jobs(tenant_id);
create index if not exists youtube_connections_tenant_id_idx on private.youtube_connections(tenant_id);
