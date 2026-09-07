import { env } from "cloudflare:workers";
import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import landingHtml from "../public/index.html?raw";
import appScript from "../public/app.js?raw";
import worker, { cutoff, isSameOrigin, pruneOldSessions } from "../src/index.js";
import { RELEASE } from "../src/release.js";

const ORIGIN = "https://beta.example.test";
const ARCHIVE_BYTES = new TextEncoder().encode("deterministic-test-archive");

const assets = {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === `/downloads/${RELEASE.archive}`) {
      return new Response(ARCHIVE_BYTES, {
        headers: { "Content-Type": "application/zip" },
      });
    }
    if (path === "/index.html") return new Response(landingHtml);
    if (path === "/app.js") return new Response(appScript);
    return new Response("missing", { status: 404 });
  },
};

const testEnv = () => ({ DB: env.DB, ASSETS: assets });

async function request(path, init = {}) {
  const context = createExecutionContext();
  const response = await worker.fetch(new Request(`${ORIGIN}${path}`, init), testEnv(), context);
  await waitOnExecutionContext(context);
  return response;
}

beforeEach(async () => {
  await env.DB.prepare("DELETE FROM install_sessions").run();
});

describe("researcher beta Worker", () => {
  it("serves public landing assets with hardened headers", async () => {
    const landing = await request("/");
    expect(landing.status).toBe(200);
    const html = await landing.text();
    expect(html).toContain("<!doctype html>");
    expect(html).toContain("Run it on your own dataset");
    expect(html).toContain("How it works");
    expect(html).toContain("First download the package in this tab");
    expect(html).toContain("1. Did the scan complete?");
    expect(html).toContain("2. What needs review?");
    expect(html).toContain("Open feedback email");
    expect(html).toContain("[hidden] { display:none !important; }");
    expect(html.indexOf("Download the beta package")).toBeLessThan(html.indexOf("Run it on your own dataset"));
    expect(html).toContain("The included synthetic demo is an optional installation check");
    expect(html.indexOf("Run it on your own dataset")).toBeLessThan(html.indexOf("synthetic demo"));
    expect(landing.headers.get("X-Frame-Options")).toBe("DENY");
    expect(landing.headers.get("Cache-Control")).toBe("no-store");

    const script = await request("/app.js");
    expect(script.status).toBe(200);
    const javascript = await script.text();
    expect(javascript).toContain('downloadButton.textContent = downloadedInTab ? "Download again"');
    expect(javascript).toContain("Installation confirmed for this download session");
    expect(javascript).toContain("retryLoadButton.addEventListener");
    expect(javascript).toContain("confirmStatus.focus()");
    expect(javascript).toContain("tableWrap.scrollWidth > tableWrap.clientWidth");
  });

  it("exposes one internally consistent release description", async () => {
    const response = await request("/api/info");
    const info = await response.json();
    expect(response.status).toBe(200);
    expect(info.version).toBe("0.3.0b1");
    expect(info.tag).toBe("v0.3.0b1");
    expect(info.archive).toBe("neurodata-researcher-beta-0.3.0b1-r2.zip");
    expect(info.archiveSha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it("rejects cross-origin counter mutations", async () => {
    expect(isSameOrigin(new Request(`${ORIGIN}/api/download`))).toBe(false);
    const response = await request("/api/download", {
      method: "POST",
      headers: { Origin: "https://other.example.test" },
    });
    expect(response.status).toBe(403);
    expect(await env.DB.prepare("SELECT COUNT(*) AS count FROM install_sessions").first()).toEqual({ count: 0 });
  });

  it("runs the complete download and idempotent confirmation path against D1", async () => {
    const download = await request("/api/download", {
      method: "POST",
      headers: { Origin: ORIGIN },
    });
    expect(download.status).toBe(200);
    expect(new Uint8Array(await download.arrayBuffer())).toEqual(ARCHIVE_BYTES);
    expect(download.headers.get("Content-Disposition")).toContain(RELEASE.archive);
    expect(download.headers.get("X-Archive-SHA256")).toBe(RELEASE.archiveSha256);
    const installSession = download.headers.get("X-Install-Session");
    expect(installSession).toMatch(/^[0-9a-f-]{36}$/);

    const afterDownload = await request("/api/stats");
    expect(await afterDownload.json()).toEqual({ downloads: 1, confirmedInstallations: 0 });

    const confirmation = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: JSON.stringify({ installSession }),
    });
    expect(confirmation.status).toBe(200);
    expect(await confirmation.json()).toEqual({ ok: true, downloads: 1, confirmedInstallations: 1 });

    const repeat = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: JSON.stringify({ installSession }),
    });
    expect(repeat.status).toBe(200);
    expect(await repeat.json()).toEqual({ ok: true, downloads: 1, confirmedInstallations: 1 });
  });

  it("returns precise errors for invalid and expired confirmation sessions", async () => {
    const invalid = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: JSON.stringify({ installSession: "not-a-session" }),
    });
    expect(invalid.status).toBe(400);

    const expired = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: JSON.stringify({ installSession: "11111111-1111-4111-8111-111111111111" }),
    });
    expect(expired.status).toBe(404);
    expect(await expired.json()).toEqual({ error: "Install session not found or expired." });

    const oldSession = "22222222-2222-4222-8222-222222222222";
    await env.DB.prepare(
      "INSERT INTO install_sessions (id, downloaded_at, release_version) VALUES (?, ?, ?)",
    ).bind(oldSession, "2025-01-01T00:00:00.000Z", RELEASE.version).run();
    const oldConfirmation = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: JSON.stringify({ installSession: oldSession }),
    });
    expect(oldConfirmation.status).toBe(404);

    const oversized = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: JSON.stringify({ installSession: "x".repeat(2_000) }),
    });
    expect(oversized.status).toBe(413);
    expect(await oversized.json()).toEqual({ error: "Invalid request." });

    const chunks = [new Uint8Array(700), new Uint8Array(700)];
    const chunked = new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      },
    });
    const chunkedOversized = await request("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: ORIGIN },
      body: chunked,
    });
    expect(chunkedOversized.status).toBe(413);
    expect(await chunkedOversized.json()).toEqual({ error: "Invalid request." });
  });

  it("counts only current-version activity inside the 30-day window", async () => {
    const recent = new Date().toISOString();
    const old = "2025-01-01T00:00:00.000Z";
    await env.DB.batch([
      env.DB.prepare("INSERT INTO install_sessions (id, downloaded_at, confirmed_at, release_version) VALUES (?, ?, ?, ?)")
        .bind("11111111-1111-4111-8111-111111111111", recent, recent, RELEASE.version),
      env.DB.prepare("INSERT INTO install_sessions (id, downloaded_at, confirmed_at, release_version) VALUES (?, ?, ?, ?)")
        .bind("22222222-2222-4222-8222-222222222222", old, old, RELEASE.version),
      env.DB.prepare("INSERT INTO install_sessions (id, downloaded_at, confirmed_at, release_version) VALUES (?, ?, ?, ?)")
        .bind("33333333-3333-4333-8333-333333333333", recent, recent, "0.2.1b1"),
    ]);

    const response = await request("/api/stats");
    expect(await response.json()).toEqual({ downloads: 1, confirmedInstallations: 1 });
  });

  it("streams the archive even when anonymous tracking is unavailable", async () => {
    const failingDb = {
      prepare() {
        throw new Error("D1 unavailable");
      },
    };
    const response = await worker.fetch(
      new Request(`${ORIGIN}/api/download`, { method: "POST", headers: { Origin: ORIGIN } }),
      { DB: failingDb, ASSETS: assets },
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("X-Install-Session")).toBeNull();
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(ARCHIVE_BYTES);
  });

  it("prunes old rows only from the scheduled handler", async () => {
    const recent = new Date().toISOString();
    await env.DB.batch([
      env.DB.prepare("INSERT INTO install_sessions (id, downloaded_at, release_version) VALUES (?, ?, ?)")
        .bind("11111111-1111-4111-8111-111111111111", "2025-01-01T00:00:00.000Z", RELEASE.version),
      env.DB.prepare("INSERT INTO install_sessions (id, downloaded_at, release_version) VALUES (?, ?, ?)")
        .bind("22222222-2222-4222-8222-222222222222", recent, RELEASE.version),
    ]);
    expect(cutoff(new Date("2026-09-03T00:00:00.000Z"))).toBe("2026-08-04T00:00:00.000Z");

    const context = createExecutionContext();
    await worker.scheduled({}, testEnv(), context);
    await waitOnExecutionContext(context);

    const rows = await env.DB.prepare("SELECT id FROM install_sessions ORDER BY id").all();
    expect(rows.results).toEqual([{ id: "22222222-2222-4222-8222-222222222222" }]);
  });

  it("supports direct deterministic cleanup checks", async () => {
    await pruneOldSessions(env, new Date("2026-09-03T00:00:00.000Z"));
    expect(cutoff(new Date("2026-09-03T00:00:00.000Z"))).toBe("2026-08-04T00:00:00.000Z");
  });
});
