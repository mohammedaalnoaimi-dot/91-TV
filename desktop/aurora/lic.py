"""Activation by code (Lemon Squeezy license keys) + 7-day free trial. Port of the TV app's Lic.kt; same plans, same codes.
No secret is stored in the app. Plan length comes from the licence length set in Lemon Squeezy."""
from __future__ import annotations
import hashlib, json, re, socket, time, urllib.parse, urllib.request, urllib.error, datetime

REQUIRED = True
PRODUCT_ID = 1488315                 # "91 TV for Windows" product
TRIAL_PRODUCT_ID = 1492379           # "91 TV Free Trial (7 days)": free trial, codes issued by our own server, one per email
TRIAL_URL = "https://ninetyonetv.com/trial/"
BUY_URL = "91tv.lemonsqueezy.com"
TRIAL_DAYS = 7
DAY = 24 * 3600
RECHECK_S = 1 * DAY                  # online re-check at most once a day
GRACE_S = 7 * DAY                    # keeps working offline this long after the last good check
API = "https://api.lemonsqueezy.com/v1/licenses/"
PAIR_API = "https://ninetyone-pair.mohammed-a-alnoaimi.workers.dev"   # our own server: issues and checks the free-trial codes
OWNER_HASH = "146a00214bdc124e201464ee733c5e935c5f11a7be38743656e569a0c515c066"
OWNER_PIN_HASH = "242b8faf3b09925bbe051cb47f25b9168ae9ca6ea43458a5c6a993407056f62d"


class NoNet(Exception):
    pass


def is_trial_key(k: str) -> bool:
    h = re.sub(r"[^A-Za-z0-9]", "", k or "")
    if re.fullmatch(r"[A-Za-z0-9\- ]+", k or "") is None: return False
    # 16 hex = free-trial token; 8 characters (no 0/O/1/I) = short lifetime code. Both are checked by our own server.
    return re.fullmatch(r"[0-9a-fA-F]{16}", h) is not None or re.fullmatch(r"[A-HJ-NP-Za-hj-np-z2-9]{8}", h) is not None


def _post(path: str, kv: dict) -> dict:
    body = urllib.parse.urlencode(kv).encode()
    base = (PAIR_API + "/lic/") if is_trial_key(str(kv.get("license_key", ""))) else API
    req = urllib.request.Request(base + path, data=body, method="POST", headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        try:
            with urllib.request.urlopen(req, timeout=15) as r: txt = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
        return json.loads(txt)
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as e:
        raise NoNet() from e


transport = _post            # replaced in tests
clock = time.time


def device_name() -> str:
    import platform, uuid
    return f"{platform.node() or 'Windows PC'} {format(uuid.getnode(), 'x')[-6:]}"


def _pbkdf2(pw: str, salt: str, rounds: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), rounds, 32).hex()


_owner_cache: dict = {}
def is_owner(code) -> bool:
    c = (code or "").strip().upper()
    if not c: return False
    if c in _owner_cache: return _owner_cache[c]
    digits = re.sub(r"\D", "", c)
    r = hashlib.sha256(("91tv-owner:" + c).encode()).hexdigest() == OWNER_HASH or \
        (len(digits) == 14 and len(digits) == len(re.sub(r"[^A-Za-z0-9]", "", c)) and _pbkdf2(digits, "91tv-owner-pin", 100000) == OWNER_PIN_HASH)
    _owner_cache[c] = r
    return r


def normalize(raw: str) -> str:
    t = raw.strip(); h = re.sub(r"[^A-Za-z0-9]", "", t)
    if is_trial_key(t): return h.upper()
    if len(h) == 32 and re.fullmatch(r"[0-9a-fA-F]{32}", h) and re.fullmatch(r"[A-Za-z0-9\- ]+", t):
        h = h.lower(); return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
    return t


def _parse_date(s) -> float:
    if not s or s == "null" or len(s) < 19: return 0.0
    try: return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
    except ValueError: return 0.0


