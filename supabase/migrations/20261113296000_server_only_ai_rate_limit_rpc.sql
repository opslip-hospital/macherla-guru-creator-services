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
