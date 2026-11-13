-- The customer/admin app reads non-secret channel connection metadata through
-- the public invoker wrapper. Allow that wrapper to call the guarded private
-- SECURITY DEFINER helper, which checks auth.uid() and tenant/admin membership.
grant execute on function private.list_tenant_youtube_connections(uuid) to authenticated;
