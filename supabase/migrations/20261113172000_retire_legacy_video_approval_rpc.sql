-- Retire the legacy separate customer-approval RPC. Publish now / Schedule
-- is the only customer consent action in the current workflow.
revoke all on function public.customer_approve_upload(uuid) from public, anon, authenticated;
