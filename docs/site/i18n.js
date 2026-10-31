(function(){
  var d=document,h=d.documentElement,btn=d.getElementById('lang');
  var st=d.createElement('style');
  st.textContent="@font-face{font-family:'Cairo';src:url('site/fonts/cairo-arabic.woff2') format('woff2');font-weight:200 1000;font-display:swap;unicode-range:U+0600-06FF,U+0750-077F,U+FB50-FDFF,U+FE70-FEFF}"+
  "#lang{font:inherit;font-size:14px;cursor:pointer;background:transparent;color:inherit;border:1px solid currentColor;border-radius:999px;padding:6px 14px;margin-inline:12px;opacity:.85}#lang:hover{opacity:1}"+
  "html[lang=ar] body,html[lang=ar] button,html[lang=ar] input{font-family:'Cairo','Jost',sans-serif}"+
  "html[lang=ar] h1,html[lang=ar] h2,html[lang=ar] h3,html[lang=ar] .btn,html[lang=ar] nav a{font-family:'Cairo',sans-serif;letter-spacing:0!important;text-transform:none!important}"+
  "html[lang=ar] em{font-style:normal}html[lang=ar] *{letter-spacing:0!important}.btn,#lang{white-space:nowrap}";
  d.head.appendChild(st);
  var els=[].slice.call(d.querySelectorAll('[data-ar]'));
  els.forEach(function(e){e.setAttribute('data-en',e.innerHTML)});
  var note=d.getElementById('arnote');
  function set(l){
    els.forEach(function(e){e.innerHTML=e.getAttribute(l==='ar'?'data-ar':'data-en')});
    h.lang=l;h.dir=l==='ar'?'rtl':'ltr';
    if(btn)btn.textContent=l==='ar'?'English':'العربية';
    if(note)note.hidden=l!=='ar';
    try{localStorage.setItem('lang91',l)}catch(e){}
  }
  var l='en';
  try{l=localStorage.getItem('lang91')||((navigator.language||'').slice(0,2)==='ar'?'ar':'en')}catch(e){}
  if(l==='ar')set('ar');
  if(btn)btn.addEventListener('click',function(){set(h.lang==='ar'?'en':'ar')});
})();
