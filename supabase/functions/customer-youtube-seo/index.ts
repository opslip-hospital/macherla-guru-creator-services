import { createClient } from "npm:@supabase/supabase-js@2";

const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers });
function required(name: string) {
  const value = Deno.env.get(name);
  if (!value) throw new Error("missing_configuration");
  return value;
}
function cleanText(value: unknown, max: number): string {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}
function normalizeTags(value: unknown, max: number): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((x) => String(x).trim()).filter(Boolean).slice(0, max);
}
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  try {
    const url = required("SUPABASE_URL");
    const publishable = Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ?? Deno.env.get("SUPABASE_ANON_KEY");
    const service = Deno.env.get("SUPABASE_SECRET_KEY") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!publishable || !service) throw new Error("missing_configuration");
    const bearer = (req.headers.get("Authorization") ?? "").match(/^Bearer\s+(.+)$/i)?.[1];
    if (!bearer) return json({ error: "authentication_required" }, 401);
    const userClient = createClient(url, publishable, {
      global: { headers: { Authorization: `Bearer ${bearer}` } },
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const { data: auth, error: authError } = await userClient.auth.getUser(bearer);
    if (authError || !auth.user) return json({ error: "invalid_session" }, 401);
    const body = await req.json().catch(() => ({}));
    const jobId = cleanText(body.job_id, 64);
    const action = body.action === "save" ? "save" : "generate";
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(jobId)) {
      return json({ error: "invalid_job_id" }, 400);
    }
    const admin = createClient(url, service, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: job, error: jobError } = await admin.from("upload_jobs")
      .select("id,tenant_id,video_title,status").eq("id", jobId).maybeSingle();
    if (jobError || !job) return json({ error: "video_not_found" }, 404);
    const { data: membership } = await admin.from("tenant_memberships")
      .select("tenant_id").eq("tenant_id", job.tenant_id).eq("user_id", auth.user.id)
      .eq("membership_role", "owner").maybeSingle();
    if (!membership) return json({ error: "workspace_owner_required" }, 403);
    if (!["received", "uploaded_private", "awaiting_approval", "approved"].includes(job.status)) {
      return json({ error: "video_not_ready_for_metadata" }, 409);
    }

    let metadata: Record<string, unknown>;
    if (action === "generate") {
      const apiKey = required("GEMINI_API_KEY");
      const sourceTitle = cleanText(body.title, 100) || cleanText(job.video_title, 100);
      const context = cleanText(body.context, 1500);
      const language = cleanText(body.language, 40) || "Telugu";
      if (!sourceTitle) return json({ error: "video_topic_required" }, 400);
      const prompt = `You are an expert YouTube SEO editor for a creator's own channel.
Create truthful, compelling YouTube metadata based only on the supplied video topic/context. Do not invent events, claims, names, or details absent from the input. Optimize naturally for YouTube search and viewer clarity; never promise virality.
Output language/script: ${language}.
Video title/topic: ${sourceTitle}
Creator context / what happens in the video: ${context || "Not provided; stay close to the topic and avoid unsupported specifics."}
Return JSON only with this exact shape:
{"title":"under 100 characters","description":"SEO-friendly description, up to 4500 characters; include relevant hashtags at the end","tags":["short relevant tags"],"hashtags":["without #, up to 5"],"caption":"short social caption"}
Rules: title <=100 chars; description <=4500 chars; tags <=20 and total tag characters <=450; hashtags <=5; caption <=1000 chars. Use the requested language/script. Tags should be concise search phrases, not hashtag strings. Hashtags must be relevant and not generic spam.`;
      const response = await fetch(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
          body: JSON.stringify({
            contents: [{ role: "user", parts: [{ text: prompt }] }],
            generationConfig: { responseMimeType: "application/json", temperature: 0.6, maxOutputTokens: 1800 },
          }),
        },
      );
      if (!response.ok) {
        const status = response.status;
        return json({ error: status === 429 || status === 503 ? "ai_temporarily_busy" : "ai_generation_failed" }, 502);
      }
      const generated = await response.json();
      const text = generated?.candidates?.[0]?.content?.parts?.map((p: {text?: string}) => p.text ?? "").join("") ?? "";
      const parsed = JSON.parse(text.replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim());
      metadata = {
        title: cleanText(parsed.title, 100),
        description: cleanText(parsed.description, 5000),
        tags: normalizeTags(parsed.tags, 20),
        hashtags: normalizeTags(parsed.hashtags, 5).map((x) => x.replace(/^#+/, "")),
        caption: cleanText(parsed.caption, 2200),
      };
    } else {
      metadata = {
        title: cleanText(body.title, 100),
        description: cleanText(body.description, 5000),
        tags: normalizeTags(body.tags, 100),
        hashtags: normalizeTags(body.hashtags, 30).map((x) => x.replace(/^#+/, "")),
        caption: cleanText(body.caption, 2200),
      };
      if (!metadata.title) return json({ error: "title_required" }, 400);
      const totalTagChars = (metadata.tags as string[]).reduce((n, tag) => n + tag.length, 0);
      if (totalTagChars > 500) return json({ error: "tags_limit_exceeded" }, 400);
    }
    const { data: existing } = await admin.from("content_metadata").select("id")
      .eq("upload_job_id", jobId).order("created_at", { ascending: false }).limit(1).maybeSingle();
    const record = {
      upload_job_id: jobId,
      tenant_id: job.tenant_id,
      title: metadata.title,
      description: metadata.description,
      tags: metadata.tags,
      hashtags: metadata.hashtags,
      caption: metadata.caption,
      prepared_by: auth.user.id,
      created_at: new Date().toISOString(),
    };
    const write = existing?.id
      ? await admin.from("content_metadata").update(record).eq("id", existing.id)
      : await admin.from("content_metadata").insert(record);
    if (write.error) return json({ error: "metadata_save_failed" }, 500);
    await admin.from("audit_events").insert({
      tenant_id: job.tenant_id,
      actor_user_id: auth.user.id,
      event_type: action === "generate" ? "customer_ai_seo_generated" : "customer_seo_metadata_saved",
      details: { upload_job_id: jobId },
    });
    return json({ success: true, metadata });
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    if (message === "missing_configuration") return json({ error: "ai_not_configured" }, 503);
    return json({ error: "seo_request_failed" }, 502);
  }
});
