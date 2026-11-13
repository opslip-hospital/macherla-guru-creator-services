-- Keep SECURITY DEFINER code in the non-exposed private schema.
-- Public RPC wrappers execute as invokers; their private callees perform auth.uid()
-- and tenant/admin checks before touching privileged rows.
alter function public.admin_approve_customer(uuid,text) security invoker;
alter function public.admin_reject_customer(uuid) security invoker;
alter function public.admin_update_billing_account(uuid,text,text) security invoker;
alter function public.admin_update_service_ticket_status(uuid,text) security invoker;
alter function public.admin_update_tenant_status(uuid,text) security invoker;
alter function public.claim_youtube_publish_job(uuid,uuid,text,timestamptz) security invoker;
alter function public.claim_youtube_upload_job(uuid,uuid) security invoker;
alter function public.create_customer_upload_job(uuid,text,text,text,bigint) security invoker;
alter function public.finalize_customer_video_upload(uuid,text) security invoker;

grant execute on function private.approve_customer_request(uuid,text) to authenticated;
grant execute on function private.reject_customer_request(uuid) to authenticated;
grant execute on function private.admin_update_billing_account(uuid,text,text) to authenticated;
grant execute on function private.admin_update_service_ticket_status(uuid,text) to authenticated;
grant execute on function private.admin_update_tenant_status(uuid,text) to authenticated;
grant execute on function private.claim_youtube_publish_job(uuid,uuid,text,timestamptz) to authenticated;
grant execute on function private.claim_youtube_upload_job(uuid,uuid) to authenticated;
grant execute on function private.create_customer_upload_job(uuid,text,text,text,bigint) to authenticated;
grant execute on function private.finalize_customer_video_upload(uuid,text) to authenticated;
grant execute on function private.admin_save_content_metadata(uuid,text,text,text[],text[],text) to authenticated;
