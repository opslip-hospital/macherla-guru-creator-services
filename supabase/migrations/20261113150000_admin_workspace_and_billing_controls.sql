create or replace function private.admin_update_tenant_status(p_tenant uuid, p_status text)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_platform_admin() then raise exception 'not authorized' using errcode='42501'; end if;
  if p_status not in ('pending','active','suspended','closed') then raise exception 'invalid tenant status' using errcode='22023'; end if;
  update public.tenants set status=p_status where id=p_tenant;
  if not found then raise exception 'workspace not found' using errcode='P0002'; end if;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details) values(p_tenant,auth.uid(),'workspace_status_changed',jsonb_build_object('status',p_status));
  return true;
end; $$;
create or replace function public.admin_update_tenant_status(p_tenant uuid,p_status text)
returns boolean language sql set search_path = '' as $$ select private.admin_update_tenant_status(p_tenant,p_status); $$;
create or replace function private.admin_update_billing_account(p_tenant uuid,p_plan_code text,p_subscription_status text)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_platform_admin() then raise exception 'not authorized' using errcode='42501'; end if;
  if p_plan_code not in ('trial','starter','creator','pro','custom') then raise exception 'invalid plan code' using errcode='22023'; end if;
  if p_subscription_status not in ('pending','trialing','active','past_due','cancelled') then raise exception 'invalid subscription status' using errcode='22023'; end if;
  if not exists(select 1 from public.tenants where id=p_tenant) then raise exception 'workspace not found' using errcode='P0002'; end if;
  insert into public.billing_accounts(tenant_id,plan_code,subscription_status,updated_at) values(p_tenant,p_plan_code,p_subscription_status,now())
  on conflict(tenant_id) do update set plan_code=excluded.plan_code,subscription_status=excluded.subscription_status,updated_at=now();
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details) values(p_tenant,auth.uid(),'billing_account_updated',jsonb_build_object('plan_code',p_plan_code,'subscription_status',p_subscription_status));
  return true;
end; $$;
create or replace function public.admin_update_billing_account(p_tenant uuid,p_plan_code text,p_subscription_status text)
returns boolean language sql set search_path = '' as $$ select private.admin_update_billing_account(p_tenant,p_plan_code,p_subscription_status); $$;
revoke all on function private.admin_update_tenant_status(uuid,text) from public,anon,authenticated;
revoke all on function private.admin_update_billing_account(uuid,text,text) from public,anon,authenticated;
grant execute on function public.admin_update_tenant_status(uuid,text) to authenticated;
grant execute on function public.admin_update_billing_account(uuid,text,text) to authenticated;