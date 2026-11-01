# Troubleshooting

**Logs:** `%LOCALAPPDATA%\91TV\logs\aurora.log` (Settings → *Open log folder*). Self-test report: `91TV.exe --selftest` writes `selftest.txt` next to the log (set `91 TV_DATA_DIR` to redirect).
When asking for help, send `aurora.log`.

| Symptom | Fix |
|---|---|
| `build.ps1` blocked: "running scripts is disabled" | `Set-ExecutionPolicy -Scope Process Bypass` then re-run |
| Build fails on Python 3.14 | Install Python 3.12 (python.org) alongside; `build.ps1` prefers it. Delete `.venv` and re-run |
| Download of mpv fails | GitHub unreachable/rate-limited. Download `mpv-dev-x86_64-*.7z` from github.com/shinchiro/mpv-winbuild-cmake/releases, extract `libmpv-2.dll` to `build\mpv\`, re-run |
| "Video engine missing" popup / log says libmpv not loaded | `libmpv-2.dll` must sit next to `91TV.exe` (portable: inside the 91 TV folder). Re-extract the ZIP completely; check antivirus quarantine |
| App won't start, no window | Run `91TV.exe --selftest`, read `selftest.txt` and `aurora.log`. Install the Microsoft Visual C++ Redistributable 2015-2022 x64 |
| SmartScreen warning | Unsigned build. *More info → Run anyway* |
| Playlist "could not load" | Check URL in a browser; some providers block unknown User-Agents or limit connections; Xtream: verify server includes port |
| Black video, audio plays | Set Hardware decoding to *Direct3D 11* or *Software*; update NVIDIA driver; check log for `mpv[...]` lines |
| Stutter at 4K | Use wired network; hardware decoding must not be *Software only*; Info panel shows decoder |
| HDR looks washed out / dim | Enable Windows HDR for that display; leave HDR output on *Auto*. If Windows HDR is off, 91 TV tone-maps to SDR by design |
| No surround / no passthrough | Select the HDMI/optical device; tick the formats it supports; check Windows Sound → Properties → Supported Formats; try WASAPI exclusive; Info panel → *Audio output* must say "Bitstream passthrough" |
| Atmos says "Not detected" | The stream's audio isn't E-AC-3 JOC/TrueHD Atmos, or the source strips it; many IPTV streams carry plain stereo/5.1 |
| No EPG | Paste an XMLTV URL in Settings; channel `tvg-id` must match the guide's channel ids (or display names) |
| "Stream stalled - reloading…" / "Trying backup source" | Auto-recovery working: it reloads the channel, then tries alternate URL formats and same-named channels. If every source fails the channel is down at the provider. Press ↻ Reload (or `R`) to retry manually; press twice quickly to force the next backup |
| Reconnecting… loops | Provider dropped the stream; raise *Auto-reconnect attempts* or check subscription connection limit |
| Forgot where data is | `%LOCALAPPDATA%\91TV` (database, cache, logs). Delete the folder for a clean reset (also remove entries named "91 TV" in Credential Manager) |

## v1.1 features
| Symptom | Fix |
|---|---|
| No posters / "Key rejected" | Settings → Artwork & info: paste your TMDB v3 API key or v4 token and press *Test key*. Posters are only fetched for items without artwork unless *Prefer TMDB posters* is on |
| ↺10 does nothing on a channel | Live rewind needs *Live rewind buffer* ≠ Off and only goes back as far as you have been watching that channel |
| A channel vanished | It was auto-hidden after failing 3 times: Settings → Parental controls → *Auto-hidden channels…* → Restore |
| Hidden category won't come back | Settings → *Unlock hidden content* (needs your PIN) or *Hidden categories…* to untick it |
| Forgot the PIN | Close 91 TV and delete `pin_hash` / `pin_salt` rows from the `settings` table in `%LOCALAPPDATA%\91TV\aurora.db` (e.g. with DB Browser for SQLite) |
| TV Guide is empty | No EPG: add an XMLTV URL in Settings or use a playlist that provides one; only channels with guide data are listed |
| Overlay controls look square / don't fade | Needs Windows desktop composition (default on Win 11); report it with the log if not |
| Controller does nothing | Only XInput pads (Xbox, most modern pads; Steam Input can emulate). Enable it in Settings → Controls |
