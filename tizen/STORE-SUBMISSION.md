# 91 TV: Samsung Seller Office submission pack

Everything below is ready to paste. Steps that need your Samsung account are marked **[YOU]**.

## 1. Before you start
- **[YOU]** Samsung account working (the 400 "unusual activity" block must clear first).
- **[YOU]** Register at https://seller.samsungapps.com (Individual is fine). Add the TV service: "Smart TV".
- Install Tizen Studio (or the VS Code Tizen extension) so the app can be signed with a **distributor certificate** (different from the Apps2Samsung certificate). Use Certificate Manager, then a Samsung certificate, type Distributor, Public.
- Build the package: `python3 tizen/build.py`, then package `tizen/pkg/` as a `.wgt` signed with the distributor certificate.
- Change the app id in `tizen/build.py` if Seller Office assigns a different one.

## 2. Listing text

**App name:** 91 TV
**Category:** Video / Entertainment
**Short description (80 chars):**
Your playlists, channels, movies and series in one beautiful app.

**Full description:**
91 TV is a media player for your own content. Add your M3U playlist or Xtream login and browse live channels, movies and series in a clean, fast interface made for the TV remote.
- Live TV, movies and series in one place
- Favourites and resume where you stopped
- Search across everything
- Built for the remote: arrows, OK and Back
- Plays HLS, TS, MKV and MP4

91 TV does not include any channels, playlists or media. You add only the content you have the right to watch.

**Keywords:** IPTV, player, M3U, live TV, movies, series

**Age rating:** 3+ (the app has no content of its own)
**Privacy policy URL:** https://ninetyonetv.com/privacy.html
**Support URL / email:** https://ninetyonetv.com (use the support email from the site)
**Languages:** English, Arabic

## 3. Graphics (Samsung sizes)
- App icon: 512x512 PNG (`docs/icon-512.png`)
- Screenshots: 1920x1080, at least 3 (home, live channels, player). Take them from the TV or from the web app at 1920x1080.
- Samsung may ask for a 1280x720 preview image.

## 4. Review notes (paste into "Notes for reviewers")
91 TV is an empty player. It does not ship, host or link to any channels or media. Users enter their own playlist URL or login. Sign-in uses a licence key bought on ninetyonetv.com; a free trial is available from the app. To test, use any public test stream, for example an HLS test URL. Contact us and we will provide a test playlist and a test licence key.

## 5. Things reviewers often flag
- IPTV apps get extra scrutiny. Keep the "no content included" wording above and don't show any channel names or logos in the screenshots.
- Make sure the app always responds to the Back key (it does: key 10009 is handled).
- Payment: Samsung may require in-app purchase through Samsung Checkout for digital goods bought inside the app. Our app only takes a licence key bought on the website. If asked, explain that, or hide the buy button on the TV build.
- Expect 1 to 2 weeks per review round.

## 6. Order of work
1. Samsung account unblocked, then install on your own TV with Apps2Samsung and test it.
2. Seller Office registration.
3. Signed package with distributor certificate.
4. Screenshots, then submit.
