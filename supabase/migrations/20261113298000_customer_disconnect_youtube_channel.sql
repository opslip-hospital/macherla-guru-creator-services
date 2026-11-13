create or replace function private.revoke_youtube_connection(
  p_tenant_id uuid,
  p_channel_id text
)
returns boolean
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_rows integer;
begin
  if auth.uid() is null or p_tenant_id is null or nullif(trim(p_channel_id),'') is null then
    raise exception 'authenticated workspace owner required' using errcode='42501';
  end if;
  if not exists (
    select 1 from public.tenant_memberships m
    where m.tenant_id=p_tenant_id and m.user_id=auth.uid()
      and m.membership_role='owner'
  ) then
    raise exception 'workspace owner required' using errcode='42501';
  end if;

  update private.youtube_connections
     set revoked_at=coalesce(revoked_at,now()),
         encrypted_refresh_token=decode('','hex'),
         granted_scopes='{}'::text[]
   where tenant_id=p_tenant_id and channel_id=p_channel_id and revoked_at is null;
  get diagnostics v_rows = row_count;
  if v_rows=0 then return false; end if;

  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
  values(p_tenant_id,auth.uid(),'youtube_channel_disconnected',
    jsonb_build_object('channel_id',p_channel_id,'refresh_token_cleared',true));
  return true;
end;
$function$;

revoke all on function private.revoke_youtube_connection(uuid,text) from public, anon, authenticated;
grant execute on function private.revoke_youtube_connection(uuid,text) to authenticated;

create or replace function public.revoke_youtube_connection(
  p_tenant_id uuid,
  p_channel_id text
)
returns boolean
language sql
security invoker
set search_path to ''
as $function$
  select private.revoke_youtube_connection(p_tenant_id,p_channel_id);
$function$;

revoke all on function public.revoke_youtube_connection(uuid,text) from public, anon, authenticated;
grant execute on function public.revoke_youtube_connection(uuid,text) to authenticated;
