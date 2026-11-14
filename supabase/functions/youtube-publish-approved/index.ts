import { createClient } from "npm:@supabase/supabase-js@2";
const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS","Content-Type":"application/json"};
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers});
function required(name:string){const v=Deno.env.get(name);if(!v)throw new Error("missing_configuration");return v;}
function decodeHex(value:string){if(!/^(?:[0-9a-f]{2})+$/i.test(value))throw new Error("invalid_token");return new Uint8Array(value.match(/.{2}/g)!.map(x=>parseInt(x,16)));}
async function decrypt(hex:string,b64:string){
 const packed=decodeHex(hex),raw=Uint8Array.from(atob(b64),(c)=>c.charCodeAt(0));
 if(packed.length<29||raw.length!==32)throw new Error("invalid_encryption_material");
 const key=await crypto.subtle.importKey("raw",raw,{name:"AES-GCM"},false,["decrypt"]);
 const clear=await crypto.subtle.decrypt({name:"AES-GCM",iv:packed.slice(0,12)},key,packed.slice(12));
 return new TextDecoder().decode(clear);
}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers});
 if(req.method!=="POST")return json({error:"method_not_allowed"},405);
 let admin:ReturnType<typeof createClient>|null=null,jobId:string|null=null;
 let youtubeUpdated=false;
 let youtubeUpdateStarted=false;
 let youtubeUpdateResponded=false;
 let youtubeUpdateOutcomeUnknown=false;
 let youtubeVideoId:string|null=null;
 try{
  const url=required("SUPABASE_URL");
  const publishable=Deno.env.get("SUPABASE_PUBLISHABLE_KEY")??Deno.env.get("SUPABASE_ANON_KEY");
  const service=Deno.env.get("SUPABASE_SECRET_KEY")??Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!publishable||!service)throw new Error("missing_configuration");
  const bearer=(req.headers.get("Authorization")??"").match(/^Bearer\s+(.+)$/i)?.[1];
  if(!bearer)return json({error:"authentication_required"},401);
  const userClient=createClient(url,publishable,{global:{headers:{Authorization:`Bearer ${bearer}`}},auth:{persistSession:false,autoRefreshToken:false}});
  const {data:auth,error:authError}=await userClient.auth.getUser(bearer);
  if(authError||!auth.user)return json({error:"invalid_session"},401);
  const body=await req.json().catch(()=>({}));
  jobId=typeof body.job_id==="string"?body.job_id:"";
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(jobId))return json({error:"invalid_job_id"},400);
  const mode=body.mode==="schedule"?"schedule":"";
  if(!mode)return json({error:"invalid_publish_mode"},400);
  let publishAt:string|null=null;
  if(mode==="schedule"){
   const date=typeof body.publish_at==="string"?new Date(body.publish_at):new Date(NaN);
   if(Number.isNaN(date.getTime())||date.getTime()<Date.now()+15*60*1000)return json({error:"schedule_must_be_15_minutes_ahead"},400);
   publishAt=date.toISOString();
  }
  admin=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:claimed,error:claimError}=await userClient.rpc("claim_youtube_publish_job",{
   p_job_id:jobId,p_admin_user_id:auth.user.id,p_mode:mode,p_publish_at:publishAt,
  });
  if(claimError||!claimed)return json({error:"workspace_owner_or_private_upload_required"},409);
  youtubeVideoId=String(claimed.youtube_video_id);
  const refresh=await decrypt(claimed.encrypted_refresh_token_hex,required("TOKEN_ENCRYPTION_KEY"));
  const tokenResponse=await fetch("https://oauth2.googleapis.com/token",{
   method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
   body:new URLSearchParams({client_id:required("GOOGLE_CLIENT_ID"),client_secret:required("GOOGLE_CLIENT_SECRET"),refresh_token:refresh,grant_type:"refresh_token"}),
  });
  if(!tokenResponse.ok)throw new Error("google_token_refresh_failed");
  const tokenData=await tokenResponse.json();if(!tokenData.access_token)throw new Error("google_access_token_missing");
  const status=mode==="now"?{privacyStatus:"public"}:{privacyStatus:"private",publishAt};
  youtubeUpdateStarted=true;
  const update=await fetch("https://www.googleapis.com/youtube/v3/videos?part=status",{
   method:"PUT",headers:{Authorization:`Bearer ${tokenData.access_token}`,"Content-Type":"application/json"},
   body:JSON.stringify({id:claimed.youtube_video_id,status}),
  });
  youtubeUpdateResponded=true;
  if(!update.ok){
   if(update.status>=500)youtubeUpdateOutcomeUnknown=true;
   throw new Error("youtube_video_update_failed");
  }
  youtubeUpdated=true;
  const finalStatus=mode==="now"?"published":"scheduled";
  const {error:updateError}=await admin.from("upload_jobs").update({
   status:finalStatus,scheduled_for:publishAt,updated_at:new Date().toISOString(),
  }).eq("id",jobId).eq("status","publishing");
  if(updateError)throw new Error("job_status_update_failed");
  await admin.from("audit_events").insert({
   tenant_id:claimed.tenant_id,actor_user_id:auth.user.id,event_type:mode==="now"?"youtube_video_published":"youtube_video_scheduled",
   details:{upload_job_id:jobId,youtube_video_id:claimed.youtube_video_id,channel_id:claimed.channel_id,publish_at:publishAt,initiated_by_authenticated_owner:true},
  });
  return json({success:true,status:finalStatus,youtube_video_id:claimed.youtube_video_id,
   youtube_url:`https://www.youtube.com/watch?v=${claimed.youtube_video_id}`,
   message:mode==="now"?"Your video is now public.":"Your video is scheduled."});
 }catch{
  const outcomeUnknown=youtubeUpdateStarted&&(!youtubeUpdateResponded||youtubeUpdateOutcomeUnknown);
  if(admin&&jobId&&!youtubeUpdated&&!outcomeUnknown)await admin.from("upload_jobs").update({status:"uploaded_private",scheduled_for:null,updated_at:new Date().toISOString()}).eq("id",jobId).eq("status","publishing");
  return json({
   error:youtubeUpdated?"publish_status_sync_failed":outcomeUnknown?"publish_status_unknown":"publish_or_schedule_failed",
   ...(youtubeUpdated&&youtubeVideoId?{youtube_video_id:youtubeVideoId,youtube_url:`https://www.youtube.com/watch?v=${youtubeVideoId}`}:{}),
   message:youtubeUpdated
    ?"YouTube accepted the publish or schedule action, but dashboard status sync failed. Check YouTube Studio before retrying."
    :outcomeUnknown
     ?"The YouTube request timed out before a response was received. The job is held to prevent an unsafe retry; check YouTube Studio and contact support if its status is unclear."
     :"Publishing could not be completed. The video remains private; review the channel connection and retry."
  },502);
 }
});
