// 91 TV phone activation. Cloudflare Worker + one KV namespace bound as PAIR.
// TV:    POST /new            -> { code, secret }      (TV shows the short code)
// Phone: POST /claim {code,key} -> { ok }               (checks the key with Lemon Squeezy first)
// TV:    GET  /status?code&secret -> { pending } | { key } | { expired }   (key is handed over once, then deleted)
const TRIAL_PRODUCT = 1492379, TRIAL_MS = 7 * 86400000, TRIAL_MAX_PER_IP_DAY = 5, TRIAL_DEVICES = 2;
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

// ---- Own free trial: one per email, 16-hex token, LS-compatible licence endpoints so the apps reuse their code ----
function normEmail(e) {
  e = String(e || "").trim().toLowerCase(); const m = e.match(/^([^@\s]+)@([^@\s]+\.[^@\s]+)$/); if (!m) return null;
  let [, u, d] = m; if (d === "googlemail.com") d = "gmail.com";
  if (d === "gmail.com") u = u.replace(/\./g, "");
  u = u.split("+")[0]; return u ? u + "@" + d : null;
}
async function sha(s) { const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join(""); }
function newToken() { const b = crypto.getRandomValues(new Uint8Array(8)); return [...b].map(x => x.toString(16).padStart(2, "0")).join("").toUpperCase(); }
function cleanToken(k) {
  const a = String(k || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  if (a.length === 16 && /^[0-9A-F]{16}$/.test(a)) return a;           // trial token
  if (a.length === 8 && [...a].every(c => ALPHABET.includes(c))) return a; // short hand-issued lifetime code
  return null;
}
function licBody(t, extra) {
  if (t.life) return { valid: true, license_key: { status: "active", expires_at: null }, meta: { product_id: 1488147, variant_name: "Lifetime" }, ...extra };
  const left = t.exp - Date.now();
  return { valid: left > 0, license_key: { status: left > 0 ? "active" : "expired", expires_at: new Date(t.exp).toISOString() }, meta: { product_id: TRIAL_PRODUCT, variant_name: "Free trial" }, ...extra };
}
// Hand-issued lifetime codes (for people you know): paste them in a Worker variable named LIFE_CODES, comma separated. Remove a code from the list to revoke it.
function isLife(env, tok) { return !!tok && String(env.LIFE_CODES || "").split(/[,\s]+/).map(cleanToken).includes(tok); }
async function readForm(req) {
  const ct = req.headers.get("Content-Type") || "";
  if (ct.includes("json")) return await req.json().catch(() => ({}));
  const f = await req.formData().catch(() => null); const o = {}; if (f) for (const [k, v] of f.entries()) o[k] = String(v); return o;
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
        const code = cleanCode(b.code); const tt = cleanToken(b.key); const key = tt || cleanKey(b.key);
        if (code.length !== 6) return json({ ok: false, error: "code" }, 400);
        if (!key) return json({ ok: false, error: "key_format" }, 400);
        const raw = await env.PAIR.get("p:" + code);
        if (!raw) return json({ ok: false, error: "code_unknown" }, 404);
        if (tt) {
          const tr = await env.PAIR.get("tk:" + tt); if (!tr) return json({ ok: false, error: "key_unknown" }, 404);
          if (JSON.parse(tr).exp <= Date.now()) return json({ ok: false, error: "key_invalid" }, 400);
          const d0 = JSON.parse(raw); d0.key = tt; await env.PAIR.put("p:" + code, JSON.stringify(d0), { expirationTtl: 300 }); return json({ ok: true });
        }
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
      if (path === "/trial/new" && req.method === "POST") {
        const b = await readForm(req); const em = normEmail(b.email);
        if (!em) return json({ ok: false, error: "email" }, 400);
        const eh = await sha("e:" + em); const old = await env.PAIR.get("te:" + eh);
        let token, exp, again = false;
        if (old) {
          const o = JSON.parse(old); if (o.exp <= Date.now()) return json({ ok: false, error: "used" }, 409);
          token = o.token; exp = o.exp; again = true;
        } else {
          const ip = req.headers.get("CF-Connecting-IP") || "x"; const day = new Date().toISOString().slice(0, 10);
          const ik = "ti:" + (await sha(ip)).slice(0, 16) + ":" + day; const n = Number((await env.PAIR.get(ik)) || 0);
          if (n >= TRIAL_MAX_PER_IP_DAY) return json({ ok: false, error: "busy" }, 429);
          await env.PAIR.put(ik, String(n + 1), { expirationTtl: 172800 });
          token = newToken(); exp = Date.now() + TRIAL_MS;
          await env.PAIR.put("tk:" + token, JSON.stringify({ exp, devs: [] }));
          await env.PAIR.put("te:" + eh, JSON.stringify({ token, exp }));
        }
        const code = cleanCode(b.code);
        if (code.length === 6) {
          const raw = await env.PAIR.get("p:" + code);
          if (raw) { const d = JSON.parse(raw); d.key = token; await env.PAIR.put("p:" + code, JSON.stringify(d), { expirationTtl: 300 }); return json({ ok: true, token, exp, again, tv: true }); }
          return json({ ok: true, token, exp, again, tv: false, tvError: "code_unknown" });
        }
        return json({ ok: true, token, exp, again, tv: false });
      }
      if (path.startsWith("/lic/") && req.method === "POST") {
        const b = await readForm(req); const tok = cleanToken(b.license_key); const act = path.slice(5);
        let raw = tok ? await env.PAIR.get("tk:" + tok) : null;
        if (!raw && isLife(env, tok)) raw = JSON.stringify({ life: true, exp: 0, devs: [] });
        if (raw && JSON.parse(raw).life && !isLife(env, tok)) raw = null; // revoked
        if (!raw) {
          // Not one of our own trial tokens: a paid key. Forward to Lemon Squeezy (so web apps can use it despite CORS) and only accept our products.
          const lk = cleanKey(b.license_key);
          if (lk && ["validate", "activate", "deactivate"].includes(act)) {
            const f = new URLSearchParams({ license_key: lk }); if (b.instance_name) f.set("instance_name", String(b.instance_name).slice(0, 60)); if (b.instance_id) f.set("instance_id", String(b.instance_id).slice(0, 64));
            const r = await fetch("https://api.lemonsqueezy.com/v1/licenses/" + act, { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" }, body: f });
            const v = await r.json().catch(() => ({}));
            if (act !== "deactivate" && !ALLOWED_PRODUCTS.includes(Number(v?.meta?.product_id))) return json({ valid: false, activated: false, deactivated: false, error: "license_key not found.", license_key: null });
            return json(v);
          }
          return json({ valid: false, activated: false, deactivated: false, error: "license_key not found.", license_key: null });
        }
        const t = JSON.parse(raw);
        if (act === "validate") {
          if (b.instance_id && !t.devs.includes(b.instance_id)) return json({ valid: false, error: "license_key not found.", license_key: null });
          return json(licBody(t));
        }
        if (act === "activate") {
          if (!t.life && t.exp <= Date.now()) return json({ activated: false, error: "license_key has expired." });
          if (t.devs.length >= TRIAL_DEVICES) return json({ activated: false, error: "This license key has reached the activation limit." });
          const id = newSecret().slice(0, 16); t.devs.push(id); await env.PAIR.put("tk:" + tok, JSON.stringify(t));
          return json({ activated: true, instance: { id, name: String(b.instance_name || "") }, ...licBody(t) });
        }
        if (act === "deactivate") {
          const i = t.devs.indexOf(b.instance_id); if (i < 0) return json({ deactivated: false, error: "license_key not found." });
          t.devs.splice(i, 1); await env.PAIR.put("tk:" + tok, JSON.stringify(t)); return json({ deactivated: true });
        }
      }
      return json({ error: "not_found" }, 404);
    } catch (e) { return json({ error: "server" }, 500); }
  },
};
