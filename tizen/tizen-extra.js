// ---- Samsung TV additions: remote control navigation and AVPlay (plays MKV / HLS / TS natively)
(function () {
  if (window.innerWidth >= 1700) document.documentElement.style.zoom = "1.5";
  try { if (window.tizen && tizen.tvinputdevice) ["MediaPlay", "MediaPause", "MediaPlayPause", "MediaStop", "MediaFastForward", "MediaRewind", "ColorF0Red"].forEach(k => { try { tizen.tvinputdevice.registerKey(k); } catch (e) {} }); } catch (e) {}
  const SEL = "button,a[href],input,.card,.live,.cat,.ep,summary";
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight && e.offsetParent !== null; };
  function mark() { document.querySelectorAll(".card,.live,.cat,.ep").forEach(e => { if (!e.hasAttribute("tabindex")) e.setAttribute("tabindex", "0"); }); }
  new MutationObserver(mark).observe(document.documentElement, { childList: true, subtree: true });
  function move(dir) {
    const cur = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
    const all = [...document.querySelectorAll(SEL)].filter(vis);
    // inside the player overlay only that overlay's buttons count
    const pl = document.getElementById("player") || document.getElementById("av-wrap"); const list = pl ? all.filter(e => pl.contains(e)) : all;
    if (!list.length) return;
    if (!cur || !list.includes(cur)) { list[0].focus(); return; }
    const c = cur.getBoundingClientRect(), cx = c.left + c.width / 2, cy = c.top + c.height / 2; let best = null, bs = 1e12;
    for (const e of list) {
      if (e === cur) continue; const r = e.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, dx = x - cx, dy = y - cy;
      const ok = dir === "L" ? dx < -4 : dir === "R" ? dx > 4 : dir === "U" ? dy < -4 : dy > 4; if (!ok) continue;
      const main = dir === "L" || dir === "R" ? Math.abs(dx) : Math.abs(dy), cross = dir === "L" || dir === "R" ? Math.abs(dy) : Math.abs(dx);
      const sc = main + cross * 3; if (sc < bs) { bs = sc; best = e; }
    }
    if (best) { best.focus(); best.scrollIntoView({ block: "nearest", inline: "nearest" }); }
  }
  let avStop = null;
  addEventListener("keydown", ev => {
    const k = ev.keyCode;
    if (avStop) {   // full-screen AVPlay is running
      if (k === 10009 || k === 8 || k === 413 || k === 27) { ev.preventDefault(); avStop(); }
      else if (k === 13 || k === 415 || k === 19 || k === 10252) { ev.preventDefault(); try { const st = webapis.avplay.getState(); st === "PLAYING" ? webapis.avplay.pause() : webapis.avplay.play(); } catch (e) {} }
      else if (k === 39 || k === 417) { ev.preventDefault(); try { webapis.avplay.jumpForward(30000); } catch (e) {} }
      else if (k === 37 || k === 412) { ev.preventDefault(); try { webapis.avplay.jumpBackward(30000); } catch (e) {} }
      return;
    }
    if (k === 37) { ev.preventDefault(); move("L"); } else if (k === 39) { ev.preventDefault(); move("R"); }
    else if (k === 38) { ev.preventDefault(); move("U"); } else if (k === 40) { ev.preventDefault(); move("D"); }
    else if (k === 13) { const a = document.activeElement; if (a && a !== document.body && a.tagName !== "INPUT") { ev.preventDefault(); a.click(); } }
    else if (k === 10009) { const b = document.querySelector("#sheet .back, .sheet .back, #player .back"); if (b) { ev.preventDefault(); b.click(); } }
  });
  window.tvPlay = function (it, url) {
    const w = document.createElement("div"); w.id = "av-wrap";
    w.innerHTML = '<object id="av-obj" type="application/avplayer"></object><div id="ptitle">' + esc(clean(it.name)) + '</div><div id="perr"></div>';
    document.body.appendChild(w); const err = w.querySelector("#perr"), av = webapis.avplay; let timer;
    const resume = () => { try { const sp = pos()[keyOf(it)]; if (sp && sp.t > 10 && sp.d - sp.t > 30) av.seekTo(Math.max(0, (sp.t - 3) * 1000)); } catch (e) {} };
    const save = () => { try { if (it.kind === "live") return; const d = av.getDuration() / 1000, t = av.getCurrentTime() / 1000; if (d > 0) { const p = pos(); p[keyOf(it)] = { t, d }; LS.set("pos", p); } } catch (e) {} };
    avStop = () => { clearInterval(timer); save(); try { av.stop(); } catch (e) {} try { av.close(); } catch (e) {} w.remove(); avStop = null; if (tab === "home") home(); };
    const fail = m => { err.style.display = "block"; err.textContent = (it.kind === "live" ? "This channel did not start. " : "This title did not start. ") + (m || "") + "  Press Back to leave."; };
    try {
      av.open(url);
      av.setDisplayRect(0, 0, 1920, 1080);
      av.setListener({ onerror: e => fail(String(e)), onstreamcompleted: () => { const p = pos(); delete p[keyOf(it)]; LS.set("pos", p); avStop && avStop(); }, onbufferingcomplete: () => {} });
      av.prepareAsync(() => { try { av.play(); resume(); } catch (e) { fail(String(e)); } timer = setInterval(save, 5000); }, e => fail(String(e)));
    } catch (e) { fail(String(e)); }
  };
})();
