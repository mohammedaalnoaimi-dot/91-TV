"""libmpv playback engine wrapper: hardware decoding, HDR, passthrough, tracks, info, reconnect."""
from __future__ import annotations
import logging, os, sys, time
from .paths import app_dir, exe_dir

log = logging.getLogger(__name__)
_mpv = None
_mpv_error = None


def _prepare_dll_path():
    if sys.platform == "darwin":
        # Bundled libmpv (inside the .app) is found first; otherwise Homebrew's (Apple Silicon or Intel).
        import ctypes.util
        for d in (str(exe_dir()), str(app_dir()), str(exe_dir().parent / "Frameworks"), "/opt/homebrew/lib", "/usr/local/lib"):
            for n in ("libmpv.2.dylib", "libmpv.dylib"):
                f = os.path.join(d, n)
                if os.path.exists(f):
                    _orig = ctypes.util.find_library
                    ctypes.util.find_library = lambda name, _f=f, _o=_orig: _f if name == "mpv" else _o(name)
                    return
        return
    if sys.platform != "win32":
        return
    for d in {str(exe_dir()), str(app_dir()), str(exe_dir() / "_internal"), str(exe_dir() / "mpv")}:
        if os.path.isdir(d):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(d)
            except (OSError, AttributeError):
                pass


def load_mpv():
    """Import python-mpv/libmpv. Returns module or None (error kept in mpv_error())."""
    global _mpv, _mpv_error
    if _mpv or _mpv_error:
        return _mpv
    _prepare_dll_path()
    try:
        import mpv
        _mpv = mpv
        log.info("libmpv loaded")
    except Exception as e:
        _mpv_error = f"{type(e).__name__}: {e}"
        log.error("libmpv could not be loaded: %s", _mpv_error)
    return _mpv


def mpv_error():
    return _mpv_error


def passthrough_codecs(settings) -> str:
    c = []
    if settings.get("pass_ac3"): c.append("ac3")
    if settings.get("pass_eac3"): c.append("eac3")
    if settings.get("pass_dts"): c += ["dts"]
    if settings.get("pass_hd"): c += ["dts-hd", "truehd"]
    return ",".join(c)


QUALITY = {   # picture-quality presets (applied to the full-screen player only)
    "fast": dict(scale="bilinear", cscale="bilinear", dscale="bilinear", deband="no"),
    "balanced": dict(scale="spline36", cscale="spline36", dscale="mitchell", correct_downscaling="yes", deband="no"),
    "max": dict(scale="ewa_lanczossharp", cscale="ewa_lanczossharp", dscale="mitchell", sigmoid_upscaling="yes", correct_downscaling="yes",
                deband="yes", deband_iterations="2", deband_grain="16"),
}
DENOISE = {"light": "hqdn3d=1.5:1.2:3:2.5", "medium": "hqdn3d=3:2.5:6:5"}


