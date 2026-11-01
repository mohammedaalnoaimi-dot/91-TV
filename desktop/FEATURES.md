# Feature status (honest list)

Legend: **Tested** = verified in the Linux sandbox (unit tests, offscreen UI render, real libmpv with null outputs). **Untested on Windows** = implemented but needs verification on real Windows/NVIDIA hardware. Nothing below has been run on Windows.

## Implemented
| Area | Feature | Status |
|---|---|---|
| Playlists | M3U/M3U8 import (URL, local file, gzip), group/logo/tvg-id parsing, `url-tvg` EPG header | Tested |
| Playlists | Xtream Codes login (live, movies, series, episodes, short EPG, XMLTV) | Logic tested with mocked API; not tested against a real server |
| Content | Live TV with categories, Movies, TV series (season/episode dialog), search + category filter | UI rendered and checked; logic tested |
| EPG | XMLTV (plain/gzip) parsing, now/next, progress bar, upcoming list | Tested |
| User data | Favorites ("My List"), recently watched, resume position for movies/episodes, multiple profiles, multiple playlists per profile, persistent settings (SQLite) | Tested |
| Security | URLs/passwords in Windows Credential Manager (keyring); falls back to local DB only if no keyring backend exists | Fallback tested; Credential Manager untested on Windows |
| Playback | libmpv engine, fullscreen, pause/seek/volume, audio + subtitle track switching, channel zapping | Engine tested with real libmpv (software, null output); on-screen embedding untested on Windows |
| v1.3 | **New look (dark luxury theatre)** shared with the Android 91 TV app: top menu instead of the sidebar, Cinzel / Jost fonts, rose accent. Branding is plain "91 TV" | Rendered offscreen on Linux; not seen on real Windows |
| v1.3 | **Prayer times (Bahrain)** from aladhan.com (Gulf Region default, 4 other methods), Prayer page, next-prayer chip + clock in the top bar, optional reminder banner, cached on disk | Logic + render tested; live API not reachable from the test sandbox |
| v1.3 | **Smart lists**: Recently added, Top rated, New releases, Hollywood / English in the Movies / Series category box; smarter search (all words, best match + best rated first) | Tested with fake data; "Hollywood" matches category names, so it depends on your provider's names |
| v1.3 | **IMDb + Rotten Tomatoes** (free OMDb key in Settings) on posters, hero, detail page and search; provider score shown without a key | Offline paths tested; OMDb itself not reachable from the sandbox |
| v1.3 | **Mr / Mrs / Together lists** (button in top bar), clock screensaver after idle (Settings) | Tested |
| v1.4 | **Netflix-style player**: gradient control bars that fade, thin red seek bar, big round play / pause, vector icons, centre play / pause flash | Rendered offscreen on Linux; real fade + libmpv overlay behaviour not seen on Windows |
| v1.4 | **Multi-view**: 2-4 live channels on one screen, click a screen for sound, "Add to Multi-view" in the right-click menu | Layout rendered offscreen; real streams not tested (needs a provider that allows several connections) |
| v1.4 | **"Because you watched" rows** on Home, built from this PC's own history (same category, better rated first), nothing leaves the PC | Tested with fake data |
| v1.4 | **Guide**: cleaner programme titles and IMDb / RT line (OMDb key) in the details panel | Title cleaning + cache path tested; no poster / plot for programmes |
| v1.4 | **Channel pre-warm**: next / previous channel are contacted in the background (DNS, TLS, redirect). Does not pre-decode video, so the gain is modest and not measured | Untested against a real provider |
| v1.5 | **Monthly prayer timetable** (button on the Prayer page) and **Ramadan mode** (suhoor / iftar countdowns on the Prayer page, "IFTAR" in the top bar). Detected from the hijri month, no setting needed | Logic + render tested with fake data; real Aladhan month data not reachable from the sandbox |
| v1.5 | **Faster start**: the saved library is read off the UI thread; posters are saved on disk after the first load (about 400 MB cap) | Tested with fake data; real speed-up on a 100k+ library not measured |
| v1.1 | **TMDB artwork & info** (optional, your own free key): fills missing posters, plots, ratings, cast, backdrops; titles are cleaned ("4K-AR-DO - Film (2019) FHD" → "Film", 2019); results cached on disk | Tested against a fake TMDB server. NOT tested against the real TMDB API |
| v1.1 | **Movie page** (Netflix-style, same as series) with plot/cast/rating from provider (`get_vod_info`) and TMDB | Tested |
| v1.1 | **TV guide grid**: time-based grid of all channels with EPG data, category + search filter, keyboard/mouse navigation, details panel, live preview, Watch | Tested (Linux, fake EPG). Not tested with a 1000-channel real EPG |
| v1.1 | **Channel numbers & fast zapping**: type a number (OSD), Up/Down = channel up/down, Backspace/Q = last channel, media keys; fast-start stream probing | Tested. Zapping speed on real streams not measured |
| v1.1 | **Full-screen player**: control bars float over the video and fade out (no re-layout), channel banner with now/next + progress, number OSD | Tested on Linux/Xvfb. Fade animation and translucent corners need a compositor: verify on Windows |
| v1.1 | **Live rewind (timeshift)**: ↺10 / 10↻ on live TV, "−42s ▶ LIVE" jump-to-live button, 2-20 min RAM buffer (setting) | Tested with a real libmpv + real-time test stream (rewind and return to live) |
| v1.1 | **Smooth motion** (frame interpolation, optional), **HDR→SDR tone-mapping choice**, **display peak brightness** | Options validated with real libmpv; visual effect untested (needs GPU/HDR display) |
| v1.1 | **Setup wizard** (playlist → audio device + test tone → extras → self-check) shown on first run; re-run from Settings | Tested (self-check against fake server). Test-tone audible output not testable here |
| v1.1 | **Parental controls**: PBKDF2-hashed PIN, hidden categories per profile (unlock with PIN per session), adult-looking category helper | Tested |
| v1.1 | **Auto-hide dead channels**: 3 failed plays in a row hides a channel (retested after 7 days, restore any time); a burst of failures with no success is treated as a network outage and ignored | Tested |
| v1.1 | **Game controller** (Windows XInput): D-pad/stick, A/B/X/Y, LB/RB channel -/+, Start; plus remote-control media keys | Button mapping/repeat logic unit-tested. NOT tested with a real pad or on Windows |
| Playback | Auto-reconnect with retry limit, stall detection, failure message | Tested (bad stream → 2 retries → failed) |
| Playback | Stuck-stream auto-recovery: no picture in 8 s, frozen picture 6 s or starved buffer 8 s → reloads the channel, then rotates to backup sources (Xtream .m3u8↔.ts, same-name channels from other categories/playlists). Dead links jump straight to a backup. Manual ↻ Reload button / `R` key | Tested on Linux with real libmpv + local fake server (dead link → backup in 1.5 s, hung stream → backup in 9 s). NOT tested on real providers |
| Video | Hardware decode selection (auto / NVDEC / NVDEC copy / D3D11VA / software), HEVC/AV1/VP9/H.264 allowed, gpu-next + D3D11, HDR10 signalling to Windows | Untested on Windows/NVIDIA |
| Audio | Device selection, AC-3/E-AC-3/DTS/TrueHD/DTS-HD passthrough toggles, WASAPI exclusive option | Untested on Windows |
| Live TV | Three-column Live TV page: categories, channel list (number, logo, now-playing, progress), and a **live preview panel** - selecting a channel plays it in the panel with now/next + upcoming guide, mute, My List and "Watch full screen"; preview is debounced, released when the full player opens, stopped when you leave the page, and can be disabled in Settings | Tested on Linux under a virtual X11 display against a fake Xtream server (software video, 14 automated checks). **Not tested on Windows / D3D11 / NVDEC** |
| Series | **Netflix-style series page**: single-click a series to open a full page with a backdrop banner, cleaned title, year/rating/seasons/genre, plot and cast, Play / **Resume** button (continues the last episode you watched), My List, season selector, and an episode list with thumbnails, durations and descriptions. Messy provider names ("4K-AR-DO - Show - S01E01 - Episode 1") are cleaned for display | Tested on Linux against a fake Xtream server (15 automated checks incl. play episode, back navigation, resume). Look checked in screenshots. Real providers' artwork/metadata vary - **untested against a real provider or on Windows** |
| Video | "Upscaling" setting (off / high-quality mpv GPU scaling: EWA Lanczos, sigmoid, deband) for the full-screen player. Classic filters - **not AI and not NVIDIA DLSS / RTX Video Super Resolution** | Setting implemented; **untested on Windows** |
| UI | Redesigned sidebar (vector icons, compact mode on narrow windows), glass panels, backdrop glow, new headers | Rendered and checked in screenshots (Linux) |
| Info panel | Actual codec, resolution, fps, HDR format, decoder, audio codec/profile, Atmos detection, bitstream-vs-PCM output | Tested for h264/ac3 (values read from libmpv); HDR/Atmos branches untested |
| Diagnostics | Rotating log in `%LOCALAPPDATA%\91TV\logs`, `--selftest`, Settings → Run diagnostics | Tested on Linux |
| Build | PyInstaller spec, build.ps1, Inno Setup installer script, GitHub Actions workflow | **Not executed on Windows** |

## Not implemented / limitations
* **No EXE has been compiled or tested by me** (see README).
* Dolby Vision **output** (display-side DV) - not possible with mpv/libplacebo; DV is tone-mapped.
* Atmos from sources other than E-AC-3 JOC / TrueHD, and any passthrough on devices/receivers that don't advertise the formats, will fall back to PCM. DTS:X is not specially detected.
* Real 4K60 smoothness depends on stream bitrate, network and GPU; not benchmarked.
* No catch-up (provider archive), recording/PVR or Chromecast. Live rewind only covers what was buffered since you tuned in.
* Instant zapping uses fast stream probing on one decoder; a second pre-loaded 'standby' decoder was NOT built.
* Artwork comes from your playlist; with an optional TMDB key it is filled in/replaced from TMDB (titles are sent to TMDB). No key is bundled.
* Live/VOD lists with 100k+ entries are supported by virtual list models but have not been load-tested.
* Mouse double-click on the video surface does not toggle fullscreen (use `F`, `F11` or the button).
* Code is not signed: Windows SmartScreen may warn on first launch of the EXE ("More info → Run anyway").
