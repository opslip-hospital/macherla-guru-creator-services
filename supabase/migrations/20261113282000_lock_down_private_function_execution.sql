-- Keep private-schema helpers callable by RLS, but prevent direct client invocation
-- of internal administrative and workflow functions.
revoke execute on all functions in schema private from public, anon, authenticated;
grant execute on all functions in schema private to service_role;
grant execute on function private.is_platform_admin() to authenticated;
grant execute on function private.is_tenant_member(uuid) to authenticated;
