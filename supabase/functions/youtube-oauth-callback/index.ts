import { createClient } from "npm:@supabase/supabase-js@2";
const hash=async(s:string)=>[...new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s)))].map(x=>x.toString(16).padStart(2,"0")).join("");
const hex=(b:Uint8Array)=>[...b].map(x=>x.toString(16).padStart(2,"0")).join("");
function redirect(status:string){const base=Deno.env.get("APP_BASE_URL");if(!base)return new Response("OAuth callback is not configured.",{status:503});const u=new URL(base);u.searchParams.set("youtube_oauth",status);return Response.redirect(u.toString(),303)}
Deno.serve(async(req)=>{
 if(req.method!=="GET")return new Response("Method not allowed",{status:405});
 const q=new URL(req.url).searchParams;if(q.get("error"))return redirect("denied");
 const code=q.get("code")??"",state=q.get("state")??"";if(!code||state.length<32||state.length>256)return redirect("failed");
 try{
  const url=Deno.env.get("SUPABASE_URL")!,service=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,id=Deno.env.get("GOOGLE_CLIENT_ID")!,secret=Deno.env.get("GOOGLE_CLIENT_SECRET")!,uri=Deno.env.get("GOOGLE_REDIRECT_URI")!;
  const keyB64=Deno.env.get("TOKEN_ENCRYPTION_KEY")??"",keyBytes=Uint8Array.from(atob(keyB64),(c)=>c.charCodeAt(0));
  if(!url||!service||!id||!secret||!uri||keyBytes.length!==32)return redirect("not_configured");
  const tr=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams({code,client_id:id,client_secret:secret,redirect_uri:uri,grant_type:"authorization_code"})});
  if(!tr.ok)return redirect("token_exchange_failed");const tokens=await tr.json();if(!tokens.access_token||!tokens.refresh_token)return redirect("refresh_token_missing");
  const cr=await fetch("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",{headers:{Authorization:`Bearer ${tokens.access_token}`}});
  if(!cr.ok)return redirect("channel_lookup_failed");const cd=await cr.json(),ch=cd.items?.[0];if(!ch?.id)return redirect("no_channel_found");
  const iv=crypto.getRandomValues(new Uint8Array(12)),k=await crypto.subtle.importKey("raw",keyBytes,{name:"AES-GCM"},false,["encrypt"]);
  const enc=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv},k,new TextEncoder().encode(tokens.refresh_token)));
  const packed=new Uint8Array(iv.length+enc.length);packed.set(iv);packed.set(enc,iv.length);
  const scopes=typeof tokens.scope==="string"?tokens.scope.split(" ").filter(Boolean):["https://www.googleapis.com/auth/youtube.upload","https://www.googleapis.com/auth/youtube.readonly"];
  const admin=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
  const {error}=await admin.rpc("complete_youtube_oauth",{p_state_hash:await hash(state),p_channel_id:ch.id,p_channel_title:ch.snippet?.title??"YouTube channel",p_encrypted_refresh_token:"\\x"+hex(packed),p_granted_scopes:scopes});
  if(error)return redirect("save_failed");return redirect("connected");
 }catch{return redirect("failed")}
});