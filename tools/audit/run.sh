#!/usr/bin/env bash
# usage: run.sh <apk> <outdir> <density>   (runs inside the emulator job)
APK=$1; OUT=$2; DENS=${3:-320}; PKG=com.aurora.tv; HOST=10.0.2.2:8080
mkdir -p "$OUT"; LOG="$OUT/log.txt"; : > "$LOG"
k()    { adb shell input keyevent "$@"; sleep 0.9; }
kn()   { n=$1; shift; for _ in $(seq "$n"); do adb shell input keyevent "$@"; sleep 0.35; done; sleep 0.6; }
snap() { adb exec-out screencap -p > "$OUT/$1.png"; }
goto() { kn 8 19; kn 16 21; kn "$1" 22; k 23; sleep 3.5; }          # top bar: go to the Nth menu entry and open it
mem()  { echo "== $1" >> "$LOG"; adb shell dumpsys meminfo $PKG | grep -E "Java Heap|Native Heap|Graphics|TOTAL PSS|TOTAL:" | head -6 >> "$LOG"; adb shell top -b -n 1 | grep -E "aurora|PID" | head -3 >> "$LOG"; }

adb uninstall $PKG >/dev/null 2>&1; adb install -r "$APK" >> "$LOG" 2>&1
adb shell wm density "$DENS"; adb shell wm size >> "$LOG"; adb shell wm density >> "$LOG"
NOW=$(date +%s)000
cat > /tmp/aurora.xml <<XML
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
 <string name="server">http://$HOST</string><string name="user">demo</string><string name="pass">demo</string>
 <string name="lic_key">AUDIT-0000-0000-0000</string><string name="lic_inst">audit</string>
 <long name="lic_ok" value="$NOW"/><long name="lic_seen" value="$NOW"/><long name="lic_exp" value="0"/>
 <string name="profile">mr</string>
</map>
XML
adb push /tmp/aurora.xml /data/local/tmp/aurora.xml >/dev/null
adb shell run-as $PKG mkdir -p shared_prefs; adb shell run-as $PKG cp /data/local/tmp/aurora.xml shared_prefs/aurora.xml
adb shell run-as $PKG ls shared_prefs >> "$LOG" 2>&1

# startup: record the screen while the app opens, and time the launch
adb shell "screenrecord --time-limit 22 --size 1280x720 --bit-rate 6000000 /sdcard/startup.mp4" &
sleep 1
adb shell am start -W -n $PKG/.MainActivity >> "$LOG" 2>&1
sleep 5;  snap 00_intro_5s
sleep 8;  snap 00_intro_13s
sleep 12; adb pull /sdcard/startup.mp4 "$OUT/startup.mp4" >/dev/null 2>&1
snap 01_home; mem after_home

k 20; snap 02_home_down1; kn 2 20; snap 03_home_down3; kn 2 22; snap 04_home_right
adb shell input keyevent --longpress 23; sleep 1.2; snap 05_longpress_menu; k 4
kn 8 19; snap 06_topbar_focus
for i in 1 2 3 4 5 6 7 8 9; do k 22; snap 07_nav_$i; done

if [ "$DENS" = "320" ]; then
 for i in 1 3 4 5 6 7 8 9; do goto $i; snap "10_page_$i"; k 20; snap "10_page_${i}_d1"; k 20; k 20; snap "10_page_${i}_d3"; k 21; sleep 0.6; snap "10_page_${i}_left"; done
fi

# movies: category panel + category grid
goto 3; snap 20_movies; k 21; sleep 0.8; snap 21_movies_catpanel; kn 2 20; snap 22_catpanel_sel; k 23; sleep 3; snap 23_cat_grid; kn 3 20; snap 24_cat_grid_down; k 4; k 4

# playback + details
goto 3; kn 2 20; snap 30_movies_poster_focus; k 23; sleep 3; snap 31_details; k 23; sleep 7; snap 32_player; k 23; sleep 1.2; snap 33_player_controls; k 22; sleep 1; snap 34_player_focus
sleep 8; snap 35_player_late; k 4; sleep 1.5; snap 36_after_player; k 4

# series -> episode -> next-episode pill
goto 4; kn 2 20; k 23; sleep 3; snap 40_series_details; kn 2 20; snap 41_series_eps; k 23; sleep 8; snap 42_ep_player; sleep 6; snap 43_ep_player_late; k 4; k 4; k 4

# search
kn 8 19; kn 16 21; kn 8 22; k 23; sleep 2; snap 50_search_try; kn 3 22; snap 51_search_keys; k 23; k 23; sleep 1.5; snap 52_search_typed; k 4

# scroll performance on Movies (rapid key presses), measured with gfxinfo
goto 3; adb shell dumpsys gfxinfo $PKG reset >/dev/null
adb shell 'for i in $(seq 70); do input keyevent 22; done'; sleep 1
adb shell 'for i in $(seq 40); do input keyevent 20; done'; sleep 1.5
echo "== gfxinfo after rapid scrolling (right x70, down x40)" >> "$LOG"; adb shell dumpsys gfxinfo $PKG | sed -n '1,28p' >> "$LOG"
snap 60_after_scroll; mem after_scroll
echo "== startup (am start -W, cold)" >> "$LOG"; adb shell am force-stop $PKG; sleep 1; adb shell am start -W -n $PKG/.MainActivity | grep -E "TotalTime|WaitTime|ThisTime" >> "$LOG"
sleep 14; snap 61_relaunch_home
adb shell wm density reset
