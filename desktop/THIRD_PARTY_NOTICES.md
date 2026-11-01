# Third-party components
* **PySide6 / Qt 6** (LGPLv3) - UI. https://www.qt.io
* **libmpv / mpv** (the Windows build used is GPLv2+ from shinchiro/mpv-winbuild-cmake, bundles FFmpeg and libplacebo) - playback. https://mpv.io
* **python-mpv** (GPL/LGPL) - Python binding. **requests** (Apache-2.0), **keyring** (MIT), **PyInstaller** (GPL with bootloader exception), **Inno Setup** (free license).
Because the bundled mpv build is GPL, distributing the packaged app means complying with the GPL for that component (offer its source: see the mpv-winbuild-cmake project).
Dolby, DTS and HEVC are trademarks / patented technologies of their owners; 91 TV only passes streams to your system decoders/receiver or the bundled FFmpeg decoders and includes no licensed Dolby/DTS decoder of its own.


## Fonts (v1.3)
Cinzel, Jost and EB Garamond are licensed under the SIL Open Font License 1.1; the licence texts are in `assets/fonts/`.
Prayer times: aladhan.com API (free). Ratings: OMDb API (free key, user supplied).
