// TV mode: Samsung / LG / other smart-TV browsers. Remote-control navigation, big focus ring, Back key.
(function () {
  if (window.__tvx) return;
  var tv = /Tizen|SMART-TV|SmartTV|Web0S|WebOS|NetCast|HbbTV|Large Screen/i.test(navigator.userAgent) || /[?&]tv=1/.test(location.search);
  if (!tv) return;
  window.__tvx = 1;
  document.documentElement.className += " tv";
  if (window.innerWidth >= 1700) document.documentElement.style.zoom = "1.5";
  var st = document.createElement("style");
  st.textContent = ":focus{outline:3px solid #c9475c!important;outline-offset:2px}.tv *{cursor:none}.tv nav button:focus{background:#1a1412;border-radius:8px}";
  document.head.appendChild(st);
  try { if (window.tizen && tizen.tvinputdevice) ["MediaPlay", "MediaPause", "MediaPlayPause", "MediaStop", "MediaFastForward", "MediaRewind"].forEach(function (k) { try { tizen.tvinputdevice.registerKey(k); } catch (e) {} }); } catch (e) {}
  var SEL = "button,a[href],input,.card,.live,.cat,.ep,summary";
  function vis(e) { var r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth && e.offsetParent !== null; }
  function mark() { document.querySelectorAll(".card,.live,.cat,.ep").forEach(function (e) { if (!e.hasAttribute("tabindex")) e.setAttribute("tabindex", "0"); }); }
  new MutationObserver(function () { mark(); if (!document.activeElement || document.activeElement === document.body) { var f = document.querySelector("#main .quick button,#main .hero0 button,nav button.on"); if (f && vis(f)) f.focus(); } }).observe(document.documentElement, { childList: true, subtree: true });
  function move(dir) {
    var cur = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
    var all = Array.prototype.filter.call(document.querySelectorAll(SEL), vis);
    var top = document.querySelector(".sheet:last-of-type,#player"); var sheet = document.querySelector(".sheet"), pl = document.getElementById("player");
    var layer = pl || sheet; var list = layer ? all.filter(function (e) { return layer.contains(e); }) : all;
    if (!list.length) return;
    if (!cur || list.indexOf(cur) < 0) { list[0].focus(); return; }
    var c = cur.getBoundingClientRect(), cx = c.left + c.width / 2, cy = c.top + c.height / 2, best = null, bs = 1e12;
    list.forEach(function (e) {
      if (e === cur) return; var r = e.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, dx = x - cx, dy = y - cy;
      var ok = dir === "L" ? dx < -4 : dir === "R" ? dx > 4 : dir === "U" ? dy < -4 : dy > 4; if (!ok) return;
      var horiz = dir === "L" || dir === "R", main = horiz ? Math.abs(dx) : Math.abs(dy), cross = horiz ? Math.abs(dy) : Math.abs(dx), sc = main + cross * 3;
      if (sc < bs) { bs = sc; best = e; }
    });
    if (best) { best.focus(); try { best.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch (e) {} }
  }
  addEventListener("keydown", function (ev) {
    var k = ev.keyCode, a = document.activeElement, inp = a && a.tagName === "INPUT";
    if (k === 37 || k === 39 || k === 38 || k === 40) {
      if (inp && (k === 37 || k === 39)) return;
      ev.preventDefault(); move(k === 37 ? "L" : k === 39 ? "R" : k === 38 ? "U" : "D");
    } else if (k === 13) { if (a && a !== document.body && !inp) { ev.preventDefault(); a.click(); } }
    else if (k === 10009 || k === 27 || (k === 8 && !inp)) { var b = document.querySelector(".sheet .back,#player .back"); if (b) { ev.preventDefault(); b.click(); } }
  });
})();
