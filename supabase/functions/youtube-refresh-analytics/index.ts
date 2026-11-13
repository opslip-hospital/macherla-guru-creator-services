import { createClient } from "npm:@supabase/supabase-js@2";
const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS","Content-Type":"application/json"};
const json=(v:unknown,s=200)=>new Response(JSON.stringify(v),{status:s,headers});
function required(n:string){const v=Deno.env.get(n);if(!v)throw new Error("missing_configuration");return v;}
function hexBytes(v:string){if(!/^(?:[0-9a-f]{2})+$/i.test(v))throw new Error("invalid_token");return new Uint8Array(v.match(/.{2}/g)!.map(x=>parseInt(x,16)));}
async function decrypt(v:string,b64:string){
 const packed=hexBytes(v),raw=Uint8Array.from(atob(b64),(c)=>c.charCodeAt(0));
 if(packed.length<29||raw.length!==32)throw new Error("invalid_key");
 const key=await crypto.subtle.importKey("raw",raw,{name:"AES-GCM"},false,["decrypt"]);
 const clear=await crypto.subtle.decrypt({name:"AES-GCM",iv:packed.slice(0,12)},key,packed.slice(12));
 return new TextDecoder().decode(clear);
}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers});
 if(req.method!=="POST")return json({error:"method_not_allowed"},405);
 try{
  const url=required("SUPABASE_URL"),pub=Deno.env.get("SUPABASE_PUBLISHABLE_KEY")??Deno.env.get("SUPABASE_ANON_KEY"),
   service=Deno.env.get("SUPABASE_SECRET_KEY")??Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!pub||!service)throw new Error("missing_configuration");
  const bearer=(req.headers.get("Authorization")??"").match(/^Bearer\s+(.+)$/i)?.[1];
  if(!bearer)return json({error:"authentication_required"},401);
  const user=createClient(url,pub,{global:{headers:{Authorization:`Bearer ${bearer}`}},auth:{persistSession:false,autoRefreshToken:false}});
  const {data:auth,error:authError}=await user.auth.getUser(bearer);
  if(authError||!auth.user)return json({error:"invalid_session"},401);
  const {data:profile}=await user.from("profiles").select("role").eq("user_id",auth.user.id).maybeSingle();
  if(profile?.role!=="admin")return json({error:"admin_required"},403);
  const body=await req.json().catch(()=>({})),tenant=typeof body.tenant_id==="string"?body.tenant_id:"";
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(tenant))return json({error:"invalid_workspace"},400);
  const admin=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:claim,error:claimError}=await admin.rpc("claim_youtube_analytics",{p_tenant:tenant,p_admin_user_id:auth.user.id});
  if(claimError||!claim)return json({error:"youtube_readonly_connection_required"},409);
  const refresh=await decrypt(claim.encrypted_refresh_token_hex,required("TOKEN_ENCRYPTION_KEY"));
  const tr=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
   body:new URLSearchParams({client_id:required("GOOGLE_CLIENT_ID"),client_secret:required("GOOGLE_CLIENT_SECRET"),refresh_token:refresh,grant_type:"refresh_token"})});
  if(!tr.ok)throw new Error("google_refresh_failed");
  const tokens=await tr.json();if(!tokens.access_token)throw new Error("access_token_missing");
  const response=await fetch(`https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id=${encodeURIComponent(claim.channel_id)}`,{
   headers:{Authorization:`Bearer ${tokens.access_token}`}});
  if(!response.ok)throw new Error("youtube_analytics_failed");
  const payload=await response.json(),channel=payload.items?.[0];
  if(!channel)throw new Error("channel_not_found");
  const stats=channel.statistics??{};
  const snapshot={
   tenant_id:tenant,connection_id:claim.connection_id,channel_id:claim.channel_id,
   channel_title:channel.snippet?.title??claim.channel_title??"YouTube channel",
   subscriber_count:stats.hiddenSubscriberCount?null:Number(stats.subscriberCount??0),
   view_count:stats.viewCount==null?null:Number(stats.viewCount),
   video_count:stats.videoCount==null?null:Number(stats.videoCount),
  };
  const {error:insertError}=await admin.from("channel_analytics_snapshots").insert(snapshot);
  if(insertError)throw new Error("analytics_snapshot_save_failed");
  return json({success:true,channel_title:snapshot.channel_title,subscriber_count:snapshot.subscriber_count,
   view_count:snapshot.view_count,video_count:snapshot.video_count,captured_at:new Date().toISOString()});
 }catch{return json({error:"analytics_refresh_failed",message:"Channel analytics could not be refreshed. Check the YouTube connection and read-only permission."},502);}
});
