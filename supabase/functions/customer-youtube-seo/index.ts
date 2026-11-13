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
  return [...new Set(value.map((x) => String(x).trim()).filter(Boolean))].slice(0, max);
}
function normalizeHashtags(value: unknown, max: number): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of value) {
    const tag = String(item).replace(/^#+/, "").trim()
      .replace(/\s+/g, "_").replace(/[^\p{L}\p{N}_]/gu, "");
    const key = tag.toLowerCase();
    if (!tag || seen.has(key)) continue;
    seen.add(key);
    result.push(tag);
    if (result.length >= max) break;
  }
  return result;
}
async function uploadVideoToGemini(apiKey: string, bytes: Uint8Array, mime: string, name: string) {
  const start = await fetch("https://generativelanguage.googleapis.com/upload/v1beta/files", {
    method: "POST",
    headers: {
      "x-goog-api-key": apiKey,
      "X-Goog-Upload-Protocol": "resumable",
      "X-Goog-Upload-Command": "start",
      "X-Goog-Upload-Header-Content-Length": String(bytes.byteLength),
      "X-Goog-Upload-Header-Content-Type": mime,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ file: { display_name: name.slice(0, 100) } }),
  });
  if (!start.ok) throw new Error("gemini_file_start_failed");
  const uploadUrl = start.headers.get("x-goog-upload-url") ?? start.headers.get("location");
  if (!uploadUrl || !uploadUrl.startsWith("https://")) throw new Error("gemini_upload_url_missing");
  const uploaded = await fetch(uploadUrl, {
    method: "POST",
    headers: {
      "x-goog-api-key": apiKey,
      "X-Goog-Upload-Offset": "0",
      "X-Goog-Upload-Command": "upload, finalize",
      "Content-Length": String(bytes.byteLength),
    },
    body: bytes,
  });
  if (!uploaded.ok) throw new Error("gemini_file_upload_failed");
  const payload = await uploaded.json();
  const file = payload.file ?? payload;
  if (!file.name || !file.uri) throw new Error("gemini_file_reference_missing");
  return { name: String(file.name), uri: String(file.uri), state: String(file.state ?? "PROCESSING") };
}
async function waitForGeminiFile(apiKey: string, fileName: string) {
  for (let attempt = 0; attempt < 30; attempt++) {
    const response = await fetch(
      "https://generativelanguage.googleapis.com/v1beta/" + fileName,
      { headers: { "x-goog-api-key": apiKey } },
    );
    if (!response.ok) throw new Error("gemini_file_status_failed");
    const payload = await response.json();
    const state = String(payload.state ?? payload.file?.state ?? "");
    if (state === "ACTIVE") return;
    if (state === "FAILED") throw new Error("gemini_video_processing_failed");
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  throw new Error("gemini_video_processing_timeout");
}
async function deleteGeminiFile(apiKey: string, fileName: string) {
  try {
    await fetch("https://generativelanguage.googleapis.com/v1beta/" + fileName, {
      method: "DELETE",
      headers: { "x-goog-api-key": apiKey },
    });
  } catch {
    // Temporary Gemini files are best-effort deleted after metadata generation.
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  let geminiFileName = "";
  let geminiKey = "";
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
      .select("id,tenant_id,video_title,status,storage_object_path,mime_type,file_size_bytes")
      .eq("id", jobId).maybeSingle();
    if (jobError || !job) return json({ error: "video_not_found" }, 404);
    const { data: membership } = await admin.from("tenant_memberships")
      .select("tenant_id").eq("tenant_id", job.tenant_id).eq("user_id", auth.user.id)
      .eq("membership_role", "owner").maybeSingle();
    if (!membership) return json({ error: "workspace_owner_required" }, 403);
    const { data: tenantStatus } = await admin.from("tenants").select("status").eq("id", job.tenant_id).maybeSingle();
    if (tenantStatus?.status !== "active") return json({ error: "workspace_not_active" }, 403);
    const { data: channelConnection } = await admin.schema("private").from("youtube_connections")
      .select("channel_title").eq("tenant_id", job.tenant_id).is("revoked_at", null)
      .order("connected_at", { ascending: false }).limit(1).maybeSingle();
    const channelName = cleanText(channelConnection?.channel_title, 120) || "the creator's YouTube channel";
    if (!["received", "uploaded_private", "awaiting_approval", "approved"].includes(job.status)) {
      return json({ error: "video_not_ready_for_metadata" }, 409);
    }

    let metadata: Record<string, unknown>;
    if (action === "generate") {
      geminiKey = required("GEMINI_API_KEY");
      if (!job.storage_object_path || !["video/mp4", "video/quicktime", "video/webm"].includes(String(job.mime_type))) {
        return json({ error: "video_file_unavailable_or_unsupported" }, 409);
      }
      const { data: videoBlob, error: storageError } = await admin.storage
        .from("customer-video-intake").download(job.storage_object_path);
      if (storageError || !videoBlob) return json({ error: "video_file_unavailable" }, 409);
      if (videoBlob.size !== Number(job.file_size_bytes) || videoBlob.size > 104857600) {
        return json({ error: "video_file_size_mismatch" }, 409);
      }
      const videoBytes = new Uint8Array(await videoBlob.arrayBuffer());
      const geminiFile = await uploadVideoToGemini(
        geminiKey, videoBytes, String(job.mime_type), String(job.video_title ?? "creator-video"),
      );
      geminiFileName = geminiFile.name;
      await waitForGeminiFile(geminiKey, geminiFileName);
      const language = cleanText(body.language, 40) || "Telugu";
      const prompt = `You are an expert YouTube SEO editor. Watch and listen to the attached complete video. Identify the actual scenes, actions, spoken dialogue, language, mood, subject and context. Base every metadata field on what is genuinely visible or audible; do not invent events or claims. Produce engaging, searchable metadata for the creator's own YouTube channel.
Channel identity: ${channelName}. Use the channel name naturally when it improves branding, but do not force it into every title or tag.\nOutput language/script: ${language}.
Return JSON only with this exact shape:
{"title":"best YouTube title","title_options":["five different title options"],"description":"SEO-friendly description up to 4500 characters; do not include hashtags because they are returned separately","tags":["12 to 18 short relevant YouTube search tags"],"hashtags":["exactly 5 relevant hashtags without #"],"caption":"short social caption","youtube_caption":"YouTube caption","instagram_caption":"Instagram caption","keywords":["SEO keywords"],"category":"YouTube category"}
Rules: return exactly 5 distinct title_options; title <=100 chars; description <=4500 chars and must not contain hashtags; tags 12–18 and total tag characters <=450; exactly 5 hashtags in the separate hashtags array; caption, youtube_caption and instagram_caption <=1000 chars each; keywords <=20; category must be a valid YouTube category label. Use the requested language/script. Tags are concise search phrases, not hashtag strings. Hashtags must be relevant, avoid generic spam. Do not claim you heard dialogue unless it is audible.`;
      const response = await fetch(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-goog-api-key": geminiKey },
          body: JSON.stringify({
            contents: [{ role: "user", parts: [
              { fileData: { mimeType: String(job.mime_type), fileUri: geminiFile.uri } },
              { text: prompt },
            ] }],
            generationConfig: { responseMimeType: "application/json", temperature: 0.6, maxOutputTokens: 1800 },
          }),
        },
      );
      if (!response.ok) {
        const status = response.status;
        return json({ error: status === 429 || status === 503 ? "ai_temporarily_busy" : "ai_generation_failed", provider_status: status }, 502);
      }
      const generated = await response.json();
      const text = generated?.candidates?.[0]?.content?.parts?.map((p: {text?: string}) => p.text ?? "").join("") ?? "";
      const parsed = JSON.parse(text.replace(/^\x60\x60\x60(?:json)?/i, "").replace(/\x60\x60\x60$/i, "").trim());
      metadata = {
        title: cleanText(parsed.title, 100),
        description: cleanText(parsed.description, 5000),
        tags: normalizeTags(parsed.tags, 18),
        hashtags: normalizeHashtags(parsed.hashtags, 5),
        caption: cleanText(parsed.caption, 2200),
        metadata_details: {
          title_options: normalizeTags(parsed.title_options, 5),
          youtube_caption: cleanText(parsed.youtube_caption, 2200) || cleanText(parsed.caption, 2200),
          instagram_caption: cleanText(parsed.instagram_caption, 2200),
          keywords: normalizeTags(parsed.keywords, 30),
          category: cleanText(parsed.category, 80) || "Entertainment",
        },
      };
      const generatedTags = metadata.tags as string[];
      const generatedHashtags = metadata.hashtags as string[];
      const generatedTitles = (metadata.metadata_details as Record<string, unknown>).title_options as string[];
      const generatedTagLength = generatedTags.reduce((total, tag) => total + tag.length, 0);
      const uniqueHashtags = new Set(generatedHashtags.map((tag) => tag.toLowerCase()));
      const uniqueTitles = new Set(generatedTitles.map((title) => title.toLowerCase()));
      if (!metadata.title) return json({ error: "ai_returned_empty_metadata" }, 502);
      if (generatedTags.length < 12 || generatedTagLength > 450) {
        return json({ error: "ai_returned_invalid_tags" }, 502);
      }
      if (generatedHashtags.length !== 5 || uniqueHashtags.size !== 5 ||
          generatedTitles.length !== 5 || uniqueTitles.size !== 5) {
        return json({ error: "ai_returned_incomplete_metadata" }, 502);
      }
    } else {
      metadata = {
        title: cleanText(body.title, 100),
        description: cleanText(body.description, 5000),
        tags: normalizeTags(body.tags, 100),
        hashtags: normalizeHashtags(body.hashtags, 30),
        caption: cleanText(body.caption, 2200),
        metadata_details: {
          title_options: normalizeTags(body.metadata_details?.title_options, 5),
          youtube_caption: cleanText(body.metadata_details?.youtube_caption, 2200),
          instagram_caption: cleanText(body.metadata_details?.instagram_caption, 2200),
          keywords: normalizeTags(body.metadata_details?.keywords, 30),
          category: cleanText(body.metadata_details?.category, 80),
        },
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
      metadata_details: metadata.metadata_details ?? {},
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
      details: { upload_job_id: jobId, analyzed_uploaded_video: action === "generate" },
    });
    return json({ success: true, metadata, analyzed_uploaded_video: action === "generate" });
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    if (message === "missing_configuration") return json({ error: "ai_not_configured" }, 503);
    return json({ error: "seo_request_failed" }, 502);
  } finally {
    if (geminiFileName && geminiKey) await deleteGeminiFile(geminiKey, geminiFileName);
  }
});
