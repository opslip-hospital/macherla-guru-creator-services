-- Match the customer thumbnail intake limit to YouTube's 2 MB custom thumbnail API limit.
do $block$
declare v_def text;
begin
  select pg_get_functiondef('private.set_customer_upload_assets(uuid,text,boolean)'::regprocedure) into v_def;
  v_def := replace(v_def,
    $old$between 1 and 10485760$old$,
    $new$between 1 and 2097152$new$);
  v_def := replace(v_def,
    $old$thumbnail must be JPG or PNG up to 10 MB$old$,
    $new$thumbnail must be JPG or PNG up to 2 MB$new$);
  execute v_def;
end
$block$;
