# 91 TV for Android TV / Google TV (TCL etc.)

Early version (0.3.0). Live TV, Movies, Series (Xtream Codes), or any M3U playlist.
D-pad friendly. Channel up/down or Up/Down zaps channels. Long-press OK on a category to hide it
(or every category with the same language prefix such as `FR|` / `[AR]`).
Built-in stream recovery: retries `.m3u8` then `.ts` variants.

No content is bundled. You supply your own provider.

## Get the APK
Push to `main` (or run Actions > Build AURORA TV APK). Every build is published as the release "AURORA TV (latest build)".
Stable link: `https://github.com/<you>/<repo>/releases/latest/download/AuroraTV.apk` (repo must be public).
The APK is signed with the key in `app/aurora.jks`, so new builds install over old ones. (Uninstall a 0.1.0 build once: it used a different key.)

## Install on the TV with Downloader
1. Install **Downloader** (Google Play on the TV).
2. Allow it to install unknown apps (Settings > Apps > Security & restrictions > Unknown sources > Downloader).
3. In Downloader, type the APK URL above (or a short code/link you create at https://aftvnews.com/ for that URL) and Go > Install.

## Status
NOT compiled or run by the author (no Android toolchain available in the build sandbox). The first GitHub Actions build may fail on a compile error: send the log and it will be fixed.

## 0.4.0 - "Dark Luxury Theatre" look
Top menu + header (clock, next prayer), Prayer page for Bahrain (Aladhan API, Gulf Region method by default),
Mr / Mrs / Together watchlists, quiet clock screensaver.

Fonts bundled in `app/src/main/assets/fonts` (all SIL Open Font License, licence texts included):
Cinzel, Jost, EB Garamond Italic. Prayer times: https://aladhan.com (free public API).
