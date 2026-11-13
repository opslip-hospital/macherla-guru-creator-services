
create or replace function public.create_customer_upload_job(
 p_tenant uuid,p_title text,p_filename text,p_mime text,p_size bigint
) returns uuid language sql security definer set search_path = ''
as $$ select private.create_customer_upload_job(p_tenant,p_title,p_filename,p_mime,p_size); $$;

create or replace function public.finalize_customer_video_upload(
 p_job uuid,p_object_path text
) returns boolean language sql security definer set search_path = ''
as $$ select private.finalize_customer_video_upload(p_job,p_object_path); $$;

create or replace function public.claim_youtube_upload_job(
 p_job_id uuid,p_admin_user_id uuid
) returns jsonb language sql security definer set search_path = ''
as $$ select private.claim_youtube_upload_job(p_job_id,p_admin_user_id); $$;

create or replace function public.claim_youtube_publish_job(
 p_job_id uuid,p_admin_user_id uuid,p_mode text,p_publish_at timestamp with time zone default null
) returns jsonb language sql security definer set search_path = ''
as $$ select private.claim_youtube_publish_job(p_job_id,p_admin_user_id,p_mode,p_publish_at); $$;

create or replace function public.admin_update_tenant_status(p_tenant uuid,p_status text)
returns boolean language sql security definer set search_path = ''
as $$ select private.admin_update_tenant_status(p_tenant,p_status); $$;

create or replace function public.admin_update_billing_account(p_tenant uuid,p_plan_code text,p_subscription_status text)
returns boolean language sql security definer set search_path = ''
as $$ select private.admin_update_billing_account(p_tenant,p_plan_code,p_subscription_status); $$;

revoke all on function public.create_customer_upload_job(uuid,text,text,text,bigint) from public,anon;
revoke all on function public.finalize_customer_video_upload(uuid,text) from public,anon;
revoke all on function public.claim_youtube_upload_job(uuid,uuid) from public,anon;
revoke all on function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) from public,anon;
revoke all on function public.admin_update_tenant_status(uuid,text) from public,anon;
revoke all on function public.admin_update_billing_account(uuid,text,text) from public,anon;
grant execute on function public.create_customer_upload_job(uuid,text,text,text,bigint) to authenticated;
grant execute on function public.finalize_customer_video_upload(uuid,text) to authenticated;
grant execute on function public.claim_youtube_upload_job(uuid,uuid) to authenticated;
grant execute on function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) to authenticated;
grant execute on function public.admin_update_tenant_status(uuid,text) to authenticated;
grant execute on function public.admin_update_billing_account(uuid,text,text) to authenticated;
