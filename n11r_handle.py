# -*- coding: utf-8 -*-
"""
Handle Extend & Move — source-TC hesapları PER-CLIP FPS ile.
- OFFSET varsa: MediaStart/End + Left/Right (source frame) -> ±25 (mevcut kadar)
- OFFSET yoksa: FALLBACK_INOUT (MediaPoolItem in/out / start/end) -> ±25 (mevcut kadar)
- Retime güvenilmez ise SKIP + konsola not ([RETIME-SKIP])
- Çıkış TL 01:00:00:00; yerleştirme InsertClips(timecode) ile.
"""

import sys, os, importlib, importlib.util, re, datetime

EXPIRATION_DATE = datetime.date(2026, 1, 1)

def check_expiration():
    today = datetime.date.today()
    
    if today > EXPIRATION_DATE:
        print("\n" + "="*50)
        print("UYARI: n11r Extender script'inin kullanım süresi dolmuştur.")
        print("Lütfen nehircanatabek@yandex.com ile iletişime geçin.")
        print("="*50 + "\n")
        return False
    
    return True

# ======= AYARLAR =======
TARGET_EXTEND_FRAMES = 25
FILTER_COLOR = "Yellow"
RUNNING_CURSOR = True
ALIGN_TO_SOURCE_RECORD = False
OUTPUT_TL = "Extended_Timeline"
SKIP_UNCERTAIN_RETIME = True
DEBUG = True

# ======= API LOADER =======
def _append_paths(paths):
    for p in paths:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)

def get_resolve_app():
    if sys.platform.startswith("darwin"):
        _append_paths([
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/",
            os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"),
        ])
    elif sys.platform.startswith("win"):
        _append_paths([os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                         "Blackmagic Design","DaVinci Resolve","Support","Developer","Scripting","Modules")])
    else:
        _append_paths(["/opt/resolve/Developer/Scripting/Modules/"])

    for modname in ("DaVinciResolveScript", "fusionscript"):
        try:
            mod = importlib.import_module(modname)
            if hasattr(mod, "scriptapp"):
                try:
                    return mod.scriptapp("Resolve"), mod
                except Exception:
                    pass
        except Exception:
            pass

    for d in list(sys.path):
        p = os.path.join(d, "DaVinciResolveScript.py")
        if os.path.isfile(p):
            try:
                spec = importlib.util.spec_from_file_location("DaVinciResolveScript", p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "scriptapp"):
                    try:
                        return mod.scriptapp("Resolve"), mod
                    except Exception:
                        pass
            except Exception:
                pass

    if "bmd" in globals() and hasattr(globals()["bmd"], "scriptapp"):
        try: return globals()["bmd"].scriptapp("Resolve"), globals()["bmd"]
        except Exception: pass
    for g in ("fusion","fu","app"):
        if g in globals():
            obj = globals()[g]
            if hasattr(obj, "GetResolve"):
                try: return obj.GetResolve(), obj
                except Exception: pass
    raise RuntimeError("DaVinci Resolve scripting API bulunamadı.")

resolve, api_module = get_resolve_app()
pm = resolve.GetProjectManager(); project = pm.GetCurrentProject() if pm else None
mp = project.GetMediaPool() if project else None
timeline = project.GetCurrentTimeline() if project else None
if not (resolve and project and mp and timeline):
    raise RuntimeError("Resolve/Project/Timeline erişilemedi. Edit sayfasında çalıştır.")

if not check_expiration():
    exit()

# ======= FPS / TC =======
def get_timeline_fps():
    try:
        f = project.GetSetting("timelineFrameRate")
        return float(f) if f else 25.0
    except Exception:
        return 25.0

TL_FPS = get_timeline_fps()

def parse_fps(val, default=25.0):
    try:
        if isinstance(val, (int,float)): return float(val)
        if isinstance(val, str):
            return float(val.strip().replace(',', '.'))
    except Exception:
        pass
    return float(default)

def tc_to_frames(tc, fps):
    if tc is None: return None
    if isinstance(tc, (int,float)): return int(round(tc))
    if not isinstance(tc, str): return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2}):(\d{2}):(\d{2})\s*$", tc)
    if not m:
        try: return int(round(float(tc)))
        except Exception: return None
    h, mm, ss, ff = map(int, m.groups())
    return int(round((((h*3600)+(mm*60)+ss)*fps)+ff))

