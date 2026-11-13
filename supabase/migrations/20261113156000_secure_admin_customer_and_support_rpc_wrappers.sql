
create or replace function public.admin_approve_customer(target_user uuid, workspace_name text)
returns uuid language sql security definer set search_path = ''
as $$ select private.approve_customer_request(target_user,workspace_name); $$;

create or replace function public.admin_reject_customer(target_user uuid)
returns boolean language sql security definer set search_path = ''
as $$ select private.reject_customer_request(target_user); $$;

create or replace function public.admin_update_service_ticket_status(p_ticket uuid,p_status text)
returns boolean language sql security definer set search_path = ''
as $$ select private.admin_update_service_ticket_status(p_ticket,p_status); $$;

revoke all on function public.admin_approve_customer(uuid,text) from public,anon;
revoke all on function public.admin_reject_customer(uuid) from public,anon;
revoke all on function public.admin_update_service_ticket_status(uuid,text) from public,anon;
grant execute on function public.admin_approve_customer(uuid,text) to authenticated;
grant execute on function public.admin_reject_customer(uuid) to authenticated;
grant execute on function public.admin_update_service_ticket_status(uuid,text) to authenticated;
