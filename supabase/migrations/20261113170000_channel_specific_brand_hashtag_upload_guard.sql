do $migration$
declare v_definition text;
begin
  select pg_get_functiondef(p.oid) into v_definition
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='private' and p.proname='claim_youtube_upload_job'
    and pg_get_function_identity_arguments(p.oid)='p_job_id uuid, p_admin_user_id uuid';
  if v_definition is null then raise exception 'claim_youtube_upload_job definition not found'; end if;
  if position('where lower(x)=''macherlaguru''' in v_definition)=0 then
    raise exception 'Expected legacy brand hashtag guard not found; refusing migration';
  end if;
  v_definition := replace(v_definition,
    'where lower(x)=''macherlaguru''',
    'where lower(x)=left(regexp_replace(lower(normalize(v_connection.channel_title, NFKC)), ''[^[:alnum:]]'', '''', ''g''), 60)');
  v_definition := replace(v_definition,
    'SEO metadata requires five unique hashtags including MacherlaGuru',
    'SEO metadata requires five unique hashtags including the connected channel brand hashtag');
  execute v_definition;
end
$migration$;