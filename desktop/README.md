# 91 TV 1.1.0

A cinematic IPTV player for **Windows 11 x64**: Netflix/Apple TV-style dark OLED interface, M3U/M3U8 and Xtream Codes
playlists, live TV with EPG, movies and series, and a **libmpv** playback engine (NVIDIA hardware decoding, HEVC/AV1,
HDR10, Dolby/DTS bitstream passthrough where your hardware allows).

91 TV ships **no channels or content**. You add your own legally obtained playlist.

> **Status of this package (please read):** the source, build scripts and tests were created and tested on Linux.
> A Windows `.exe` could **not** be compiled or run in that environment, so **no EXE is included and none has been
> tested on Windows**. The two ways below turn this source into a real EXE; both run the built EXE's
> `--selftest` automatically and fail loudly if it does not start.

## Get the EXE - Option A: build on your PC (about 5-10 minutes)
Requirements: Windows 11 x64, 64-bit Python 3.12-3.14 from python.org, internet.

1. Unzip the source package, open PowerShell in that folder.
2. If scripts are blocked: `Set-ExecutionPolicy -Scope Process Bypass`
3. Easiest: double-click `BUILD.bat` (window stays open, output saved to `build-log.txt`). Or in PowerShell: `.\build.ps1`

Output in `release\`:
* `91TV-1.1.0-win64-portable.zip` - unzip anywhere, run `91TV.exe`
* `91TV-Setup-1.0.0.exe` - only if Inno Setup 6 is installed (https://jrsoftware.org/isinfo.php)

The script creates a virtual environment, installs dependencies, downloads the mpv video engine (`libmpv-2.dll`,
GPL build from github.com/shinchiro/mpv-winbuild-cmake), runs unit tests, builds with PyInstaller, runs the self-test and packages.
Python 3.12 is preferred automatically if installed; your 3.14.7 is used if nothing else is found (newer Python +
PyInstaller combinations are less proven - if the build fails on 3.14, install 3.12 side by side and re-run).

## Get the EXE - Option B: GitHub Actions (no local tooling)
1. Create a (private) GitHub repository and push this folder:
   `git init; git add .; git commit -m "91 TV"; git branch -M main; git remote add origin <your-repo-url>; git push -u origin main`
2. Open the repo → **Actions** → *Build 91 TV (Windows)* → wait for green.
3. Open the run → **Artifacts** → download `91TV-windows` (portable ZIP + Setup.exe).
Tag a release (`git tag v1.0.0; git push --tags`) to also publish them as a GitHub Release.

## First run
1. Start `91TV.exe`. Go to **Settings → Add playlist**: paste an M3U/M3U8 URL, pick a local file, or enter Xtream server/user/password.
2. Content loads in the background and is cached; use **Reload content** to refresh.
3. EPG: Xtream lists load their guide automatically; M3U lists use the `url-tvg` header if present, otherwise paste an XMLTV URL in Settings.

**Series:** click a series to open its page (banner, seasons, episodes); click an episode to play; *Resume* continues where you left off; `Esc` or *Back* returns.

**Live TV:** click a channel to preview it live in the panel on the right (with now/next guide info); double-click or press Enter, or use *Watch full screen*, to open it in the full player. Previews start muted and can be turned off in Settings → Live preview.

Controls: `F`/`F11` fullscreen · `Esc` back/exit fullscreen · `Space` pause · `←/→` seek 10 s · `PgUp/PgDn` previous/next channel ·
`Ctrl+F` search · right-click a title for *My List*. Profiles: click the profile name at the bottom of the sidebar to cycle.

## For best 4K / HDR / audio results (Windows configuration)
* Install current NVIDIA drivers. Settings → Hardware decoding: *Automatic* normally picks NVDEC through D3D11.
* **HDR10:** turn on *Settings → System → Display → HDR* for your monitor/TV. 91 TV signals HDR to Windows only when the content is HDR; otherwise it is tone-mapped to SDR.
* **Dolby Vision:** decoded and tone-mapped to your display (profile 5/8 handled by libplacebo). Output **as** Dolby Vision is not supported by this pipeline.
* **Dolby Digital / Digital Plus / DTS / TrueHD / DTS-HD / Atmos:** tick the matching checkboxes in Settings → Audio and choose your HDMI/optical device. The device must expose those formats in *Windows Sound → device → Properties → Supported Formats*, and the receiver must support them. **Dolby Atmos** is only passed through as E-AC-3 JOC (streaming-style) or TrueHD (needs exclusive-mode HDMI). The Info panel (player → *Info*) shows whether Atmos was detected in the stream and whether output is really bitstream or decoded to PCM.

See `FEATURES.md` for exactly what is and is not implemented and `TROUBLESHOOTING.md` for fixes.

## Layout
`aurora/` application · `tests/` unit tests · `tools/` icon + visual-check scripts · `build.ps1`, `aurora.spec`, `installer.iss` build kit · `.github/workflows/build.yml` CI.
Run from source (dev): `py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements.txt; .venv\Scripts\python main.py` (needs `libmpv-2.dll` next to `main.py`).

## New in 1.2

- **Hide what you don't want** - hide single channels/titles, whole categories (right-click a category in Live TV, or the "Hide category" button on Movies/Series), every category with the same language prefix (FR|, [AR]...), or whole alphabets (Arabic, Cyrillic, CJK...). Manage it all under Settings > Parental > "Hide channels & languages...". Undo any time.
- **Search everything** (Ctrl+K): channels, movies, series and upcoming programmes (jumps to the TV guide).
- **Visuals**: hover lift/glow on posters, page fades, Netflix-style zoom when opening a title, background colour that follows the poster, skeleton placeholders while loading, proper rounded logo tiles with clean fallbacks.
- **Appearance**: 5 accent colours, text/UI size, 10-foot (TV) mode.
- **Picture**: Fast/Balanced/Max scaling, debanding, noise reduction (CPU, up to 1080p), deinterlacing (auto), tone-mapping/peak settings with links to Windows HDR calibration, and per-channel picture profiles (Picture button in the player).
- **Fullscreen**: bigger controls and scrub-bar preview thumbnails for movies/series.

Honest limits: all of this was tested on Linux only; not yet run on Windows. Animations are fades/zoom, not slides. UI size and 10-foot mode apply after a restart. Preview thumbnails use a second decoder, so they can be switched off. There is no sharpen filter or artificial film grain. HDR calibration is guidance plus links, not automatic.

## New in 1.1
TMDB posters/plots/cast (optional key) · movie pages · TV guide grid · channel numbers (type digits, Up/Down, Backspace = last channel) · floating full-screen controls with channel banner · live rewind (↺10 / jump to live) · smooth motion & HDR tuning · first-run setup wizard · parental PIN + hidden categories · auto-hide dead channels · Xbox controller & remote media keys. See FEATURES.md for what is tested and what is not.

Keys: `0-9` channel number · `↑/↓` channel up/down (player) · `←/→` ±10 s · `Backspace`/`Q` last channel · `L` jump to live · `R` reload stream · `F`/`F11` full screen · `Esc` back.