class Player:
    def __init__(self, wid: int, settings: dict):
        mpv = load_mpv()
        if mpv is None:
            raise RuntimeError(f"libmpv not available: {_mpv_error}")
        self.settings = settings
        opts = dict(
            wid=str(int(wid)), input_default_bindings="no", input_vo_keyboard="no", osc="no", osd_level="0",
            keep_open="yes", idle="yes", force_window="yes", cursor_autohide="1000",
            hwdec=settings.get("hwdec") or "auto-safe",
            hwdec_codecs="all",                      # allow HEVC / AV1 / VP9 / H.264 hardware decode
            vo=os.environ.get("AURORA_VO") or ("gpu" if sys.platform == "darwin" else "gpu-next"), gpu_api="d3d11" if sys.platform == "win32" else "auto",
            target_colorspace_hint="yes" if settings.get("hdr", "auto") == "auto" else "no",   # HDR10 signalling to Windows
            tone_mapping="bt.2390", hdr_compute_peak="yes",
            video_sync="audio", interpolation="no",
            cache="yes", demuxer_max_bytes="32MiB" if settings.get("lite") else "150MiB", demuxer_readahead_secs="6" if settings.get("lite") else "20",
            network_timeout="10", stream_lavf_o="reconnect=1,reconnect_streamed=1,reconnect_delay_max=5",
            user_agent="VLC/3.0.20 LibVLC/3.0.20", ytdl="no", log_handler=self._log, loglevel="warn",
            audio_channels="auto-safe", volume=str(settings.get("volume", 100)),
        )
        dev = settings.get("audio_device") or "auto"
        opts["audio_device"] = dev
        spdif = passthrough_codecs(settings)
        if spdif:
            opts["audio_spdif"] = spdif
        if settings.get("audio_exclusive"):
            opts["audio_exclusive"] = "yes"
        if sys.platform != "win32" or os.environ.get("AURORA_VO"):
            opts.pop("gpu_api", None)
        if sys.platform == "darwin":
            opts["hwdec"] = settings.get("hwdec") or "videotoolbox"
            for k in ("target_colorspace_hint",): opts.pop(k, None)
        if os.environ.get("AURORA_VO"):
            for k in ("target_colorspace_hint", "tone_mapping", "hdr_compute_peak"):
                opts.pop(k, None)
        tm = settings.get("tone_mapping") or "auto"
        if tm != "auto" and not os.environ.get("AURORA_VO"): opts["tone_mapping"] = tm
        if int(settings.get("display_peak") or 0) > 0 and not os.environ.get("AURORA_VO"): opts["target_peak"] = str(int(settings["display_peak"]))
        if not settings.get("lite"):
            ts = int(settings.get("timeshift") or 0)            # minutes of live rewind kept in RAM (~1 MiB/s of stream assumed)
            if ts > 0:
                opts.update(demuxer_seekable_cache="yes", demuxer_max_back_bytes=f"{ts * 60}MiB", demuxer_max_bytes="150MiB")
            if settings.get("motion") == "smooth":
                opts.update(video_sync="display-resample", interpolation="yes", tscale="oversample")
        opts.update(cache_pause_initial="no", demuxer_lavf_probesize="750000", demuxer_lavf_analyzeduration="1")   # faster channel start / zapping
        q = settings.get("quality") or ("max" if settings.get("upscale") == "high" else "balanced")
        if not settings.get("lite") and not os.environ.get("AURORA_VO"):
            opts.update(QUALITY.get(q, QUALITY["balanced"]))
            if settings.get("hdr_enhance"): opts["hdr_contrast_recovery"] = "0.30"
        if (settings.get("denoise") or "off") != "off" and opts["hwdec"] in ("auto-safe", "auto", "nvdec", "d3d11va", "d3d11va-copy"):
            opts["hwdec"] = "auto-copy-safe"        # CPU filters need frames in system memory
        try:
            self.m = mpv.MPV(**opts)
        except Exception:
            log.exception("MPV init failed with gpu-next; retrying with default vo")
            opts.update(vo="gpu"); opts.pop("target_colorspace_hint", None)
            self.m = mpv.MPV(**opts)
        if settings.get("mute"):
            self.m.mute = True
        self.pic: dict = {}; self._vf = None; self._deint = None; self._h = 0; self.apply_picture(None)
        self.current_url = ""
        self.is_live = False
        self.expect_play = False
        self.retries = 0
        self.stall_since = None
        self.start_pos = 0.0
        self.sources: list[str] = []; self._refreshed: set[int] = set(); self.source_index = 0; self.loaded_at = 0.0; self.last_pos = -1.0; self.last_change = 0.0
        log.info("Player ready (hwdec=%s, passthrough=%s, device=%s)", opts["hwdec"], spdif or "off", dev)

    @staticmethod
    def _log(level, prefix, text):
        if level in ("error", "fatal", "warn"):
            log.warning("mpv[%s] %s", prefix, text.strip())

    # control
    STARTUP_TIMEOUT = 8.0     # no picture this long after (re)load -> recover
    FROZEN_SECS = 6.0          # live picture not advancing this long -> recover
    CACHE_STALL_LIVE = 8.0     # buffer-starved this long -> recover (VOD gets more patience)
    CACHE_STALL_VOD = 15.0

    def play(self, url: str, live: bool, start: float = 0.0, alternates=None):
        """alternates: backup URLs for the same content, tried in order when recovery is needed."""
        self.sources = [url] + [u for u in (alternates or []) if u and u != url]
        self.source_index = 0; self.retries = 0; self._refreshed = set()
        self._load(url, live, start)

    def _load(self, url: str, live: bool, start: float = 0.0):
        self.current_url, self.is_live, self.expect_play, self.start_pos = url, live, True, start
        self.stall_since = None; self.loaded_at = time.time(); self.last_pos = -1.0; self.last_change = time.time()
        log.info("Play %s (live=%s, source %d/%d)", url.split("?")[0], live, self.source_index + 1, len(getattr(self, "sources", [url])))
        self.m.start = f"{start:.0f}" if start > 5 else "0"
        self.m.pause = False
        self.m.play(url)

    def reload(self, next_source: bool = False):
        """Manual refresh. Pressing twice within 10 s moves on to the next backup source."""
        now = time.time()
        if next_source or (now - getattr(self, "_manual_at", 0) < 10 and len(self.sources) > 1):
            self.source_index = (self.source_index + 1) % len(self.sources)
        self._manual_at = now
        pos = 0.0 if self.is_live else self.position()[0]
        self._load(self.sources[self.source_index], self.is_live, pos)

    def stop(self):
        self.expect_play = False
        try:
            self.m.command("stop")
        except Exception:
            pass

    def toggle_pause(self):
        self.m.pause = not self.m.pause

    def seek(self, secs, absolute=False):
        try:
            self.m.command("seek", secs, "absolute" if absolute else "relative")
        except Exception:
            pass

    # ---- per-channel picture profile
    def apply_picture(self, profile: dict | None):
        """Global picture settings overlaid with a per-channel profile {motion, denoise, deband, deinterlace}."""
        s, p = self.settings, dict(profile or {})
        q = s.get("quality") or ("max" if s.get("upscale") == "high" else "balanced")
        self.pic = dict(motion=p.get("motion", s.get("motion") or "off"), denoise=p.get("denoise", s.get("denoise") or "off"),
                        deband=p.get("deband", "on" if QUALITY.get(q, {}).get("deband") == "yes" else "off"), deinterlace=p.get("deinterlace", s.get("deinterlace") or "auto"))
        if s.get("lite"): return
        sm = self.pic["motion"] == "smooth"
        for k, v in (("video-sync", "display-resample" if sm else "audio"), ("interpolation", "yes" if sm else "no"), ("tscale", "oversample" if sm else "mitchell"),
                     ("deband", "yes" if self.pic["deband"] == "on" else "no")):
            self._set(k, v)
        self._deint = None

    def _set(self, name, val):
        try: self.m[name] = val
        except Exception as e: log.debug("option %s not applied: %s", name, e)

    def _update_picture(self):
        """Once per second: denoise filter (<=1080p only, CPU) and deinterlacing."""
        if self.settings.get("lite"): return
        try: vp = self.m.video_params or {}
        except Exception: return
        h = int(vp.get("h") or 0)
        if h:
            want = DENOISE.get(self.pic.get("denoise")) if h <= 1080 else None
            if want != self._vf:
                try:
                    if want:
                        if "copy" not in str(self.m.hwdec_current or "") and (self.m.hwdec_current or "no") != "no": self.m.hwdec = "auto-copy-safe"
                        self.m.command("vf", "set", f"lavfi=[{want}]")
                    else: self.m.command("vf", "clr", "")
                    self._vf = want; log.info("Denoise filter: %s (video height %d)", want or "off", h)
                except Exception as e: log.debug("denoise filter failed: %s", e); self._vf = want
        mode = self.pic.get("deinterlace", "auto")
        if mode == "auto":
            try: on = bool((self.m.video_frame_info or {}).get("interlaced"))
            except Exception: on = False
        else: on = mode == "on"
        if on != self._deint:
            self._set("deinterlace", "yes" if on else "no"); self._deint = on
            if on: log.info("Deinterlacing enabled (%s)", mode)

    def behind_live(self) -> float:
        """Seconds the picture is behind the live edge (timeshift); 0 when at live or unknown."""
        try:
            if self.m.eof_reached: return 0.0
            end, pos = self.m.demuxer_cache_time, self.m.time_pos
            return max(0.0, float(end) - float(pos)) if end is not None and pos is not None else 0.0
        except Exception:
            return 0.0

    def go_live(self):
        try:
            end = self.m.demuxer_cache_time
            if end is not None: self.m.command("seek", float(end) - 0.3, "absolute")
        except Exception:
            pass

    def set_mute(self, on: bool):
        try:
            self.m.mute = bool(on)
        except Exception:
            pass

    def set_volume(self, v: int):
        self.m.volume = max(0, min(150, v))

    def set_track(self, kind: str, tid):
        setattr(self.m, "aid" if kind == "audio" else "sid", tid if tid not in (None, "no") else "no")

    def shutdown(self):
        try:
            self.m.terminate()
        except Exception:
            pass

    # state
    def tracks(self):
        try:
            return list(self.m.track_list or [])
        except Exception:
            return []

    def audio_devices(self):
        try:
            return [(d["name"], d.get("description", d["name"])) for d in self.m.audio_device_list]
        except Exception:
            return [("auto", "Auto")]

    def position(self):
        try:
            return float(self.m.time_pos or 0), float(self.m.duration or 0)
        except Exception:
            return 0.0, 0.0

    def tick(self):
        """Call once per second. Returns None, 'reconnect' (same source), 'switched' (backup source), 'failed' or 'ended'."""
        if not self.expect_play:
            return None
        self._update_picture()
        now = time.time()
        try:
            idle = bool(self.m.idle_active)
            paused = bool(self.m.pause)
            starved = bool(self.m.paused_for_cache) and not paused
            eof = bool(self.m.eof_reached)
        except Exception:
            return None
        pos, dur = self.position()
        if pos != self.last_pos:
            self.last_pos, self.last_change = pos, now
        if idle or eof:
            if not self.is_live and dur and pos >= dur - 5:
                self.expect_play = False; return "ended"
            log.warning("Stream ended/dropped (idle=%s eof=%s)", idle, eof)
            return self._retry(hard=idle)
        if starved:
            self.stall_since = self.stall_since or now
            if now - self.stall_since > (self.CACHE_STALL_LIVE if self.is_live else self.CACHE_STALL_VOD):
                log.warning("Buffer starved for %.0fs", now - self.stall_since); return self._retry()
        else:
            self.stall_since = None
        if self.is_live and not paused:
            if pos <= 0 and now - self.loaded_at > self.STARTUP_TIMEOUT:
                log.warning("No picture %.0fs after loading", now - self.loaded_at); return self._retry(hard=len(self.sources) > 1)
            if pos > 0 and now - self.last_change > self.FROZEN_SECS:
                log.warning("Picture frozen for %.0fs", now - self.last_change); return self._retry()
        if pos > 3 and now - self.last_change < 2:
            self.retries = 0; self._refreshed.clear()
        return None

    def _retry(self, hard: bool = False):
        """Recovery ladder. A stalled/frozen picture: reload the same source once (often enough), then rotate to backups.
        hard=True (stream failed to open at all, e.g. dead link): go straight to the next source."""
        mx = int(self.settings.get("max_reconnects", 6))
        if self.retries >= mx:
            self.expect_play = False
            log.error("Giving up after %d recovery attempts", self.retries)
            return "failed"
        self.retries += 1
        old, n = self.source_index, len(self.sources)
        if n <= 1 or (not hard and old not in self._refreshed):
            self._refreshed.add(old)
        else:
            self.source_index = (old + 1) % n
        switched = self.source_index != old
        log.warning("Recovery %d/%d: %s (source %d/%d)", self.retries, mx, "switching to backup source" if switched else "reloading same source", self.source_index + 1, len(self.sources))
        pos = 0.0 if self.is_live else self.position()[0]
        self._load(self.sources[self.source_index], self.is_live, pos)
        return "switched" if switched else "reconnect"

    def info(self) -> dict:
        """Actual detected stream/output properties (None = not detectable)."""
        m, d = self.m, {}
        g = lambda name: _safe(lambda: getattr(m, name))
        vp = g("video_params") or {}
        vtrack = next((t for t in self.tracks() if t.get("type") == "video" and t.get("selected")), {})
        atrack = next((t for t in self.tracks() if t.get("type") == "audio" and t.get("selected")), {})
        d["video_codec"] = g("video_format") or vtrack.get("codec")
        d["video_desc"] = g("video_codec")
        d["resolution"] = f"{vp['w']}x{vp['h']}" if vp.get("w") else None
        fps = g("container_fps") or g("estimated_vf_fps")
        d["fps"] = round(float(fps), 2) if fps else None
        gamma, prim, cm = vp.get("gamma"), vp.get("primaries"), vp.get("colormatrix")
        dvp = vtrack.get("dolby-vision-profile")
        if dvp is not None or cm == "dolbyvision":
            d["hdr"] = f"Dolby Vision (profile {dvp})" if dvp is not None else "Dolby Vision"
            d["hdr_note"] = "decoded and tone-mapped by mpv; not output as Dolby Vision"
        elif gamma == "pq":
            d["hdr"] = "HDR10 / PQ"
        elif gamma == "hlg":
            d["hdr"] = "HLG"
        elif gamma:
            d["hdr"] = "SDR"
        else:
            d["hdr"] = None
        hw = g("hwdec_current"); d["hwdec"] = "software (CPU)" if hw in (None, "", "no") else f"hardware ({hw})"
        d["audio_codec"] = g("audio_codec_name") or atrack.get("codec")
        prof = (atrack.get("codec-profile") or "") + " " + (g("audio_codec") or "")
        d["audio_profile"] = (atrack.get("codec-profile") or "") or None
        d["atmos"] = ("Dolby Atmos detected in stream" if "atmos" in prof.lower() else
                      ("Not detected" if d["audio_codec"] else None))
        ao = g("audio_out_params") or {}
        fmt = str(ao.get("format", ""))
        d["audio_output"] = "Bitstream passthrough (%s)" % fmt if fmt.startswith("spdif") else (f"PCM {ao.get('hr-channels') or ao.get('channels','')}" if ao else None)
        d["audio_device"] = g("audio_device")
        d["atmos_passthrough"] = bool(d["atmos"] and "detected in" in d["atmos"] and fmt.startswith("spdif"))
        return d


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def format_info(d: dict) -> str:
    def v(x, none="not detectable"):
        return str(x) if x not in (None, "") else none
    atmos = d.get("atmos")
    if atmos and d.get("atmos_passthrough"):
        atmos += " | output: Atmos bitstream passthrough ACTIVE"
    elif atmos and "detected in" in atmos:
        atmos += " | but output is NOT passthrough (decoded to PCM/ downmix)"
    lines = [
        ("Video codec", v(d.get("video_codec"))), ("Resolution", v(d.get("resolution"))), ("Frame rate", v(d.get("fps")) + (" fps" if d.get("fps") else "")),
        ("HDR format", v(d.get("hdr")) + (f" ({d['hdr_note']})" if d.get("hdr_note") else "")),
        ("Decoder", v(d.get("hwdec"))), ("Audio codec", v(d.get("audio_codec")) + (f" - {d['audio_profile']}" if d.get("audio_profile") else "")),
        ("Atmos", v(atmos)), ("Audio output", v(d.get("audio_output"))), ("Device", v(d.get("audio_device"))),
    ]
    return "\n".join(f"{k}: {x}" for k, x in lines)
