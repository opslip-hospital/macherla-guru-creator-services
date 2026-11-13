import { createClient } from "npm:@supabase/supabase-js@2";

const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers });

function secret(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error("missing_configuration");
  return value;
}
function decodeHex(value: string): Uint8Array {
  if (!/^(?:[0-9a-f]{2})+$/i.test(value)) throw new Error("invalid_encrypted_token");
  return new Uint8Array(value.match(/.{2}/g)!.map((part) => parseInt(part, 16)));
}
async function decryptRefreshToken(hex: string, base64Key: string): Promise<string> {
  const packed = decodeHex(hex);
  if (packed.length < 29) throw new Error("invalid_encrypted_token");
  const keyBytes = Uint8Array.from(atob(base64Key), (c) => c.charCodeAt(0));
  if (keyBytes.length !== 32) throw new Error("invalid_encryption_key");
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "AES-GCM" }, false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: packed.slice(0, 12) },
    key,
    packed.slice(12),
  );
  return new TextDecoder().decode(plain);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  let claimedJobId: string | null = null;
  let uploadedVideoId: string | null = null;
  let admin: ReturnType<typeof createClient> | null = null;
  try {
    const supabaseUrl = secret("SUPABASE_URL");
    const publishable = Deno.env.get("SUPABASE_PUBLISHABLE_KEY")
      ?? Deno.env.get("SUPABASE_ANON_KEY")
      ?? (() => { throw new Error("missing_configuration"); })();
    const serviceKey = Deno.env.get("SUPABASE_SECRET_KEY")
      ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
      ?? (() => { throw new Error("missing_configuration"); })();
    const bearer = (req.headers.get("Authorization") ?? "").match(/^Bearer\s+(.+)$/i)?.[1];
    if (!bearer) return json({ error: "authentication_required" }, 401);

    const userClient = createClient(supabaseUrl, publishable, {
      global: { headers: { Authorization: `Bearer ${bearer}` } },
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const { data: authData, error: authError } = await userClient.auth.getUser(bearer);
    if (authError || !authData.user) return json({ error: "invalid_session" }, 401);

    const body = await req.json().catch(() => ({}));
    const jobId = typeof body.job_id === "string" ? body.job_id : "";
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(jobId)) {
      return json({ error: "invalid_job_id" }, 400);
    }

    admin = createClient(supabaseUrl, serviceKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const { data: claimed, error: claimError } = await userClient.rpc("claim_youtube_upload_job", {
      p_job_id: jobId,
      p_admin_user_id: authData.user.id,
    });
    if (claimError || !claimed) return json({ error: "job_not_ready_or_channel_not_connected" }, 409);
    claimedJobId = jobId;

    const refreshToken = await decryptRefreshToken(
      claimed.encrypted_refresh_token_hex,
      secret("TOKEN_ENCRYPTION_KEY"),
    );
    const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: secret("GOOGLE_CLIENT_ID"),
        client_secret: secret("GOOGLE_CLIENT_SECRET"),
        refresh_token: refreshToken,
        grant_type: "refresh_token",
      }),
    });
    if (!tokenResponse.ok) throw new Error("google_token_refresh_failed");
    const tokenData = await tokenResponse.json();
    if (!tokenData.access_token) throw new Error("google_access_token_missing");

    const { data: videoBlob, error: storageError } = await admin.storage
      .from("customer-video-intake")
      .download(claimed.storage_object_path);
    if (storageError || !videoBlob) throw new Error("private_video_file_unavailable");
    if (videoBlob.size !== Number(claimed.file_size_bytes) || videoBlob.size > 104857600) {
      throw new Error("video_file_size_mismatch");
    }
    const videoBytes = new Uint8Array(await videoBlob.arrayBuffer());

    const hashtags = Array.isArray(claimed.hashtags)
      ? claimed.hashtags.map((tag: unknown) => String(tag).replace(/^#+/, "").trim()).filter(Boolean)
      : [];
    let description = String(claimed.description ?? "");
    const hashtagLine = hashtags.map((tag: string) => `#${tag}`).join(" ");
    if (hashtagLine && !description.includes(hashtagLine)) {
      description = [description, hashtagLine].filter(Boolean).join("\n\n");
    }
    description = description.slice(0, 5000);

    const rawTags = Array.isArray(claimed.tags) ? claimed.tags.map((tag: unknown) => String(tag).trim()).filter(Boolean) : [];
    const tags: string[] = [];
    let tagLength = 0;
    for (const tag of rawTags) {
      if (tagLength + tag.length > 500) continue;
      tags.push(tag);
      tagLength += tag.length;
    }
    const title = String(claimed.video_title ?? "Creator video").slice(0, 100);
    const categoryName = String(claimed.metadata_details?.category ?? "").toLowerCase();
    const categoryIds: Record<string, string> = {
      "film & animation": "1", "autos & vehicles": "2", "music": "10",
      "pets & animals": "15", "sports": "17", "short movies": "18",
      "travel & events": "19", "gaming": "20", "videoblogging": "21",
      "people & blogs": "22", "comedy": "23", "entertainment": "24",
      "news & politics": "25", "howto & style": "26", "education": "27",
      "science & technology": "28", "nonprofits & activism": "29",
    };
    const categoryId = categoryIds[categoryName] ?? "22";
    const initiate = await fetch(
      "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
          "Content-Type": "application/json; charset=UTF-8",
          "X-Upload-Content-Type": String(claimed.mime_type),
          "X-Upload-Content-Length": String(videoBytes.byteLength),
        },
        body: JSON.stringify({
          snippet: { title, description, tags, categoryId },
          status: { privacyStatus: "private" },
        }),
      },
    );
    if (!initiate.ok) throw new Error("youtube_upload_session_failed");
    const uploadUrl = initiate.headers.get("Location");
    if (!uploadUrl || !uploadUrl.startsWith("https://www.googleapis.com/upload/youtube/")) {
      throw new Error("youtube_upload_url_invalid");
    }
    const uploaded = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": String(claimed.mime_type), "Content-Length": String(videoBytes.byteLength) },
      body: videoBytes,
    });
    if (!uploaded.ok) throw new Error("youtube_private_upload_failed");
    const youtubeVideo = await uploaded.json();
    if (!youtubeVideo.id) throw new Error("youtube_video_id_missing");
    uploadedVideoId = String(youtubeVideo.id);

    const { error: updateError } = await admin.from("upload_jobs").update({
      status: "uploaded_private",
      youtube_video_id: youtubeVideo.id,
      updated_at: new Date().toISOString(),
    }).eq("id", jobId).eq("status", "processing");
    if (updateError) throw new Error("job_status_update_failed");
    await admin.from("audit_events").insert({
      tenant_id: claimed.tenant_id,
      actor_user_id: authData.user.id,
      event_type: "youtube_video_uploaded_private",
      details: { upload_job_id: jobId, youtube_video_id: youtubeVideo.id, channel_id: claimed.channel_id },
    });
    return json({
      success: true,
      status: "uploaded_private",
      youtube_video_id: youtubeVideo.id,
      youtube_url: `https://www.youtube.com/watch?v=${youtubeVideo.id}`,
      message: "Video uploaded as private. The channel owner can now publish or schedule it.",
    });
  } catch {
    if (admin && claimedJobId) {
      if (uploadedVideoId) {
        // YouTube accepted the upload; preserve its ID and private state if dashboard sync failed.
        await admin.from("upload_jobs").update({
          status: "uploaded_private",
          youtube_video_id: uploadedVideoId,
          updated_at: new Date().toISOString(),
        }).eq("id", claimedJobId).eq("status", "processing");
      } else {
        await admin.from("upload_jobs").update({
          status: "failed",
          updated_at: new Date().toISOString(),
        }).eq("id", claimedJobId).eq("status", "processing");
      }
    }
    return json({
      error: uploadedVideoId ? "youtube_upload_status_sync_failed" : "private_youtube_upload_failed",
      message: uploadedVideoId
        ? "YouTube received the private video, but dashboard status sync needs attention. Check the video in YouTube Studio before retrying."
        : "The private YouTube upload could not be completed. Check the channel connection and retry after reviewing the job.",
    }, 502);
  }
});
