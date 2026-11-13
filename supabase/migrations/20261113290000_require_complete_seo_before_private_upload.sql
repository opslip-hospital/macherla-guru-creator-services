create or replace function private.claim_youtube_upload_job(p_job_id uuid, p_admin_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $function$
declare
  v_job public.upload_jobs%rowtype;
  v_connection private.youtube_connections%rowtype;
  v_metadata public.content_metadata%rowtype;
  v_tag_count integer;
  v_tag_chars integer;
  v_hashtag_count integer;
  v_title_count integer;
begin
  if auth.uid() is null or p_admin_user_id is distinct from auth.uid() then
    raise exception 'authenticated customer required' using errcode='42501';
  end if;
  select * into v_job from public.upload_jobs where id=p_job_id for update;
  if not found then raise exception 'upload job not found' using errcode='P0002'; end if;
  if not exists(
    select 1 from public.tenant_memberships m
    join public.tenants t on t.id=m.tenant_id
    where m.tenant_id=v_job.tenant_id and m.user_id=auth.uid()
      and m.membership_role='owner' and t.status='active'
  ) then
    raise exception 'active workspace owner required' using errcode='42501';
  end if;
  if v_job.status<>'received' or v_job.storage_object_path is null then
    raise exception 'video file is not ready for YouTube upload' using errcode='22023';
  end if;
  select * into v_connection from private.youtube_connections
    where tenant_id=v_job.tenant_id and revoked_at is null
      and granted_scopes @> array['https://www.googleapis.com/auth/youtube.upload']::text[]
    order by connected_at desc limit 1 for update;
  if not found then
    raise exception 'connected YouTube upload permission not found' using errcode='P0002';
  end if;
  select * into v_metadata from public.content_metadata
    where upload_job_id=p_job_id and tenant_id=v_job.tenant_id
    order by created_at desc limit 1;
  if v_metadata.id is null then
    raise exception 'complete SEO metadata must be saved before upload' using errcode='22023';
  end if;
  select count(distinct lower(x)) into v_tag_count
    from unnest(coalesce(v_metadata.tags,'{}'::text[])) as x;
  select coalesce(sum(length(x)),0) + greatest(cardinality(coalesce(v_metadata.tags,'{}'::text[]))-1,0) into v_tag_chars
    from unnest(coalesce(v_metadata.tags,'{}'::text[])) as x;
  if v_tag_count<12 or v_tag_count>18 or v_tag_chars>450
     or v_tag_count<>cardinality(coalesce(v_metadata.tags,'{}'::text[])) then
    raise exception 'SEO metadata requires 12 to 18 unique tags within 450 characters' using errcode='22023';
  end if;
  select count(distinct lower(x)) into v_hashtag_count
    from unnest(coalesce(v_metadata.hashtags,'{}'::text[])) as x;
  if v_hashtag_count<>5 or cardinality(coalesce(v_metadata.hashtags,'{}'::text[]))<>5
     or not exists(
       select 1 from unnest(coalesce(v_metadata.hashtags,'{}'::text[])) as x
       where lower(x)='macherlaguru'
     ) then
    raise exception 'SEO metadata requires five unique hashtags including MacherlaGuru' using errcode='22023';
  end if;
  if jsonb_typeof(coalesce(v_metadata.metadata_details,'{}'::jsonb)->'title_options')<>'array'
     or jsonb_array_length(coalesce(v_metadata.metadata_details,'{}'::jsonb)->'title_options')<>5 then
    raise exception 'SEO metadata requires five title options' using errcode='22023';
  end if;
  select count(distinct lower(value)) into v_title_count
    from jsonb_array_elements_text(v_metadata.metadata_details->'title_options') as value;
  if v_title_count<>5 or length(btrim(coalesce(v_metadata.title,'')))<1 then
    raise exception 'SEO title options are incomplete' using errcode='22023';
  end if;
  update public.upload_jobs set status='processing',connection_id=v_connection.id,updated_at=now()
    where id=p_job_id;
  insert into public.audit_events(tenant_id,actor_user_id,event_type,details)
    values(v_job.tenant_id,auth.uid(),'youtube_private_upload_started',
      jsonb_build_object('upload_job_id',p_job_id,'channel_id',v_connection.channel_id,'actor_role','customer_owner'));
  return jsonb_build_object(
    'job_id',v_job.id,'tenant_id',v_job.tenant_id,
    'storage_object_path',v_job.storage_object_path,'mime_type',v_job.mime_type,
    'file_size_bytes',v_job.file_size_bytes,'video_title',coalesce(v_metadata.title,v_job.video_title),
    'description',coalesce(v_metadata.description,''),'tags',coalesce(to_jsonb(v_metadata.tags),'[]'::jsonb),
    'hashtags',coalesce(to_jsonb(v_metadata.hashtags),'[]'::jsonb),
    'metadata_details',coalesce(v_metadata.metadata_details,'{}'::jsonb),
    'channel_id',v_connection.channel_id,
    'encrypted_refresh_token_hex',encode(v_connection.encrypted_refresh_token,'hex')
  );
end;
$function$;
