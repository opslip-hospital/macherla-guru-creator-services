-- Enforce schedule-only customer publishing at the database boundary.
create or replace function private.claim_youtube_publish_job(
  p_job_id uuid,
  p_admin_user_id uuid,
  p_mode text,
  p_publish_at timestamptz default null
)
returns jsonb
language plpgsql
security definer
set search_path=''
as $$
declare
  v_job public.upload_jobs%rowtype;
  v_connection private.youtube_connections%rowtype;
begin
  if auth.uid() is null or p_admin_user_id is distinct from auth.uid() then
    raise exception 'authenticated customer required' using errcode='42501';
  end if;
  if p_mode is distinct from 'schedule' then
    raise exception 'only schedule mode is supported' using errcode='22023';
  end if;
  if p_publish_at is null or p_publish_at < now()+interval '15 minutes' then
    raise exception 'scheduled publish time must be at least 15 minutes in the future' using errcode='22023';
  end if;
  select * into v_job from public.upload_jobs where id=p_job_id for update;
  if not found then
    raise exception 'upload job not found' using errcode='P0002';
  end if;
  if not exists(
    select 1 from public.tenant_memberships m
    join public.tenants t on t.id=m.tenant_id
    where m.tenant_id=v_job.tenant_id and m.user_id=auth.uid()
      and m.membership_role='owner' and t.status='active'
  ) then
    raise exception 'active workspace owner required' using errcode='42501';
  end if;
  if v_job.status not in ('uploaded_private','approved') or v_job.youtube_video_id is null then
    raise exception 'private YouTube upload required before scheduling' using errcode='22023';
  end if;
  select * into v_connection from private.youtube_connections
    where id=v_job.connection_id and tenant_id=v_job.tenant_id and revoked_at is null
      and granted_scopes @> array['https://www.googleapis.com/auth/youtube.force-ssl']::text[]
    for update;
  if not found then
    raise exception 'scheduling permission not connected; reconnect YouTube' using errcode='42501';
  end if;
  update public.upload_jobs
    set status='publishing',scheduled_for=p_publish_at,updated_at=now()
    where id=p_job_id;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
    values(v_job.tenant_id,auth.uid(),'youtube_publish_execution_started',
      jsonb_build_object('upload_job_id',p_job_id,'mode','schedule',
        'publish_at',p_publish_at,'explicit_customer_action',true));
  return jsonb_build_object(
    'job_id',v_job.id,'tenant_id',v_job.tenant_id,
    'youtube_video_id',v_job.youtube_video_id,'channel_id',v_connection.channel_id,
    'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'),
    'mode','schedule','publish_at',p_publish_at
  );
end;
$$;
revoke all on function private.claim_youtube_publish_job(uuid,uuid,text,timestamptz) from public,anon,authenticated;
grant execute on function private.claim_youtube_publish_job(uuid,uuid,text,timestamptz) to authenticated;
create or replace function public.claim_youtube_publish_job(
  p_job_id uuid,p_admin_user_id uuid,p_mode text,p_publish_at timestamptz default null
)
returns jsonb
language sql
security invoker
set search_path=''
as $$
  select private.claim_youtube_publish_job(p_job_id,p_admin_user_id,p_mode,p_publish_at);
$$;
revoke all on function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) from public,anon;
grant execute on function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) to authenticated;
