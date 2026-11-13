-- Claim customer-approved videos for an audited publish/schedule worker.
alter table public.upload_jobs drop constraint if exists upload_jobs_status_check;
alter table public.upload_jobs add constraint upload_jobs_status_check
 check (status in ('draft','received','processing','uploaded_private','awaiting_approval','approved','publishing','scheduled','published','failed','cancelled'));
create or replace function private.claim_youtube_publish_job(p_job_id uuid,p_admin_user_id uuid,p_mode text,p_publish_at timestamptz default null)
returns jsonb language plpgsql security definer set search_path=''
as $$
declare v_job public.upload_jobs%rowtype; v_connection private.youtube_connections%rowtype;
begin
 if p_admin_user_id is null or not exists(select 1 from public.profiles where user_id=p_admin_user_id and role='admin') then raise exception 'platform admin required' using errcode='42501'; end if;
 if p_mode not in ('now','schedule') then raise exception 'invalid publish mode' using errcode='22023'; end if;
 if p_mode='schedule' and (p_publish_at is null or p_publish_at < now()+interval '15 minutes') then raise exception 'scheduled publish time must be at least 15 minutes in the future' using errcode='22023'; end if;
 if p_mode='now' and p_publish_at is not null then raise exception 'publish time not allowed for immediate publish' using errcode='22023'; end if;
 select * into v_job from public.upload_jobs where id=p_job_id for update;
 if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
 if v_job.status<>'approved' or v_job.approved_by is null or v_job.approved_at is null or v_job.youtube_video_id is null then raise exception 'explicit customer approval and private YouTube upload required' using errcode='42501'; end if;
 select * into v_connection from private.youtube_connections
  where id=v_job.connection_id and tenant_id=v_job.tenant_id and revoked_at is null
   and granted_scopes @> array['https://www.googleapis.com/auth/youtube.force-ssl']::text[] for update;
 if not found then raise exception 'publishing permission not connected; customer must reconnect YouTube' using errcode='42501'; end if;
 update public.upload_jobs set status='publishing',scheduled_for=p_publish_at,updated_at=now() where id=p_job_id;
 insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
 values(v_job.tenant_id,p_admin_user_id,'youtube_publish_execution_started',jsonb_build_object('upload_job_id',p_job_id,'mode',p_mode,'publish_at',p_publish_at,'customer_approved_by',v_job.approved_by));
 return jsonb_build_object('job_id',v_job.id,'tenant_id',v_job.tenant_id,'youtube_video_id',v_job.youtube_video_id,'channel_id',v_connection.channel_id,'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex'),'mode',p_mode,'publish_at',p_publish_at);
end; $$;
revoke all on function private.claim_youtube_publish_job(uuid,uuid,text,timestamptz) from public,anon,authenticated;
grant execute on function private.claim_youtube_publish_job(uuid,uuid,text,timestamptz) to service_role;
create or replace function public.claim_youtube_publish_job(p_job_id uuid,p_admin_user_id uuid,p_mode text,p_publish_at timestamptz default null)
returns jsonb language sql security invoker set search_path=''
as $$ select private.claim_youtube_publish_job(p_job_id,p_admin_user_id,p_mode,p_publish_at); $$;
revoke all on function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) from public,anon,authenticated;
grant execute on function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) to service_role;
