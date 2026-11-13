create table if not exists private.customer_ai_rate_limits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  action text not null check (action in ('youtube_seo','content_studio')),
  window_start timestamptz not null,
  request_count integer not null default 1 check (request_count > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, tenant_id, action, window_start)
);

alter table private.customer_ai_rate_limits enable row level security;
revoke all on table private.customer_ai_rate_limits from public, anon, authenticated;
grant all on table private.customer_ai_rate_limits to service_role;

create or replace function private.consume_customer_ai_rate_limit(
  p_user_id uuid,
  p_tenant_id uuid,
  p_action text,
  p_limit integer
)
returns boolean
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_window_start timestamptz := date_trunc('hour', now());
  v_request_count integer;
begin
  if p_user_id is null or p_tenant_id is null
     or p_action not in ('youtube_seo','content_studio')
     or p_limit is null or p_limit < 1 or p_limit > 100 then
    raise exception 'invalid AI rate limit request' using errcode='22023';
  end if;

  if not exists (
    select 1 from public.tenant_memberships m
    join public.tenants t on t.id=m.tenant_id
    where m.user_id=p_user_id and m.tenant_id=p_tenant_id
      and m.membership_role='owner' and t.status='active'
  ) then
    raise exception 'active workspace owner required' using errcode='42501';
  end if;

  delete from private.customer_ai_rate_limits
   where window_start < date_trunc('hour', now()) - interval '48 hours';

  insert into private.customer_ai_rate_limits(user_id,tenant_id,action,window_start,request_count)
  values(p_user_id,p_tenant_id,p_action,v_window_start,1)
  on conflict(user_id,tenant_id,action,window_start) do update
    set request_count=private.customer_ai_rate_limits.request_count+1,
        updated_at=now()
    where private.customer_ai_rate_limits.request_count < p_limit
  returning request_count into v_request_count;

  return v_request_count is not null;
end;
$function$;

revoke all on function private.consume_customer_ai_rate_limit(uuid,uuid,text,integer) from public, anon, authenticated;
grant execute on function private.consume_customer_ai_rate_limit(uuid,uuid,text,integer) to service_role;

create or replace function public.consume_customer_ai_rate_limit(
  p_user_id uuid,
  p_tenant_id uuid,
  p_action text,
  p_limit integer
)
returns boolean
language sql
security invoker
set search_path to ''
as $function$
  select private.consume_customer_ai_rate_limit(p_user_id,p_tenant_id,p_action,p_limit);
$function$;

revoke all on function public.consume_customer_ai_rate_limit(uuid,uuid,text,integer) from public, anon, authenticated;
grant execute on function public.consume_customer_ai_rate_limit(uuid,uuid,text,integer) to service_role;
