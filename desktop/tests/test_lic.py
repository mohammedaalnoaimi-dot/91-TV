import os, sys, tempfile
os.environ["AURORA_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from aurora import lic as L
from aurora.store import Store

def mk():
    return L.Lic(Store(os.path.join(tempfile.mkdtemp(), "t.db")))

def fake(calls):
    def t(path, kv):
        calls.append((path, dict(kv)))
        if path == "validate" and "instance_id" not in kv:
            return {"valid": True, "license_key": {"status": "active", "expires_at": None}, "meta": {"product_id": L.PRODUCT_ID, "variant_name": "Lifetime"}}
        if path == "activate": return {"activated": True, "instance": {"id": "inst1"}, "license_key": {"expires_at": None}, "meta": {"product_id": L.PRODUCT_ID, "variant_name": "Lifetime"}}
        if path == "validate": return {"valid": True, "license_key": {"status": "active", "expires_at": None}, "meta": {"product_id": L.PRODUCT_ID, "variant_name": "Lifetime"}}
        if path == "deactivate": return {"deactivated": True}
    return t

def test_trial_code_expires_and_clock_rollback():
    l = mk(); now = [100_000.0]; L.clock = lambda: now[0]
    assert l.needs_screen() and not l.ok()
    exp = "1970-01-09T00:00:00.000000Z"   # 8 days after the fake clock origin
    def t(p, kv):
        m = {"product_id": L.TRIAL_PRODUCT_ID, "variant_name": "Default"}
        if p == "validate": return {"valid": True, "license_key": {"status": "active", "expires_at": exp}, "meta": m}
        return {"activated": True, "instance": {"id": "i"}, "license_key": {"expires_at": exp}, "meta": m}
    L.transport = t
    assert l.activate("38b1460a-5104-4067-a91d-77b872934d51") is None and l.ok() and l.summary().startswith("Free trial")
    now[0] -= 3 * 86400; assert not l.ok() and "date" in l.message()          # clock turned back
    now[0] += 3 * 86400; assert l.ok()
    now[0] += 20 * 86400; assert not l.ok() and "trial ended" in l.message()
    L.clock = __import__("time").time; L.transport = L._post

def test_activate_and_limits():
    l = mk(); calls = []; L.transport = fake(calls)
    assert l.activate("short") == "Please type the full code"
    assert l.activate("38B1460A51044067A91D77B872934D51") is None
    assert calls[0][1]["license_key"] == "38b1460a-5104-4067-a91d-77b872934d51"      # dashes added, lower case
    assert l.ok() and l.licensed() and l.summary() == "Lifetime"
    assert l.deactivate() is None and not l.has_key()

def test_wrong_product_and_nonet():
    l = mk()
    L.transport = lambda p, kv: {"valid": True, "license_key": {"status": "active"}, "meta": {"product_id": 1}}
    assert "not for" in l.activate("38b1460a-5104-4067-a91d-77b872934d51")
    def boom(p, kv): raise L.NoNet()
    L.transport = boom; assert "internet" in l.activate("38b1460a-5104-4067-a91d-77b872934d51")
    L.transport = L._post

def test_limit_message():
    l = mk()
    def t(p, kv):
        if p == "validate": return {"valid": True, "license_key": {"status": "active"}, "meta": {"product_id": L.PRODUCT_ID}}
        return {"activated": False, "error": "This license key has reached the activation limit."}
    L.transport = t; assert "maximum number of devices" in l.activate("38b1460a-5104-4067-a91d-77b872934d51"); L.transport = L._post
