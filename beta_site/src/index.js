import { RELEASE } from "./release.js";

const SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Resource-Policy": "same-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-Robots-Tag": "noindex, nofollow, noarchive",
};

const RETENTION_DAYS = 30;
const MAX_CONFIRM_BYTES = 1024;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...SECURITY_HEADERS, "Content-Type": "application/json; charset=utf-8" },
  });
}

function cutoff(now = new Date()) {
  return new Date(now.getTime() - RETENTION_DAYS * 24 * 60 * 60 * 1000).toISOString();
}

function isSameOrigin(request) {
  return request.headers.get("Origin") === new URL(request.url).origin;
}

async function readSmallText(request, maxBytes) {
  const declaredLength = request.headers.get("Content-Length");
  if (declaredLength !== null) {
    const parsedLength = Number(declaredLength);
    if (!Number.isInteger(parsedLength) || parsedLength < 0 || parsedLength > maxBytes) {
      return null;
    }
  }
  if (!request.body) return "";

  const reader = request.body.getReader();
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > maxBytes) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

async function stats(env, now = new Date()) {
  const row = await env.DB.prepare(
    "SELECT COUNT(*) AS downloads, COUNT(confirmed_at) AS confirmed " +
      "FROM install_sessions WHERE release_version = ? AND downloaded_at >= ?",
  ).bind(RELEASE.version, cutoff(now)).first();
  return {
    downloads: Number(row?.downloads || 0),
    confirmedInstallations: Number(row?.confirmed || 0),
  };
}

async function recordDownload(env) {
  const id = crypto.randomUUID();
  await env.DB.prepare(
    "INSERT INTO install_sessions (id, downloaded_at, release_version) VALUES (?, ?, ?)",
  ).bind(id, new Date().toISOString(), RELEASE.version).run();
  return id;
}

async function download(request, env) {
  const assetUrl = new URL(`/downloads/${RELEASE.archive}`, request.url);
  const asset = await env.ASSETS.fetch(new Request(assetUrl));
  if (!asset.ok) return json({ error: "The beta package is temporarily unavailable." }, 503);

  let installSession = "";
  try {
    installSession = await recordDownload(env);
  } catch {
    // The scanner must remain downloadable if the anonymous counter is unavailable.
  }

  const headers = new Headers(asset.headers);
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) headers.set(name, value);
  headers.set("Content-Disposition", `attachment; filename="${RELEASE.archive}"`);
  headers.set("X-Archive-SHA256", RELEASE.archiveSha256);
  if (installSession) headers.set("X-Install-Session", installSession);
  return new Response(asset.body, { status: 200, headers });
}

async function confirm(request, env) {
  let body;
  try {
    const rawBody = await readSmallText(request, MAX_CONFIRM_BYTES);
    if (rawBody === null) return json({ error: "Invalid request." }, 413);
    body = JSON.parse(rawBody);
  } catch {
    return json({ error: "Invalid request." }, 400);
  }
  const id = typeof body?.installSession === "string" ? body.installSession : "";
  if (!UUID_PATTERN.test(id)) return json({ error: "Invalid install session." }, 400);

  const result = await env.DB.prepare(
    "UPDATE install_sessions SET confirmed_at = COALESCE(confirmed_at, ?) " +
      "WHERE id = ? AND release_version = ? AND downloaded_at >= ?",
  ).bind(new Date().toISOString(), id, RELEASE.version, cutoff()).run();
  if (!result.meta?.changes) {
    const existing = await env.DB.prepare(
      "SELECT confirmed_at FROM install_sessions " +
        "WHERE id = ? AND release_version = ? AND downloaded_at >= ?",
    ).bind(id, RELEASE.version, cutoff()).first();
    if (!existing) return json({ error: "Install session not found or expired." }, 404);
  }
  return json({ ok: true, ...(await stats(env)) });
}

async function pruneOldSessions(env, now = new Date()) {
  await env.DB.prepare(
    "DELETE FROM install_sessions WHERE downloaded_at < ?",
  ).bind(cutoff(now)).run();
}

async function assetResponse(request, env, path) {
  const response = await env.ASSETS.fetch(new Request(new URL(path, request.url)));
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) headers.set(name, value);
  return new Response(response.body, { status: response.status, headers });
}

async function handle(request, env) {
  const url = new URL(request.url);

  if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) {
    return assetResponse(request, env, "/index.html");
  }
  if (request.method === "GET" && url.pathname === "/app.js") {
    return assetResponse(request, env, "/app.js");
  }
  if (request.method === "GET" && url.pathname === "/api/info") {
    return json(RELEASE);
  }
  if (request.method === "GET" && url.pathname === "/api/stats") {
    try {
      return json(await stats(env));
    } catch {
      return json({ error: "Activity counters are temporarily unavailable." }, 503);
    }
  }
  if (request.method === "POST" && (url.pathname === "/api/download" || url.pathname === "/api/confirm")) {
    if (!isSameOrigin(request)) return json({ error: "Cross-origin request rejected." }, 403);
    if (url.pathname === "/api/download") return download(request, env);
    return confirm(request, env);
  }
  if (url.pathname.startsWith("/api/")) return json({ error: "Not found." }, 404);
  return new Response("Not found", { status: 404, headers: SECURITY_HEADERS });
}

export default {
  async fetch(request, env) {
    try {
      return await handle(request, env);
    } catch {
      return json({ error: "The beta service encountered an unexpected error." }, 500);
    }
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(pruneOldSessions(env));
  },
};

export { cutoff, handle, isSameOrigin, pruneOldSessions, recordDownload, stats };