def _day(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%d %b %Y").lstrip("0")


def _friendly(err: str) -> str:
    e = (err or "").lower()
    if "limit" in e: return "This code is already used on the maximum number of devices. Remove it on the other device (Settings > Licence) and try again."
    if "not found" in e: return "Code not found. Please check it and try again."
    if "expired" in e: return "This code has expired. Please buy a new plan."
    if "disabled" in e: return "This code has been cancelled."
    return err or "Code not accepted"


class Lic:
    """All state lives in the app's settings store (keys lic_*, trial_start)."""
    def __init__(self, store):
        self.st = store

    def _g(self, k, d=""):
        v = self.st.get(k); return d if v is None else v

    def _belongs(self, o: dict) -> bool:
        m = o.get("meta") or {}
        return PRODUCT_ID == 0 or m.get("product_id") in (PRODUCT_ID, TRIAL_PRODUCT_ID)

    def _is_trial(self) -> bool: return int(self._g("lic_pid", 0) or 0) == TRIAL_PRODUCT_ID

    # ---- state
    def has_key(self) -> bool: return bool(str(self._g("lic_key", "")).strip())

    def licensed(self) -> bool:
        if not REQUIRED: return True
        if not self.has_key(): return False
        if is_owner(self._g("lic_key")): return True
        now = clock(); exp = float(self._g("lic_exp", 0) or 0)
        seen = float(self._g("lic_seen", 0) or 0)       # clock set backwards to stretch a plan or the offline period
        if seen > 0 and now < seen - DAY:
            self.st.set("lic_msg", "The date on this PC looks wrong. Set the correct date and time, then press Check again."); return False
        if now > seen: self.st.set("lic_seen", now)
        if 0 < exp < now:
            self.st.set("lic_msg", (f"Your free trial ended on {_day(exp)}. Buy a plan at ninetyonetv.com to keep watching." if self._is_trial() else f"Your plan ended on {_day(exp)}. Renew it, then press Check again.")); return False
        if now - float(self._g("lic_ok", 0) or 0) >= GRACE_S: self.st.set("lic_msg", "Connect to the internet so 91 TV can check your code."); return False
        return True

    def ok(self) -> bool: return self.licensed()

    def needs_screen(self) -> bool: return not self.licensed()

    def message(self) -> str: return str(self._g("lic_msg", "") or "")

    def summary(self) -> str:
        if not self.has_key(): return "Not activated"
        if is_owner(self._g("lic_key")): return "Owner · unlimited"
        if self._is_trial():
            e = float(self._g("lic_exp", 0) or 0); return "Free trial" + (f" · until {_day(e)}" if e > 0 else "")
        plan = str(self._g("lic_plan", "") or "") or "Activated"; exp = float(self._g("lic_exp", 0) or 0)
        return f"{plan} · until {_day(exp)}" if exp > 0 else (plan if "lifetime" in plan.lower() else f"{plan} · no end date")

    # ---- actions (blocking; run off the UI thread if you like)
    def _save(self, key, inst, o):
        self.st.set("lic_key", key); self.st.set("lic_inst", inst); self.st.set("lic_ok", clock()); self.st.set("lic_seen", clock())
        self.st.set("lic_pid", int((o.get("meta") or {}).get("product_id") or 0))
        self.st.set("lic_exp", _parse_date((o.get("license_key") or {}).get("expires_at")))
        self.st.set("lic_plan", (o.get("meta") or {}).get("variant_name") or ""); self.st.set("lic_msg", "")

    def _forget(self, msg=None):
        for k in ("lic_key", "lic_inst", "lic_ok", "lic_exp", "lic_plan", "lic_pid"): self.st.set(k, "" if k in ("lic_key", "lic_inst", "lic_plan") else 0)
        self.st.set("lic_msg", msg or "")

    def activate(self, raw: str):
        """Returns None when activated, otherwise the message to show."""
        raw = raw.strip()
        if len(raw) < 8: return "Please type the full code"
        if is_owner(raw): return self._activate_checked(raw)
        k = normalize(raw); r = self._activate_checked(k)
        if r == "Code not found. Please check it and try again." and k.upper() != k:
            if self._activate_checked(k.upper()) is None: return None
        return r

    def _activate_checked(self, key: str):
        k = key.strip()
        if is_owner(k):
            self.st.set("lic_key", k.upper()); self.st.set("lic_inst", "owner"); self.st.set("lic_ok", clock())
            self.st.set("lic_exp", 0); self.st.set("lic_plan", "Owner"); self.st.set("lic_msg", ""); return None
        try:
            inst = str(self._g("lic_inst", "") or "")
            if k == self._g("lic_key", "") and inst:
                v = transport("validate", {"license_key": k, "instance_id": inst})
                if v.get("valid") and self._belongs(v): self._save(k, inst, v); return None
            v = transport("validate", {"license_key": k})
            lk = v.get("license_key")
            if not lk: return _friendly(v.get("error", ""))
            if not self._belongs(v): return "This code is not for 91 TV for Windows"
            exp = _parse_date(lk.get("expires_at"))
            if lk.get("status") == "expired" or (exp > 0 and exp < clock()): return _friendly("expired")
            if lk.get("status") == "disabled": return _friendly("disabled")
            a = transport("activate", {"license_key": k, "instance_name": device_name()})
            if not a.get("activated"): return _friendly(a.get("error", ""))
            self._save(k, (a.get("instance") or {}).get("id", ""), a); return None
        except NoNet:
            return "No internet connection. Please try again."

    def refresh(self) -> bool:
        key = str(self._g("lic_key", "") or ""); inst = str(self._g("lic_inst", "") or "")
        if not key: return False
        if is_owner(key): return True
        try:
            v = transport("validate", {"license_key": key, "instance_id": inst}); status = (v.get("license_key") or {}).get("status")
            if v.get("valid") and self._belongs(v): self._save(key, inst, v); return True
            if "valid" not in v: return False
            if status == "expired": self.st.set("lic_ok", 0); self.st.set("lic_msg", "Your plan has ended. Renew it, then press Check again."); return False
            self._forget("This code was cancelled or removed from this PC. Please enter a valid code."); return False
        except NoNet:
            self.st.set("lic_msg", "No internet connection. Please try again."); return False

    def recheck_due(self) -> bool:
        return REQUIRED and self.has_key() and not is_owner(self._g("lic_key")) and clock() - float(self._g("lic_ok", 0) or 0) >= RECHECK_S

    def deactivate(self):
        key = str(self._g("lic_key", "") or ""); inst = str(self._g("lic_inst", "") or "")
        if not key or is_owner(key): self._forget(); return None
        try:
            o = transport("deactivate", {"license_key": key, "instance_id": inst})
            if o.get("deactivated") or "not found" in (o.get("error") or "").lower(): self._forget(); return None
            return _friendly(o.get("error", ""))
        except NoNet:
            return "No internet connection. Please try again."
