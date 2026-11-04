import { env } from "cloudflare:workers";
import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { beforeEach, describe, expect, it, vi } from "vitest";
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

const testEnv = (rateLimitSuccess = true) => ({
  DB: env.DB,
  ASSETS: assets,
  DOWNLOAD_RATE_LIMITER: { async limit() { return { success: rateLimitSuccess }; } },
});

async function request(path, init = {}, runtimeEnv = testEnv()) {
  const context = createExecutionContext();
  const response = await worker.fetch(new Request(`${ORIGIN}${path}`, init), runtimeEnv, context);
  await waitOnExecutionContext(context);
  return response;
}

beforeEach(async () => {
  await env.DB.prepare("DELETE FROM install_sessions").run();
});

describe("researcher beta Worker", () => {
  it("limits public stats before touching D1", async () => {
    const response = await request("/api/stats", {}, {
      ...testEnv(false),
      DB: { prepare() { throw new Error("Stats reached D1 before its limit"); } },
    });
    expect(response.status).toBe(429);
  });

  it("acknowledges a persisted confirmation even if aggregate reads fail", async () => {
    const download = await request("/api/download", { method: "POST", headers: { Origin: ORIGIN } });
    const session = download.headers.get("X-Install-Session");
    const runtime = {
      ...testEnv(),
      DB: {
        prepare(sql) {
          if (sql.startsWith("SELECT COUNT")) {
            return { bind() { return this; }, async first() { throw new Error("Stats unavailable"); } };
          }
          return env.DB.prepare(sql);
        },
      },
    };
    const response = await request("/api/confirm", {
      method: "POST", headers: { Origin: ORIGIN }, body: JSON.stringify({ installSession: session }),
    }, runtime);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true });
    const row = await env.DB.prepare("SELECT confirmed_at FROM install_sessions WHERE id = ?").bind(session).first();
    expect(row.confirmed_at).not.toBeNull();
  });
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
    expect(javascript).toContain("window.requestAnimationFrame(updateTableFocus)");
    expect(html).toContain("Optional: confirm the installation");
    expect(html).toContain("Starting a download stores a random session ID");
    expect(html).toContain("data-kit-revision");
    expect(html).toContain('data-copy-install="formats"');
    expect(html).toContain('data-label="Inspection boundary"');
    expect(html).toContain("word-break:break-word");
    expect(javascript).toContain("navigator.clipboard.writeText(command)");
  });

  it("exposes one internally consistent release description", async () => {
    const response = await request("/api/info");
    const info = await response.json();
    expect(response.status).toBe(200);
    expect(info.version).toBe("0.3.0b4");
    expect(info.tag).toBe("v0.3.0b4");
    expect(info.kitRevision).toBe("r1");
    expect(info.archive).toBe("neurodata-researcher-beta-0.3.0b4-r1.zip");
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

  it("rate-limits repeated download attempts before writing to D1", async () => {
    const response = await request("/api/download", {
      method: "POST",
      headers: { Origin: ORIGIN },
    }, testEnv(false));
    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({
      error: "Too many attempts. Please wait a minute and try again.",
    });
    expect(await env.DB.prepare("SELECT COUNT(*) AS count FROM install_sessions").first()).toEqual({ count: 0 });
  });

  it("uses separate per-client buckets for downloads and confirmations", async () => {
    const keys = [];
    const limitedEnv = {
      ...testEnv(),
      DOWNLOAD_RATE_LIMITER: {
        async limit({ key }) {
          keys.push(key);
          return { success: true };
        },
      },
    };
    const first = await request("/api/download", {
      method: "POST",
      headers: { Origin: ORIGIN, "CF-Connecting-IP": "192.0.2.1" },
    }, limitedEnv);
    const second = await request("/api/download", {
      method: "POST",
      headers: { Origin: ORIGIN, "CF-Connecting-IP": "192.0.2.2" },
    }, limitedEnv);
    await request("/api/confirm", {
      method: "POST",
      headers: { Origin: ORIGIN, "CF-Connecting-IP": "192.0.2.1" },
      body: JSON.stringify({ installSession: first.headers.get("X-Install-Session") }),
    }, limitedEnv);
    expect(second.status).toBe(200);
    expect(keys).toHaveLength(3);
    expect(keys[0]).not.toBe(keys[1]);
    expect(keys[0]).not.toBe(keys[2]);
  });

  it("rejects confirmation before D1 access when its rate limit fails", async () => {
    const response = await request("/api/confirm", {
      method: "POST",
      headers: { Origin: ORIGIN },
      body: JSON.stringify({ installSession: "11111111-1111-4111-8111-111111111111" }),
    }, testEnv(false));
    expect(response.status).toBe(429);
    expect(await env.DB.prepare("SELECT COUNT(*) AS count FROM install_sessions").first()).toEqual({ count: 0 });
  });

  it("does not bypass abuse control when the limiter is unavailable", async () => {
    const unavailable = {
      ...testEnv(),
      DOWNLOAD_RATE_LIMITER: { async limit() { throw new Error("limiter unavailable"); } },
    };
    for (const path of ["/api/download", "/api/confirm"]) {
      const response = await request(path, {
        method: "POST",
        headers: { Origin: ORIGIN },
      }, unavailable);
      expect(response.status).toBe(503);
    }
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
      { DB: failingDb, ASSETS: assets, DOWNLOAD_RATE_LIMITER: testEnv().DOWNLOAD_RATE_LIMITER },
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

// Exercise the actual browser script without an extra DOM dependency or network.
async function frontend(fetcher, storedSession = null) {
  const nodes = new Map();
  const handlers = new Map();
  const saved = [];
  const storage = new Map(storedSession ? [["neurodataBetaInstallSession", JSON.stringify(storedSession)]] : []);
  function element(name) {
    if (!nodes.has(name)) nodes.set(name, {
      dataset: {}, disabled: name === "#download", checked: false, textContent: "", hidden: false,
      classList: { toggle() {} }, setAttribute() {}, focus() {}, scrollWidth: 300, clientWidth: 300,
      addEventListener(type, handler) { handlers.set(`${name}:${type}`, handler); },
    });
    return nodes.get(name);
  }
  const document = {
    querySelector: element,
    querySelectorAll(selector) {
      if (selector === "[data-version]") return [element("#version")];
      if (selector === "[data-kit-revision]") return [element("#kit-revision")];
      if (selector === "[data-install]") {
        const command = element("#base-install");
        command.dataset.install = "base";
        return [command];
      }
      return [];
    },
    createElement() {
      return { click() { saved.push(this.download); }, remove() {} };
    },
    body: { append() {} },
  };
  const window = {
    location: { protocol: "https:" }, setTimeout() {}, addEventListener() {},
    requestAnimationFrame(callback) { callback(); },
    sessionStorage: {
      getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
  };
  new Function("document", "window", "fetch", "URL", appScript)(
    document, window, fetcher, { createObjectURL: () => "blob:synthetic", revokeObjectURL() {} },
  );
  await vi.waitFor(() => expect(element("#download").disabled).toBe(false));
  return { nodes, saved, storage, click: (id) => handlers.get(`${id}:click`)(),
    check() { element("#ran-check").checked = true; handlers.get("#ran-check:change")(); } };
}

const oldRelease = { ...RELEASE, archiveSha256: "a".repeat(64) };
function frontendFetch(downloadResponse, confirmResponse = () => Response.json({ ok: true })) {
  return async (path) => {
    if (path === "api/info") return Response.json(oldRelease);
    if (path === "api/stats") return Response.json({ downloads: 1, confirmedInstallations: 0 });
    if (path === "api/download") return downloadResponse();
    if (path === "api/confirm") return confirmResponse();
    throw new Error(`Unexpected local request: ${path}`);
  };
}

describe("researcher beta frontend", () => {
  it("unlocks confirmation after a verified download even while stats hangs", async () => {
    let finishStats;
    let statsCalls = 0;
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode("synthetic archive"))),
      (value) => value.toString(16).padStart(2, "0")).join("");
    const fallback = frontendFetch(() => new Response("synthetic archive", { headers: {
      "X-Archive-SHA256": digest, "X-Install-Session": "11111111-1111-4111-8111-111111111111",
    } }));
    const page = await frontend((path) => {
      if (path === "api/info") return Response.json({ ...oldRelease, archiveSha256: digest });
      if (path === "api/stats" && ++statsCalls > 1) return new Promise((resolve) => { finishStats = resolve; });
      return fallback(path);
    });
    const pending = page.click("#download");
    try {
      await vi.waitFor(() => {
        expect(page.saved).toEqual([RELEASE.archive]);
        expect(page.nodes.get("#ran-check").disabled).toBe(false);
        expect(page.nodes.get("#download").disabled).toBe(false);
      });
    } finally {
      if (finishStats) finishStats(new Response("unavailable", { status: 503 }));
      await pending;
    }
  });

  it("acknowledges a saved confirmation before optional stats finishes", async () => {
    let finishStats;
    let statsCalls = 0;
    const fallback = frontendFetch(() => new Response("unused"));
    const page = await frontend((path) => {
      if (path === "api/stats" && ++statsCalls > 1) return new Promise((resolve) => { finishStats = resolve; });
      return fallback(path);
    }, { id: "11111111-1111-4111-8111-111111111111", release: `${RELEASE.version}-${RELEASE.kitRevision}` });
    page.check();
    const pending = page.click("#confirm");
    try {
      await vi.waitFor(() => {
        expect(page.nodes.get("#confirm-status").textContent).toMatch(/recorded/);
        expect(page.nodes.get("#download").disabled).toBe(false);
        expect(page.storage.has("neurodataBetaInstallSession")).toBe(false);
      });
    } finally {
      if (finishStats) finishStats(new Response("unavailable", { status: 503 }));
      await pending;
    }
  });

  it("does not restore an older session after an untracked successful redownload", async () => {
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode("synthetic archive"))),
      (value) => value.toString(16).padStart(2, "0")).join("");
    const fallback = frontendFetch(() => new Response("synthetic archive", { headers: { "X-Archive-SHA256": digest } }));
    const fetcher = (path) => path === "api/info" ? Response.json({ ...oldRelease, archiveSha256: digest }) : fallback(path);
    const page = await frontend(fetcher,
      { id: "11111111-1111-4111-8111-111111111111", release: `${RELEASE.version}-${RELEASE.kitRevision}` });
    await page.click("#download");
    expect(page.saved).toEqual([RELEASE.archive]);
    expect(page.storage.has("neurodataBetaInstallSession")).toBe(false);
    const stored = page.storage.get("neurodataBetaInstallSession");
    const reloaded = await frontend(fetcher, stored ? JSON.parse(stored) : null);
    expect(reloaded.nodes.get("#ran-check").disabled).toBe(true);
  });

  it("restores the normal stats note when confirmation returns fresh counters", async () => {
    const fallback = frontendFetch(() => new Response("unused"),
      () => Response.json({ ok: true, downloads: 2, confirmedInstallations: 1 }));
    const page = await frontend((path) => path === "api/stats" ? new Response("unavailable", { status: 503 }) : fallback(path),
      { id: "11111111-1111-4111-8111-111111111111", release: `${RELEASE.version}-${RELEASE.kitRevision}` });
    await vi.waitFor(() => expect(page.nodes.get("#stats-note").textContent).toMatch(/temporarily unavailable/));
    page.check();
    await page.click("#confirm");
    expect(page.nodes.get("#downloads").textContent).toBe(2);
    expect(page.nodes.get("#confirmed").textContent).toBe(1);
    expect(page.nodes.get("#stats-note").textContent).toMatch(/indicative counters/);
  });

  it("refreshes release metadata before a successful retry of the new kit", async () => {
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode("synthetic next kit"))),
      (value) => value.toString(16).padStart(2, "0")).join("");
    const next = { ...oldRelease, version: "0.0.99", kitRevision: "r2", archive: "next-kit.zip", wheel: "next-wheel.whl", archiveSha256: digest };
    let infoCalls = 0;
    const fallback = frontendFetch(() => new Response("synthetic next kit", {
      headers: { "X-Archive-SHA256": digest, "X-Install-Session": "11111111-1111-4111-8111-111111111111" },
    }));
    const page = await frontend((path) => path === "api/info" ? Response.json(++infoCalls === 1 ? oldRelease : next) : fallback(path));
    await page.click("#download");
    expect(page.saved).toEqual([]);
    expect(page.nodes.get("#version").textContent).toBe("0.0.99");
    expect(page.nodes.get("#base-install").textContent).toContain("next-wheel.whl");
    await page.click("#download");
    expect(page.saved).toEqual(["next-kit.zip"]);
    expect(JSON.parse(page.storage.get("neurodataBetaInstallSession")).release).toBe("0.0.99-r2");
  });

  it("prevents confirmation while a download is pending", async () => {
    let finish;
    let confirmations = 0;
    const page = await frontend(frontendFetch(() => new Promise((resolve) => { finish = resolve; }),
      () => { confirmations++; return Response.json({ ok: true }); }),
    { id: "11111111-1111-4111-8111-111111111111", release: `${RELEASE.version}-${RELEASE.kitRevision}` });
    page.check();
    const pending = page.click("#download");
    expect(page.nodes.get("#confirm").disabled).toBe(true);
    await page.click("#confirm");
    expect(confirmations).toBe(0);
    finish(new Response("unavailable", { status: 503 }));
    await pending;
  });

  it("saves verified bytes under their release filename and keeps the confirmation session", async () => {
    const bytes = new TextEncoder().encode("synthetic archive");
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      (value) => value.toString(16).padStart(2, "0")).join("");
    const info = { ...oldRelease, archiveSha256: digest };
    const session = "11111111-1111-4111-8111-111111111111";
    const fallback = frontendFetch(() => new Response(bytes, {
      headers: { "X-Archive-SHA256": digest, "X-Install-Session": session },
    }));
    const page = await frontend((path) => path === "api/info" ? Response.json(info) : fallback(path));
    await page.click("#download");
    expect(page.saved).toEqual([RELEASE.archive]);
    expect(JSON.parse(page.storage.get("neurodataBetaInstallSession")).id).toBe(session);
    page.check();
    expect(page.nodes.get("#confirm").disabled).toBe(false);
  });

  it("does not save an archive from a newly deployed release under the old filename", async () => {
    const page = await frontend(frontendFetch(() => new Response("new release bytes", {
      headers: { "X-Archive-SHA256": "b".repeat(64) },
    })));
    await page.click("#download");
    expect(page.saved).toEqual([]);
    expect(page.nodes.get("#download-status").textContent).toMatch(/version changed/i);
  });

  it("does not save bytes that disagree with the declared archive digest", async () => {
    const page = await frontend(frontendFetch(() => new Response("corrupt bytes", {
      headers: { "X-Archive-SHA256": oldRelease.archiveSha256 },
    })));
    await page.click("#download");
    expect(page.saved).toEqual([]);
    expect(page.nodes.get("#download-status").textContent).toMatch(/integrity/i);
  });

  it("prevents a new download while a confirmation is pending", async () => {
    let finish;
    let downloads = 0;
    const page = await frontend(frontendFetch(() => { downloads++; return new Response("unused"); },
      () => new Promise((resolve) => { finish = resolve; })),
    { id: "11111111-1111-4111-8111-111111111111", release: `${RELEASE.version}-${RELEASE.kitRevision}` });
    page.check();
    const pending = page.click("#confirm");
    expect(page.nodes.get("#download").disabled).toBe(true);
    await page.click("#download");
    expect(downloads).toBe(0);
    finish(Response.json({ ok: true, downloads: 1, confirmedInstallations: 1 }));
    await pending;
  });
});
