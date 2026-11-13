-- Managed content, customer approval, and support status workflows.
-- All privileged mutations are exposed through authenticated RPCs and guarded
-- inside the non-exposed private schema.
alter table public.upload_jobs drop constraint if exists upload_jobs_status_check;
alter table public.upload_jobs
  add constraint upload_jobs_status_check
  check (status in ('draft','uploaded_private','awaiting_approval','approved','scheduled','published','failed','cancelled'));

create or replace function private.admin_save_content_metadata(
  p_upload_job uuid, p_title text, p_description text,
  p_tags text[], p_hashtags text[], p_caption text
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare v_tenant uuid; v_metadata uuid;
begin
  if auth.uid() is null or not private.is_platform_admin() then
    raise exception 'not authorized' using errcode='42501';
  end if;
  if p_upload_job is null or length(btrim(coalesce(p_title,''))) < 1
     or length(p_title) > 100 or length(coalesce(p_description,'')) > 5000
     or length(coalesce(p_caption,'')) > 2200
     or coalesce(array_length(p_tags,1),0) > 500
     or coalesce(array_length(p_hashtags,1),0) > 30 then
    raise exception 'invalid metadata' using errcode='22023';
  end if;
  select tenant_id into v_tenant from public.upload_jobs where id=p_upload_job for update;
  if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
  select id into v_metadata from public.content_metadata
    where upload_job_id=p_upload_job order by created_at desc limit 1 for update;
  if v_metadata is null then
    insert into public.content_metadata(upload_job_id,tenant_id,title,description,tags,hashtags,caption,prepared_by)
    values(p_upload_job,v_tenant,btrim(p_title),coalesce(p_description,''),
      coalesce(p_tags,'{}'::text[]),coalesce(p_hashtags,'{}'::text[]),coalesce(p_caption,''),auth.uid())
    returning id into v_metadata;
  else
    update public.content_metadata set title=btrim(p_title),description=coalesce(p_description,''),
      tags=coalesce(p_tags,'{}'::text[]),hashtags=coalesce(p_hashtags,'{}'::text[]),
      caption=coalesce(p_caption,''),prepared_by=auth.uid(),created_at=now()
    where id=v_metadata;
  end if;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
  values(v_tenant,auth.uid(),'content_metadata_prepared',
    jsonb_build_object('upload_job_id',p_upload_job,'metadata_id',v_metadata));
  return v_metadata;
end;
$$;
revoke all on function private.admin_save_content_metadata(uuid,text,text,text[],text[],text) from public, anon;
grant execute on function private.admin_save_content_metadata(uuid,text,text,text[],text[],text) to authenticated;

create or replace function private.customer_approve_upload(p_upload_job uuid)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare v_tenant uuid; v_status text;
begin
  if auth.uid() is null then raise exception 'authentication required' using errcode='42501'; end if;
  select tenant_id,status into v_tenant,v_status from public.upload_jobs where id=p_upload_job for update;
  if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
  if not exists(select 1 from public.tenant_memberships
    where tenant_id=v_tenant and user_id=auth.uid() and membership_role='owner') then
    raise exception 'workspace owner required' using errcode='42501';
  end if;
  if v_status not in ('uploaded_private','awaiting_approval') then
    raise exception 'video is not awaiting customer approval' using errcode='22023';
  end if;
  update public.upload_jobs set status='approved',approved_by=auth.uid(),approved_at=now(),updated_at=now()
    where id=p_upload_job;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
  values(v_tenant,auth.uid(),'customer_approved_video_publish',
    jsonb_build_object('upload_job_id',p_upload_job,'approval','explicit_customer_consent'));
  return true;
end;
$$;
revoke all on function private.customer_approve_upload(uuid) from public, anon;
grant execute on function private.customer_approve_upload(uuid) to authenticated;

create or replace function private.admin_update_service_ticket_status(p_ticket uuid,p_status text)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare v_tenant uuid;
begin
  if auth.uid() is null or not private.is_platform_admin() then
    raise exception 'not authorized' using errcode='42501';
  end if;
  if p_status not in ('open','in_progress','waiting_customer','resolved','closed') then
    raise exception 'invalid ticket status' using errcode='22023';
  end if;
  update public.service_tickets set status=p_status where id=p_ticket returning tenant_id into v_tenant;
  if not found then raise exception 'ticket not found' using errcode='P0002'; end if;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
  values(v_tenant,auth.uid(),'support_ticket_status_changed',
    jsonb_build_object('ticket_id',p_ticket,'status',p_status));
  return true;
end;
$$;
revoke all on function private.admin_update_service_ticket_status(uuid,text) from public, anon;
grant execute on function private.admin_update_service_ticket_status(uuid,text) to authenticated;

create or replace function public.admin_save_content_metadata(
  p_upload_job uuid,p_title text,p_description text,p_tags text[],p_hashtags text[],p_caption text
) returns uuid language sql security invoker set search_path = ''
as $$ select private.admin_save_content_metadata(p_upload_job,p_title,p_description,p_tags,p_hashtags,p_caption); $$;
revoke all on function public.admin_save_content_metadata(uuid,text,text,text[],text[],text) from public, anon;
grant execute on function public.admin_save_content_metadata(uuid,text,text,text[],text[],text) to authenticated;

create or replace function public.customer_approve_upload(p_upload_job uuid)
returns boolean language sql security invoker set search_path = ''
as $$ select private.customer_approve_upload(p_upload_job); $$;
revoke all on function public.customer_approve_upload(uuid) from public, anon;
grant execute on function public.customer_approve_upload(uuid) to authenticated;

create or replace function public.admin_update_service_ticket_status(p_ticket uuid,p_status text)
returns boolean language sql security invoker set search_path = ''
as $$ select private.admin_update_service_ticket_status(p_ticket,p_status); $$;
revoke all on function public.admin_update_service_ticket_status(uuid,text) from public, anon;
grant execute on function public.admin_update_service_ticket_status(uuid,text) to authenticated;
