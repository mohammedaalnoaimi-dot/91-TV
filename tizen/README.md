# 91 TV for Samsung TV (Tizen), install on your own TV

This is a project folder, not a finished app. Samsung requires apps to be built and signed with its own free tool, using a certificate tied to your Samsung account and your TV. Nothing in here has been tried on a real Samsung TV yet.

## What you need
- A Windows PC on the same Wi-Fi/network as the TV
- A free Samsung account (https://account.samsung.com)
- The TV's IP address (TV: Settings > General > Network > Network Status > IP Settings)

## Steps
1. **Install Tizen Studio** from https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/installing-tv-sdk.html (choose the IDE installer).
2. Open **Package Manager** (from Tizen Studio) > Extension SDK tab > install **TV Extensions** (and Samsung Certificate Extension).
3. **Turn on Developer mode on the TV:** Home > Apps. Press **1 2 3 4 5** on the remote. In the window set Developer mode **On**, type your PC's IP address, press OK, then switch the TV off and on.
4. In Tizen Studio: **File > Import > Tizen > Tizen Project**, and pick the `pkg` folder from this zip.
5. Open **Tools > Device Manager**, click **Remote Device Manager**, add the TV by its IP (port 26101) and switch the connection **On**.
6. Open **Tools > Certificate Manager**, create a new **Samsung** certificate, sign in with your Samsung account, and tick your TV when it asks which devices to include.
7. Right-click the project > **Run As > Tizen Web Application**. 91 TV opens on the TV and stays installed under Apps.

## Using it
- Remote arrows move between items, **OK** opens, **Back** goes back.
- In a video: OK pauses, left/right jump 30 seconds, Back leaves.
- Enter your activation key (the 14-digit owner code works too) and your provider details on the first screen.

## If it does not work
Send me a photo of the TV or the Tizen Studio error. I can't test on a Samsung from here, so expect to fix a few things together.

Rebuild after changing the web app: `python3 build.py`
