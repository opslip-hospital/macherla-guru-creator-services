import { createClient } from "npm:@supabase/supabase-js@2";
const headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"authorization, apikey, content-type","Access-Control-Allow-Methods":"POST, OPTIONS","Content-Type":"application/json"};
const json=(v:unknown,s=200)=>new Response(JSON.stringify(v),{status:s,headers});
const clean=(v:unknown,n:number)=>typeof v==="string"?v.trim().slice(0,n):"";
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response("ok",{headers});
 if(req.method!=="POST")return json({error:"method_not_allowed"},405);
 try{
  const url=Deno.env.get("SUPABASE_URL")!,pub=Deno.env.get("SUPABASE_PUBLISHABLE_KEY")??Deno.env.get("SUPABASE_ANON_KEY");
  const service=Deno.env.get("SUPABASE_SECRET_KEY")??Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const key=Deno.env.get("GEMINI_API_KEY");if(!url||!pub||!service||!key)return json({error:"ai_not_configured"},503);
  const bearer=(req.headers.get("Authorization")??"").match(/^Bearer\s+(.+)$/i)?.[1];
  if(!bearer)return json({error:"authentication_required"},401);
  const user=createClient(url,pub,{global:{headers:{Authorization:`Bearer ${bearer}`}},auth:{persistSession:false,autoRefreshToken:false}});
  const {data:auth,error}=await user.auth.getUser(bearer);if(error||!auth.user)return json({error:"invalid_session"},401);
  const body=await req.json().catch(()=>({})),tenant=clean(body.tenant_id,64),kind=clean(body.kind,60),topic=clean(body.topic,500),notes=clean(body.notes,1000),language=clean(body.language,40)||"Telugu";
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(tenant)||!topic)return json({error:"topic_required"},400);
  const admin=createClient(url,service,{auth:{persistSession:false,autoRefreshToken:false}});
  const {data:membership}=await admin.from("tenant_memberships").select("tenant_id").eq("tenant_id",tenant).eq("user_id",auth.user.id).eq("membership_role","owner").maybeSingle();
  if(!membership)return json({error:"workspace_owner_required"},403);
  const {data:channelSnapshot}=await admin.from("channel_analytics_snapshots").select("channel_title")
   .eq("tenant_id",tenant).order("captured_at",{ascending:false}).limit(1).maybeSingle();
  const channelName=clean(channelSnapshot?.channel_title,120)||"the creator's connected YouTube channel";
  const prompt=`You are a practical YouTube content strategist and Telugu scriptwriter. Create original, engaging but truthful content for the creator's own channel.
Creator's channel name: ${channelName}
Channel/content type: ${kind||"YouTube video idea"}
Topic: ${topic}
Additional direction: ${notes||"None"}
Language: ${language}
Return a useful finished draft with a strong opening hook, clear scene/dialogue flow when it is a script, and a short ending/CTA. Avoid unsupported factual claims, copyrighted dialogue, and promises of virality. Use natural ${language}. Keep Shorts scripts suitable for 15-30 seconds unless the user specifies otherwise.`;
  const response=await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",{method:"POST",headers:{"Content-Type":"application/json","x-goog-api-key":key},body:JSON.stringify({contents:[{role:"user",parts:[{text:prompt}]}],generationConfig:{temperature:0.75,maxOutputTokens:1800}})});
  if(!response.ok)return json({error:response.status===429||response.status===503?"ai_temporarily_busy":"ai_generation_failed"},502);
  const result=await response.json(),draft=result?.candidates?.[0]?.content?.parts?.map((p:any)=>p.text??"").join("").trim()??"";
  if(!draft)return json({error:"empty_ai_response"},502);
  await admin.from("audit_events").insert({tenant_id:tenant,actor_user_id:auth.user.id,event_type:"customer_content_studio_generated",details:{kind,language}});
  return json({success:true,draft});
 }catch{return json({error:"content_studio_failed"},502);}
});
