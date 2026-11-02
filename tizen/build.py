#!/usr/bin/env python3
"""Builds the Samsung (Tizen) project in ./pkg from the iPhone web app in ../docs/app. Run: python3 build.py"""
import os, shutil, re
here = os.path.dirname(os.path.abspath(__file__)); src = os.path.join(here, "..", "docs", "app"); out = os.path.join(here, "pkg")
shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
for f in ["index.html", "wordmark.png"]: shutil.copy(os.path.join(src, f), out)
shutil.copy(os.path.join(src, "icon-512.png"), os.path.join(out, "icon.png"))
s = open(os.path.join(out, "index.html"), encoding="utf-8").read()
tz = open(os.path.join(here, "tizen-extra.js"), encoding="utf-8").read()
css = open(os.path.join(here, "tizen-extra.css"), encoding="utf-8").read()
# Samsung's AVPlay library, then our TV additions, before the app's own script
i = s.index("<script>")
s = s[:i] + '<script src="$WEBAPIS/webapis/webapis.js"></script>\n<style>' + css + "</style>\n<script>" + tz + "</script>\n" + s[i:]
# play(): hand playback to Samsung's AVPlay when it exists
a = "  pushRecent(it);\n  const url = streamUrl(it)"
assert a in s
s = s.replace(a, "  pushRecent(it);\n  if (window.webapis && webapis.avplay) return tvPlay(it, streamUrl(it));\n  const url = streamUrl(it)", 1)
s = s.replace('if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});', "")
open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(s)
open(os.path.join(out, "config.xml"), "w", encoding="utf-8").write('''<?xml version="1.0" encoding="UTF-8"?>
<widget xmlns="http://www.w3.org/ns/widgets" xmlns:tizen="http://tizen.org/ns/widgets" id="http://ninetyonetv.com/91tv" version="1.0.0" viewmodes="maximized">
  <tizen:application id="NinetyOne1.TV" package="NinetyOne1" required_version="5.5"/>
  <content src="index.html"/>
  <feature name="http://tizen.org/feature/screen.size.all"/>
  <icon src="icon.png"/>
  <name>91 TV</name>
  <tizen:privilege name="http://tizen.org/privilege/internet"/>
  <tizen:privilege name="http://tizen.org/privilege/tv.inputdevice"/>
  <tizen:privilege name="http://developer.samsung.com/privilege/avplay"/>
  <access origin="*" subdomains="true"/>
  <tizen:setting screen-orientation="landscape" context-menu="disable" background-support="disable" encryption="disable" install-location="auto" hwkey-event="enable"/>
</widget>
''')
print("built", out)
