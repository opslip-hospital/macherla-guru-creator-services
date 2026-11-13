import { createClient } from "npm:@supabase/supabase-js@2";
const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS","Content-Type":"application/json"};
const json=(v:unknown,s=200)=>new Response(JSON.stringify(v),{status:s,headers});
function required(n:string){const v=Deno.env.get(n);if(!v)throw new Error("missing_configuration");return v;}
function hexBytes(v:string){v=v.replace(/^\\\\x/i,"");if(!/^(?:[0-9a-f]{2})+$/i.test(v))throw new Error("invalid_token");return new Uint8Array(v.match(/.{2}/g)!.map(x=>parseInt(x,16)));}
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
  const body=await req.json().catch(()=>({})),tenant=typeof body.tenant_id==="string"?body.tenant_id:"";
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(tenant))return json({error:"invalid_workspace"},400);
  const {data:membership}=await user.from("tenant_memberships").select("membership_role").eq("tenant_id",tenant).eq("user_id",auth.user.id).maybeSingle();
  if(membership?.membership_role!=="owner")return json({error:"workspace_owner_required"},403);
  const admin=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:connections,error:connError}=await admin.schema("private").from("youtube_connections")
   .select("id,channel_id,channel_title,encrypted_refresh_token,granted_scopes")
   .eq("tenant_id",tenant).is("revoked_at",null).order("connected_at",{ascending:false}).limit(5);
  if(connError)throw new Error("connection_lookup_failed");
  const connection=(connections??[]).find((x:any)=>Array.isArray(x.granted_scopes)&&x.granted_scopes.includes("https://www.googleapis.com/auth/youtube.readonly"));
  if(!connection)return json({error:"youtube_readonly_connection_required"},409);
  const refresh=await decrypt(connection.encrypted_refresh_token,required("TOKEN_ENCRYPTION_KEY"));
  const tr=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},
   body:new URLSearchParams({client_id:required("GOOGLE_CLIENT_ID"),client_secret:required("GOOGLE_CLIENT_SECRET"),refresh_token:refresh,grant_type:"refresh_token"})});
  if(!tr.ok)throw new Error("google_refresh_failed");
  const tokens=await tr.json();if(!tokens.access_token)throw new Error("access_token_missing");
  const api=async(path:string)=>{const r=await fetch("https://www.googleapis.com/youtube/v3/"+path,{headers:{Authorization:`Bearer ${tokens.access_token}`}});if(!r.ok)throw new Error("youtube_api_failed");return await r.json();};
  const channel=await api("channels?part=snippet,statistics,contentDetails&id="+encodeURIComponent(connection.channel_id));
  const item=channel.items?.[0];if(!item)throw new Error("channel_not_found");
  const playlist=item.contentDetails?.relatedPlaylists?.uploads;
  let recent:any[]=[];
  if(playlist){
   const list=await api("playlistItems?part=snippet,contentDetails&maxResults=20&playlistId="+encodeURIComponent(playlist));
   const ids=(list.items??[]).map((x:any)=>x.contentDetails?.videoId).filter(Boolean);
   if(ids.length){
    const videos=await api("videos?part=snippet,statistics,status&id="+ids.join(","));
    recent=(videos.items??[]).map((v:any)=>({
     video_id:v.id,title:v.snippet?.title??"Untitled",published_at:v.snippet?.publishedAt??null,
     views:Number(v.statistics?.viewCount??0),likes:Number(v.statistics?.likeCount??0),
     comments:Number(v.statistics?.commentCount??0),url:"https://youtu.be/"+v.id,
     privacy_status:v.status?.privacyStatus??"unknown"
    })).sort((a:any,b:any)=>b.views-a.views);
   }
  }
  const stats=item.statistics??{};
  return json({success:true,channel:{id:connection.channel_id,title:item.snippet?.title??connection.channel_title??"YouTube channel",
   description:item.snippet?.description??"",custom_url:item.snippet?.customUrl??"",
   subscribers:stats.hiddenSubscriberCount?null:Number(stats.subscriberCount??0),
   views:stats.viewCount==null?null:Number(stats.viewCount),videos:stats.videoCount==null?null:Number(stats.videoCount)},
   recent_uploads:recent,captured_at:new Date().toISOString()});
 }catch(e){return json({error:"customer_dashboard_refresh_failed",message:"YouTube channel data could not be refreshed. Check the connection and try again."},502);}
});