def frames_to_tc(fr, fps):
    fr = int(max(0, round(fr)))
    f = fr % int(fps)
    sec = fr // int(fps)
    s = sec % 60
    m = (sec // 60) % 60
    h = sec // 3600
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

# ======= yardımcılar =======
def item_name(it):
    for m in ("GetName","GetClipName","GetNameEx"):
        if hasattr(it,m):
            try:
                v = getattr(it,m)()
                if v: return v
            except Exception: pass
    return "Unnamed"

def props_map(obj):
    d = {}
    if hasattr(obj,"GetClipProperty"):
        try:
            raw = obj.GetClipProperty()
            if isinstance(raw, dict): d = raw.copy()
        except Exception: pass
    return {str(k).lower(): v for k,v in (d or {}).items()}

def get_text(p, *keys):
    for k in keys:
        v = p.get(k.lower())
        if v is None: continue
        if isinstance(v, (int,float)): return v
        if isinstance(v, str) and v.strip(): return v.strip()
    return None

def get_source_fps(mpi):
    p = props_map(mpi)
    f = p.get("fps") or p.get("frame rate") or p.get("media frame rate")
    return parse_fps(f, default=TL_FPS)

def tl_items():
    out=[]
    try: vcount = timeline.GetTrackCount("video")
    except Exception: vcount=8
    for ti in range(1, int(vcount)+1):
        lst=[]
        if hasattr(timeline,"GetItemListInTrack"):
            try: lst = timeline.GetItemListInTrack("video", ti) or []
            except Exception: lst=[]
        out.extend(lst or [])
    return out

def tl_color(it):
    if hasattr(it,"GetClipColor"):
        try: return it.GetClipColor()
        except Exception: pass
    return None

def gather_targets():
    try:
        d = timeline.GetSelectedItems()
        if isinstance(d, dict) and d: return list(d.values())
    except Exception: pass
    want = (FILTER_COLOR or "").lower()
    res=[]
    for it in tl_items():
        if (tl_color(it) or "").lower()==want:
            res.append(it)
    return res

def get_offsets(it):
    left = right = None
    for m in ("GetLeftOffset","GetHeadTrim","GetStartOffset"):
        if hasattr(it,m):
            try: left = int(round(getattr(it,m)())); break
            except Exception: pass
    for m in ("GetRightOffset","GetTailTrim","GetEndOffset"):
        if hasattr(it,m):
            try: right = int(round(getattr(it,m)())); break
            except Exception: pass
    return left, right

def get_media_tc_bounds(mpi):
    p = props_map(mpi)
    ms = get_text(p, "media start","start tc","start")
    me = get_text(p, "media end","end tc","end")
    return ms, me

def log_retime_skip(it, mpi, reason, src_fps):
    name = item_name(it)
    try:
        rec_in_f  = int(round(it.GetStart()))
        rec_out_f = int(round(it.GetEnd()))
    except Exception:
        rec_in_f = rec_out_f = None
    rec_in_tc  = frames_to_tc(rec_in_f, TL_FPS)  if isinstance(rec_in_f,  int) else "?"
    rec_out_tc = frames_to_tc(rec_out_f, TL_FPS) if isinstance(rec_out_f, int) else "?"
    ms_tc, me_tc = get_media_tc_bounds(mpi) if mpi else (None,None)
    mp = props_map(mpi) if mpi else {}
    reel = mp.get("reel name") or mp.get("reel") or mp.get("camera #") or ""
    sp = mp.get("speed")
    sp_note = f", speed={sp}" if (isinstance(sp,str) and sp.strip() and sp.strip()!="100") else ""
    print(f"[RETIME-SKIP] {name} | Reel:{reel} | Record {rec_in_tc}–{rec_out_tc} | Media {ms_tc or '?'}–{me_tc or '?'} | SrcFPS:{src_fps} | Neden: {reason}{sp_note}")

# ======= hesap — PER-CLIP FPS =======
def compute_source_frames_any(it):
    """
    Dönüş: (method, new_in_abs, new_out_abs, media_start_abs, hL, hR, (src_in_abs, src_out_abs), src_fps)
    Tüm *abs* değerler KAYNAK TC'nin frame uzayındadır (0 ≠ media start).
    """
    mpi = it.GetMediaPoolItem() if hasattr(it,"GetMediaPoolItem") else None
    if not mpi: return (None,)*8
    src_fps = get_source_fps(mpi)

    ms_tc, me_tc = get_media_tc_bounds(mpi)
    if not (ms_tc and me_tc): return (None,)*8
    ms_f = tc_to_frames(ms_tc, src_fps); me_f = tc_to_frames(me_tc, src_fps)
    if None in (ms_f, me_f) or me_f <= ms_f: return (None,)*8

    # 1) OFFSET (en doğru yol)
    l_off, r_off = get_offsets(it)
    if (l_off is None or r_off is None):
        if DEBUG:
            print(f"[DEBUG] OFFSET yok -> {item_name(it)} (retime olabilir)")
    if l_off is not None and r_off is not None:
        src_in = ms_f + max(0, l_off)
        src_out= me_f - max(0, r_off)
        hL = max(0, l_off); hR = max(0, r_off)
        useL = min(TARGET_EXTEND_FRAMES, hL)
        useR = min(TARGET_EXTEND_FRAMES, hR)
        new_in  = src_in  - useL
        new_out = src_out + useR
        if new_out > new_in:
            return ("OFFSET", int(new_in), int(new_out), int(ms_f), int(hL), int(hR), (int(src_in), int(src_out)), src_fps)

    # 2) FALLBACK_INOUT (in/out veya start/end); HEPSİ src_fps uzayında çözümlenir
    p = props_map(mpi)
    in_raw  = get_text(p, "in","clip in","source in","media in") or get_text(p,"start")
    out_raw = get_text(p, "out","clip out","source out","media out") or get_text(p,"end")
    if in_raw is None or out_raw is None:
        if DEBUG:
            keys_hint = [k for k in p.keys() if any(tag in k for tag in ("in","out","start","end","tc","fps"))]
            print(f"[DEBUG] FALLBACK_INOUT veri yok -> {item_name(it)} | anahtarlar: {keys_hint}")
        if SKIP_UNCERTAIN_RETIME:
            log_retime_skip(it, mpi, "in/out bulunamadı (retime/compound?)", src_fps)
        return (None,)*8

    in_f  = tc_to_frames(in_raw, src_fps) if isinstance(in_raw, str) else int(round(in_raw))
    out_f = tc_to_frames(out_raw, src_fps) if isinstance(out_raw, str) else int(round(out_raw))

    if not (ms_f <= in_f < out_f <= me_f):
        # relatif gibi -> media start'a göre düzelt
        in_f  = ms_f + max(0, in_f)
        out_f = ms_f + max(1, out_f)

    media_len = me_f - ms_f
    src_len   = max(1, out_f - in_f)

    covers_all_media = src_len >= media_len - 1 or (in_f == ms_f and out_f == me_f)
    if covers_all_media and SKIP_UNCERTAIN_RETIME:
        log_retime_skip(it, mpi, "in/out ~ tüm medya", src_fps)
        return (None,)*8

    if covers_all_media and not SKIP_UNCERTAIN_RETIME:
        try: rec_len = int(round(it.GetDuration()))
        except Exception: rec_len = src_len
        max_extra = max(0, media_len - rec_len)
        per_side  = min(TARGET_EXTEND_FRAMES, max_extra // 2)
        hL = hR = int(per_side)
        new_in  = ms_f
        new_out = ms_f + rec_len + per_side*2
    else:
        hL = max(0, in_f - ms_f)
        hR = max(0, me_f - out_f)
        useL = min(TARGET_EXTEND_FRAMES, hL)
        useR = min(TARGET_EXTEND_FRAMES, hR)
        new_in  = in_f  - useL
        new_out = out_f + useR

    new_in  = max(ms_f, new_in)
    new_out = min(me_f, new_out)
    if new_out <= new_in:
        if SKIP_UNCERTAIN_RETIME:
            log_retime_skip(it, mpi, "hesaplanan aralık geçersiz", src_fps)
        return (None,)*8

    return ("FALLBACK_INOUT", int(new_in), int(new_out), int(ms_f), int(hL), int(hR), (int(in_f), int(out_f)), src_fps)

# ======= çıkış TL =======
def ensure_output_timeline(name=OUTPUT_TL):
    try:
        n = project.GetTimelineCount()
        for i in range(1, int(n)+1):
            tl = project.GetTimelineByIndex(i)
            if tl and hasattr(tl,"GetName") and tl.GetName()==name:
                try:
                    if hasattr(tl,"SetSetting"):
                        tl.SetSetting("useCustomTimelineStartingTimecode","1")
                        tl.SetSetting("customTimelineStartingTimecode","01:00:00:00")
                except Exception: pass
                return tl
    except Exception: pass

    try:
        prev_use = project.GetSetting("useCustomTimelineStartingTimecode")
        prev_tc  = project.GetSetting("customTimelineStartingTimecode")
        project.SetSetting("useCustomTimelineStartingTimecode","1")
        project.SetSetting("customTimelineStartingTimecode","01:00:00:00")
    except Exception:
        prev_use = prev_tc = None

    new_tl=None
    try: new_tl = mp.CreateEmptyTimeline(name)
    except Exception: new_tl=None

    try:
        if prev_use is not None: project.SetSetting("useCustomTimelineStartingTimecode", prev_use)
        if prev_tc  is not None: project.SetSetting("customTimelineStartingTimecode", prev_tc)
    except Exception: pass

    if new_tl:
        try:
            if hasattr(new_tl,"SetSetting"):
                new_tl.SetSetting("useCustomTimelineStartingTimecode","1")
                new_tl.SetSetting("customTimelineStartingTimecode","01:00:00:00")
        except Exception: pass
    return new_tl

# ======= yerleştirme =======
def insert_range_by_frames(mpi, record_start_frame_TL, start_abs_src, end_abs_src, media_start_abs_src, out_tl, src_fps):
    """
    start_abs_src/end_abs_src/media_start_abs_src: KAYNAK FPS (src_fps) frame uzayı
    startFrame/endFrame Resolve'da KAYNAĞA GÖRE BAĞIL (0 = MediaStart)
    Yerleştirme timecode'u TL_FPS'e göre verilir.
    """
    if not out_tl or not mpi: return False
    try:
        rel_start = float(start_abs_src - media_start_abs_src)
        rel_end   = float(end_abs_src   - media_start_abs_src)
    except Exception:
        return False

    clip_info = {"mediaPoolItem": mpi, "startFrame": rel_start, "endFrame": rel_end}

    try: project.SetCurrentTimeline(out_tl)
    except Exception: pass

    ok=False
    tc_str = frames_to_tc(int(max(0, record_start_frame_TL)), TL_FPS)

    if hasattr(mp,"InsertClips"):
        try:
            items = mp.InsertClips([clip_info], tc_str)
            ok = bool(items)
        except Exception:
            ok=False

    if (not ok) and hasattr(out_tl,"SetCurrentTimecode"):
        try: out_tl.SetCurrentTimecode(tc_str)
        except Exception: pass
    if not ok:
        try:
            items = mp.AppendToTimeline([clip_info])
            ok = bool(items)
        except Exception:
            ok=False

    try: project.SetCurrentTimeline(timeline)
    except Exception: pass
    return ok

# ======= MAIN =======
def main():
    items = gather_targets()
    if not items:
        print("Uyarı: Timeline’da seçili/sarı klip yok."); return
    if DEBUG:
        print(f"[DEBUG] Timeline targets: {len(items)} -> {[item_name(i) for i in items]}")

    out_tl = ensure_output_timeline()
    cursor_TL = tc_to_frames("01:00:00:00", TL_FPS) if RUNNING_CURSOR else 0
    results=[]

    for idx, it in enumerate(items, 1):
        name = item_name(it)
        method, new_in_s, new_out_s, media_start_s, hL, hR, src_pair, src_fps = compute_source_frames_any(it)
        if not method:
            print(f"[{idx}] {name}: Kaynak aralık hesaplanamadı. (retime/compound?) Atlandı.")
            continue

        # recordFrame (TL frame 0 = TL start TC)
        if RUNNING_CURSOR:
            rec_start_TL = cursor_TL
        elif ALIGN_TO_SOURCE_RECORD and hasattr(it,"GetStart"):
            try: rec_start_TL = int(round(it.GetStart()))
            except Exception: rec_start_TL = 0
        else:
            rec_start_TL = 0

        mpi = it.GetMediaPoolItem() if hasattr(it,"GetMediaPoolItem") else None
        ok = insert_range_by_frames(mpi, rec_start_TL, new_in_s, new_out_s, media_start_s, out_tl, src_fps)

        if RUNNING_CURSOR and ok:
            cursor_TL += (new_out_s - new_in_s)

        si_tc = frames_to_tc(new_in_s, src_fps); so_tc = frames_to_tc(new_out_s, src_fps)
        uL = min(TARGET_EXTEND_FRAMES, hL); uR = min(TARGET_EXTEND_FRAMES, hR)
        results.append({"name":name,"method":method,"src_tc":(si_tc,so_tc),"handles":(hL,hR),"used":(uL,uR),"ok":ok})

    print("\n=== İşlem Özeti ===")
    print(f"Kaynak TL: {timeline.GetName() if hasattr(timeline,'GetName') else 'Current'} | TL_FPS: {TL_FPS} | Çıkış TL: {OUTPUT_TL}")
    for r in results:
        (hL,hR)=r["handles"]; (uL,uR)=r["used"]; (si,so)=r["src_tc"]
        print(f"- {r['name']} [{r['method']}]: Src {si}–{so} | Handles L/R: {hL}/{hR} | Extend Used L/R: {uL}/{uR} | Place: {'OK ✅' if r['ok'] else '⚠️'}")

if __name__ == "__main__":
    main()