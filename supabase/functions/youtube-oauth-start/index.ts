import { createClient } from "npm:@supabase/supabase-js@2";
const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS","Content-Type":"application/json"};
const json=(v:unknown,s=200)=>new Response(JSON.stringify(v),{status:s,headers});
const map=(n:string)=>{try{return JSON.parse(Deno.env.get(n)??"{}")}catch{return {}}};
const b64url=(b:Uint8Array)=>{let x="";for(const n of b)x+=String.fromCharCode(n);return btoa(x).replaceAll("+","-").replaceAll("/","_").replaceAll("=","")};
const hash=async(s:string)=>[...new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s)))].map(x=>x.toString(16).padStart(2,"0")).join("");
async function adminRpc(url:string,key:string,name:string,body:unknown){
 const r=await fetch(`${url}/rest/v1/rpc/${name}`,{method:"POST",headers:{"apikey":key,"Content-Type":"application/json"},body:JSON.stringify(body)});
 if(!r.ok)throw new Error("admin_rpc_failed");
 return await r.json().catch(()=>null);
}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers});
 if(req.method!=="POST")return json({error:"method_not_allowed"},405);
 try{
  const url=Deno.env.get("SUPABASE_URL")!,pub=map("SUPABASE_PUBLISHABLE_KEYS").default??Deno.env.get("SUPABASE_ANON_KEY"),secret=map("SUPABASE_SECRET_KEYS").default??Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"),clientId=Deno.env.get("GOOGLE_CLIENT_ID"),redirect=Deno.env.get("GOOGLE_REDIRECT_URI");
  if(!url||!pub||!secret||!clientId||!redirect)return json({error:"oauth_not_configured"},503);
  const token=(req.headers.get("Authorization")??"").match(/^Bearer\s+(.+)$/i)?.[1];
  if(!token)return json({error:"authentication_required"},401);
  const userClient=createClient(url,pub,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false,autoRefreshToken:false}});
  const {data:ud,error:ue}=await userClient.auth.getUser(token);
  if(ue||!ud.user)return json({error:"invalid_session"},401);
  const body=await req.json().catch(()=>({})),tenantId=typeof body.tenant_id==="string"?body.tenant_id:"";
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(tenantId))return json({error:"invalid_workspace"},400);
  const {data:m}=await userClient.from("tenant_memberships").select("membership_role").eq("tenant_id",tenantId).eq("user_id",ud.user.id).maybeSingle();
  const {data:t}=await userClient.from("tenants").select("status").eq("id",tenantId).maybeSingle();
  if(m?.membership_role!=="owner"||t?.status!=="active")return json({error:"active_workspace_owner_required"},403);
  const raw=new Uint8Array(32);crypto.getRandomValues(raw);const state=b64url(raw),stateHash=await hash(state);
  await adminRpc(url,secret,"create_youtube_oauth_state",{p_user_id:ud.user.id,p_tenant_id:tenantId,p_state_hash:stateHash,p_expires_at:new Date(Date.now()+600000).toISOString()});
  const g=new URL("https://accounts.google.com/o/oauth2/v2/auth");
  g.searchParams.set("client_id",clientId);g.searchParams.set("redirect_uri",redirect);g.searchParams.set("response_type","code");
  g.searchParams.set("scope","https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly");
  g.searchParams.set("access_type","offline");g.searchParams.set("prompt","consent");g.searchParams.set("include_granted_scopes","true");g.searchParams.set("state",state);
  return json({authorization_url:g.toString()});
 }catch{return json({error:"oauth_start_failed"},500)}
});