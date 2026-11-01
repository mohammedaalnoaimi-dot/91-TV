// 91 TV phone activation. Cloudflare Worker + one KV namespace bound as PAIR.
// TV:    POST /new            -> { code, secret }      (TV shows the short code)
// Phone: POST /claim {code,key} -> { ok }               (checks the key with Lemon Squeezy first)
// TV:    GET  /status?code&secret -> { pending } | { key } | { expired }   (key is handed over once, then deleted)
const ALLOWED_PRODUCTS = [1488147, 1492379]; // 91 TV (Android TV) and 91 TV Free Trial
const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no 0/O/1/I
const TTL = 900; // seconds a code stays valid
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Access-Control-Allow-Headers": "Content-Type" };
const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json", ...CORS } });

function newCode() { const b = crypto.getRandomValues(new Uint8Array(6)); return [...b].map(x => ALPHABET[x % ALPHABET.length]).join(""); }
function newSecret() { const b = crypto.getRandomValues(new Uint8Array(16)); return [...b].map(x => x.toString(16).padStart(2, "0")).join(""); }
function cleanCode(c) { return String(c || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6); }
function cleanKey(k) {
  const h = String(k || "").replace(/[^0-9a-fA-F]/g, "").toUpperCase();
  if (h.length !== 32) return null;
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    const url = new URL(req.url); const path = url.pathname.replace(/\/+$/, "");
    try {
      if (path === "/new" && req.method === "POST") {
        let code = "";
        for (let i = 0; i < 8; i++) { code = newCode(); if (!(await env.PAIR.get("p:" + code))) break; }
        const secret = newSecret();
        await env.PAIR.put("p:" + code, JSON.stringify({ secret }), { expirationTtl: TTL });
        return json({ code, secret, ttl: TTL });
      }
      if (path === "/claim" && req.method === "POST") {
        const b = await req.json().catch(() => ({}));
        const code = cleanCode(b.code); const key = cleanKey(b.key);
        if (code.length !== 6) return json({ ok: false, error: "code" }, 400);
        if (!key) return json({ ok: false, error: "key_format" }, 400);
        const raw = await env.PAIR.get("p:" + code);
        if (!raw) return json({ ok: false, error: "code_unknown" }, 404);
        const r = await fetch("https://api.lemonsqueezy.com/v1/licenses/validate", {
          method: "POST", headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ license_key: key }),
        });
        const v = await r.json().catch(() => ({}));
        const pid = Number(v?.meta?.product_id);
        if (!v.valid && v.error && /not found/i.test(v.error)) return json({ ok: false, error: "key_unknown" }, 404);
        if (!ALLOWED_PRODUCTS.includes(pid)) return json({ ok: false, error: "key_unknown" }, 404);
        if (!v.valid) return json({ ok: false, error: "key_invalid", detail: v.error || (v.license_key && v.license_key.status) || "" }, 400);
        const d = JSON.parse(raw); d.key = key;
        await env.PAIR.put("p:" + code, JSON.stringify(d), { expirationTtl: 300 });
        return json({ ok: true });
      }
      if (path === "/status" && req.method === "GET") {
        const code = cleanCode(url.searchParams.get("code")); const secret = url.searchParams.get("secret") || "";
        const raw = await env.PAIR.get("p:" + code);
        if (!raw) return json({ expired: true });
        const d = JSON.parse(raw);
        if (!d.secret || d.secret !== secret) return json({ expired: true });
        if (d.key) { await env.PAIR.delete("p:" + code); return json({ key: d.key }); }
        return json({ pending: true });
      }
      return json({ error: "not_found" }, 404);
    } catch (e) { return json({ error: "server" }, 500); }
  },
};
