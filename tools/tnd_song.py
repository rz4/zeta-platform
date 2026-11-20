# THE TND RECORD, BAKED: "Set It Off" cut into the archive's own song
# structure (archive TND song_structure.py) at this machine's recording
# rate, for the song build of carts/gen_tnd.py (TND_SONG=1).
#
# THE RATE is the wave page times the frame rate -- 256 samples a frame,
# 15,360 Hz (zeta/bakepcm.py) -- so every section here is a whole number
# of FRAMES as well as the archive's whole number of BARS: its period is
# the archive's bar count at 122 BPM, rounded to the nearest frame (a
# bar is 118.03 frames; the loop drifts under half a frame a pass). Each
# start snaps to the archive's downbeat grid, and each seam is folded
# exactly as _fold_seam does: the head equal-power crossfaded, over 40
# ms, with the audio that naturally follows the loop point.
#
# THE LAYOUT is the cart's: the reprise tail sits immediately before the
# intro, so the MOBIUS REPRISE (the record's end stitched into its
# start) is not a copy -- it is the section that starts at the tail and
# runs on through the intro. One table of (start, frames) serves all
# nine.
#
# Third-party media: the source stays outside this repo and the bake
# lands in the gitignored assets/tnd/song.npz. Only a local cart carries
# it (carts/gen_tnd.py, TND_SONG).
#
#   python3 tools/tnd_song.py [path/to/Set It Off.mp3]

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from zeta import bakepcm, spec  # noqa: E402

SRC = Path(sys.argv[1] if len(sys.argv) > 1
           else ROOT.parent / "archive" / "TND" / "Set It Off.mp3")
OUT = ROOT / "assets" / "tnd" / "song.npz"
HZ = bakepcm.PCM_HZ                 # 15,360
FR = spec.WAV_W                     # samples a frame

# the archive's sections (seconds) and grid, verbatim
SECTIONS = {
    "intro": (6.23, 18.04), "lift": (20.0, 25.91), "drive": (27.87, 39.68),
    "chorus": (59.35, 75.09), "verse": (75.09, 92.79),
    "surge": (100.66, 126.23), "breakdown": (130.17, 145.91),
    "climax": (165.6, 201.0)}
REPRISE_TAIL = (206.3, 207.6)
BPM, BEAT0_S, LOOP_XF_S = 122.0, 0.332, 0.040
# the cart's order: the tail first, so reprise = tail + intro, contiguous
ORDER = ("tail", "intro", "lift", "drive", "chorus", "verse", "surge",
         "breakdown", "climax")


def decode(path):
    if not shutil.which("ffmpeg"):
        sys.exit("tnd_song needs ffmpeg")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(HZ), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float64)


def fold(seg, period, xf):
    """song_structure._fold_seam"""
    t = np.arange(xf) / xf
    loop = seg[:period].copy()
    loop[:xf] = seg[:xf] * np.sqrt(t) + seg[period:period + xf] * np.sqrt(1 - t)
    return loop


def main():
    full = decode(SRC)
    beat = round(HZ * 60.0 / BPM)
    bar = beat * 4
    beat0 = int(BEAT0_S * HZ)
    xf = int(LOOP_XF_S * HZ)
    parts, bars = {}, {}
    for name, (a, b) in SECTIONS.items():
        start = int(a * HZ)
        k = round((start - beat0) / bar)
        snapped = max(0, beat0 + k * bar)
        nbars = max(1, round((int(b * HZ) - start) / bar))
        period = round(nbars * bar / FR) * FR          # whole frames
        parts[name] = fold(full[snapped:snapped + period + xf], period, xf)
        bars[name] = nbars
    tail = full[int(REPRISE_TAIL[0] * HZ):int(REPRISE_TAIL[1] * HZ)]
    tail = tail[:len(tail) // FR * FR].copy()
    tail[-xf:] *= np.sqrt(1 - np.arange(xf) / xf)      # out, into the intro
    parts["tail"] = tail
    # one gain for the whole record: its loudest 0.05% at full scale
    pk = np.percentile(np.abs(np.concatenate(list(parts.values()))), 99.95)
    out = {}
    for name in ORDER:
        q = np.clip(np.rint(parts[name] * (127.0 / pk)), -128, 127).astype(np.int8)
        out[name] = q
    frames = {n: len(out[n]) // FR for n in ORDER}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, order=np.array(ORDER),
                        frames=np.array([frames[n] for n in ORDER]),
                        bars=np.array([bars.get(n, 0) for n in ORDER]),
                        **out)
    tot = sum(frames.values())
    for n in ORDER:
        print(f"  {n:10s} {frames[n]:5d} frames  {frames[n] / 60:6.2f} s"
              + (f"  {bars[n]} bars" if n in bars else ""))
    print(f"  total {tot} frames = {tot / 60:.1f} s = "
          f"{tot * spec.WAV_WORDS:,} CRAM words")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
