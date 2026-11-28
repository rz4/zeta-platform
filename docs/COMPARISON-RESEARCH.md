# Zeta against the consoles: researched figures and proposed changes

Written 2026-11-28. A companion to `ZETA-RECIPROCAL-DESIGN.md`. Nothing proposed here is built.

## How far to trust this

The research session could reach GitHub and web search only. copetti.org, problemkaputt.de, Wikipedia,
Sega Retro, n64brew, analogue.co and intel.com were all blocked. So each console figure carries a grade:

- **[F]** read in full from a GitHub copy of the source (Copetti's article sources, psx-spx, the GBATEK
  mirror, the 3DO SDK mirror, KallistiOS, pspsdk, libdragon, the MAME 3DO driver, the Pocket core
  template, the two rival cores' repositories);
- **[S]** seen only in a search result's summary of the page;
- **[u]** from memory, unverified.

Zeta's figures are **[r]** read from `main` at `4c308f6`, **[d]** taken from the Zeta-1 design document,
**[a]** arithmetic, **[s]** supposed.

**The weakest rows are the ones people quote most.** No real-game polygon count for any console comes
from a primary source. Treat every "in games" polygon figure as an order of magnitude.

## 1. Proposed changes

| # | change | today | proposed | whom it passes or matches | standing |
|---|---|---|---|---|---|
| 1 | reclaim (Zeta-1 stage 0) | busiest frame 97.4% [d] | about 80-83% [d] | holds 60 where both rival cores admit slowdown | measured in simulation [d] |
| 2 | one store | 2,048 cart-mesh faces [d] | 4,096 faces a frame, any mesh | twice the DS's hard cap of 2,048 [F] | designed [d] |
| 3 | program beside the picture | 65,536 instructions a frame, 3.9 M a second [r] | 262,144 a frame, 15.7 M a second [d] | about the GBA's 15 MIPS [S]; half the PlayStation's ~30 [u] | designed [d] |
| 4 | objects | 64 [r] | 256 | no console counts objects; needed for perception | proposed |
| 5 | the retina | pixels shown an object [r] | + where, how central, how bright, beside what | no counterpart in any machine surveyed | proposed |
| 6 | placed images in three weights | one full-screen plate with depth and a shadow bit [r] | cards, depth plates, lit plates, placed anywhere | PlayStation pre-drawn rooms used rectangles with one depth each [F]: depth a pixel passes them | proposed |
| 7 | light a pixel from tables | light a face or a corner [r] | a tint chosen by each pixel's normal | none of PlayStation, N64, Saturn, 3DO, DS, PSP lit finer than a corner [F]; the Dreamcast could (bump maps) and rarely did [F, S] | proposed |
| 8 | joined pages | 32 x 32 [r] | 64 or 128 square | passes the N64's 64 x 32 at 16 bits [S]; still under the PlayStation's 256 [F] and the DS's 1,024 [F] | proposed |
| 9 | slots re-aimed a band | 20 pages a frame [r] | up to 180 a frame [a] | about 245 KB of texels a frame against the N64's 4 KB at a time [F] | proposed |
| 10 | anchors and repeat | 6 or 11 clocks a textured pixel [d] | about 1 [d] | fill beside both consoles' [d] | mocked [d] |
| 11 | orthographic camera | perspective only [r] | a cell | lets image worlds pan exactly; the DS has it [F] | proposed |
| 12 | the field | none | 65,536 cells a frame by rule | no counterpart | proposed |
| 13 | far memory | 64 KB of state [r] | windows onto up to 46 MB | above every machine here in reach | designed [d] |
| 14 | the seal and the tape | a recorder [r] | a seal a frame, kept by the machine | no counterpart | proposed |
| 15 | **faster outer memory (new)** | not used | SDRAM clocked at two or three times the core | see 5.1: could cut a lit plate from 38% of a frame toward 13-19% [a, s] | from research |
| 16 | **streamed image field (new)** | -- | loaded on demand at a legislated latency, not at boot | see 5.2: boot loading would be 15-46 s | from research |
| 17 | **small saves kept small (new)** | 153 KiB [r] | save only what was written; the field outside the state unless asked | see 5.3: the rivals pause 17-30 s to save | from research |
| 18 | **four pads (new)** | two in law [r] | four | the dock gives four [F]; N64 core already has them | from research |

## 2. Home consoles of the fifth generation

| | Zeta-0 today | Zeta proposed | PlayStation | Nintendo 64 | Saturn | 3DO |
|---|---|---|---|---|---|---|
| processor | stack machine in the FPGA, 43.2 MHz [r] | the same | R3000A 33.87 MHz [F] | VR4300 93.75 MHz [F] | 2 x SH-2 28.6 MHz [F] | ARM60 12.5 MHz [F] |
| instructions a second | 3.9 M at most [r] | 15.7 M at most [d] | ~30 M [u] | 125 M rated; memory-bound in use [S, F] | ~25 M each [S] | ~10 M [S] |
| working memory | 64 KB + 8 MB cart segment [r] | + windows onto 46 MB | 2 MB + 1 MB video [F] | 4 MB shared [F] | 2 MB + ~1.5 MB video [F] | 2 MB + 1 MB video [F] |
| picture | 320 x 288, 15-bit [r] | the same | 320 x 240 or 512 x 240 typical, 15-bit [F] | 320 x 240 typical [F] | 320 or 352 x 240 [F] | 320 x 240, 15-bit [F] |
| frames a second, 3D games | 60, bounded [r] | 60, bounded | 30 typical, dips [S] | 20-30, dips [S] | 20-30 [S] | 10-20 [u] |
| polygons a frame, in games | 731-1,173 reach the glass [d] | up to 4,096 | Crash Bandicoot ~1,000 drawn [S]; later games more [u] | ~2,000-4,000 [u] | Daytona ~3,000 quads [S] | ~1,000 quads [u] |
| polygons a second, in games | 44,000-70,000 [a] | up to 245,760 [a] | ~30,000-90,000 [S] | ~60,000-100,000 [u] | ~60,000-90,000 [S] | ~20,000 [u] |
| polygons a second, on the box | -- | -- | 180,000 textured, 360,000 flat [S] | ~100,000 [S] | 200,000 textured [S] | none published |
| depth a pixel | yes, 16-bit [r] | yes | no, sorted [F] | yes [F] | no, sorted [F] | no [F] |
| edges | exact, 4 sub-pixel bits [r] | the same | whole pixels [F] | 2 sub-pixel bits [S, F] | whole pixels [u] | fractional corners [F] |
| texture perspective | exact [r] | exact at anchors [d] | none [F] | exact [F] | none on polygons [F] | none [F] |
| texel filtering | none [r] | none | none [F] | three-point [F] | none [F] | none [F] |
| smaller texture levels | yes, 4 [r] | yes | no [F] | yes, halves texture memory [F] | no [u] | no [u] |
| largest texture | 32 x 32 [r] | 128 x 128 joined | 256 x 256 [F] | 64 x 32 at 16-bit; 64 x 64 at 4-bit [S] | 504 x 255 [S] | not found |
| texture store | 20 pages, 27,200 texels [r] | 20 resident, 180 a frame, from 46 MB | ~512 KB after framebuffers [F] | 4 KB at a time [F] | 512 KB shared [F] | shared with all else [F] |
| light | a face or a corner [r] | **a pixel**, from tables | a corner [F] | a corner [F] | a corner, in software [F] | a quad [F] |
| blending | mix and add [r] | the same | four fixed modes [F] | yes [F] | badly limited [F] | fixed ratios [F] |
| fog | yes [r] | yes | a corner only [F] | yes [F] | no [F] | no [u] |
| geometry in hardware | yes, in the picture's sequencer [r] | yes | coprocessor [F] | programmable coprocessor [F] | no [F] | maths helper only [F] |
| pre-drawn scenery | depth a pixel, shadow mask [r] | + light a pixel, placed, panned | flat, masks with one depth each [F] | flat [S] | flat layers [F] | flat |
| sound | 16 voices, 48 kHz [r] | the same | 24 voices, 44.1 kHz [F] | software, 16-24 voices [F] | 32 voices, 44.1 kHz [F] | software, 44.1 kHz [F] |
| the machine knows what it showed | pixels an object [r] | + where, how bright, beside what | no | no | no | no |

## 3. Handhelds and the generation above

| | Zeta proposed | Nintendo DS | Game Boy Advance | PSP-1000 | Dreamcast |
|---|---|---|---|---|---|
| processor | stack machine, 43.2 MHz | ARM9 67 MHz + ARM7 34 MHz [F] | ARM7 16.78 MHz [F] | MIPS up to 333 MHz, 222 at launch [S] | SH-4 200 MHz [F] |
| instructions a second | 15.7 M at most | ~75 M + ~30 M [u] | ~15 M [S] | not found | 360 M rated [S] |
| working memory | 64 KB + windows onto 46 MB | 4 MB + 656 KB video [F] | 288 KB + 96 KB video [F] | 32 MB + 2 MB video [F] | 16 MB + 8 MB video [F] |
| picture | 320 x 288, 15-bit | 256 x 192, 18-bit [F] | 240 x 160, 15-bit [F] | 480 x 272 [F] | 640 x 480 [F] |
| frames a second, 3D | 60, bounded | 60 by design; many games 30 [F, u] | ~20-30 [S] | 30 typical [u] | 30 or 60 [u] |
| polygons a frame | up to 4,096 | **2,048 hard cap**, 6,144 corners [F] | a few hundred, in software [S] | ~15,000-60,000 [u] | ~20,000-50,000 [S] |
| polygons a second | up to 245,760 | 122,880 at the cap [a] | ~3,000-10,000 [u] | 0.5-2 M [u]; 33 M on the box [S] | 1-3 M [S]; 3 M on the box [S] |
| depth a pixel | yes | yes [F] | no hardware 3D [F] | yes [F] | yes, by tile [F] |
| edges | exact | whole pixels [u] | -- | sub-pixel, inferred [F] | sub-pixel [u] |
| texture perspective | exact at anchors | exact [F] | -- | exact [F] | exact [u] |
| texel filtering | none | none [F] | -- | bilinear, trilinear [F] | bilinear and better [F] |
| largest texture | 128 x 128 joined | 1,024 x 1,024 [F] | -- | 512 x 512 [F, indirect] | 1,024 x 1,024 [F] |
| texture store | 180 pages a frame from 46 MB | up to 512 KB [F] | -- | 2 MB shared [F] | ~4-6 MB [u] |
| light | **a pixel**, from tables | a corner, hardware [F] | -- | a corner, hardware [F] | a corner, on the CPU; bump maps supported, rare [F, S] |
| outline and toon | outline [r] | both [F] | -- | toon by texture [F] | -- |
| sound | 16 voices, 48 kHz | 16 channels, 32.768 kHz [F] | 2 PCM + 4 tone [F] | software, 32 voices [F] | 64 channels, 44.1 kHz [F] |
| the machine knows what it showed | yes, and more | no | no | no | no |

## 4. The Pocket itself, and the two rivals on it

| | value | grade |
|---|---|---|
| the chip | Cyclone V 5CEBA4F23C8: 18,480 ALMs, 308 block RAMs, 66 DSP blocks | [F] part, [S] counts |
| SDRAM | 64 MB, 16-bit, rated to 166 MHz; the N64 core drives it at 125 MHz | [S], [F] |
| PSRAM | two of 16 MB; the PlayStation core's author could not make synchronous bursts pass on his Pocket | [S], [F] |
| SRAM | 256 KB, 55 ns | [S] |
| video a core may send | up to 800 x 720, 1 to about 50 MHz dot clock, 47 to about 61 Hz, 24-bit | [S] |
| sound | 48 kHz, 16-bit stereo, fixed | [S] |
| link port | four two-way lines; no speed limit documented | [F] |
| pads | four when docked | [F] |
| loading into memory at launch | about 1 MB a second (N64 core author); "a few megabytes per second" (Analogue) | [F], [S] |
| saving a state | about 0.1 MB a second (PlayStation core author) | [F] |

| | PlayStation core | N64 core | Zeta |
|---|---|---|---|
| project, version | GuardianSoul, v0.6.1, 27 Nov 2026 [F] | MIRLO 64, v1.0.1, 27 Nov 2026 [F] | build 106 on `main` [r] |
| logic used | "already fills" the chip [F] | 17,885-17,941 of 18,480 ALMs, 97% [F] | 18,194, 98.5% [d] |
| timing margin | not published | +0.003 to +0.036 ns [F] | +0.706 ns [d] |
| speed | "some games may run slower than on a real console" [F] | console rates, typically 20-30 [F, S] | 60, bounded [r] |
| saving a state | ~2 MB, up to ~30 s [F] | 1-3 MB; wake ~17 s at 3 MB [F] | 153 KiB, about 1.5 s; not yet built [r] |
| library | most games tried play [F] | claims over 99% [F] | one game [r] |

For the future window: the MiSTer's chip has about 41,500 ALMs and 553 block RAMs [F, u], 2.2 times the
Pocket's logic.

## 5. What the research changes in the design

**5.1 The outer memory can be faster than the design assumed.** The design costs a lit plate at three
words a pixel and a word a core clock: 38% of a frame for a full screen. The SDRAM is rated to 166 MHz
and a rival core runs it at 125 MHz. Driven at two or three times Zeta's 43.2 MHz, a lit plate could
fall toward 13-19% of a frame [a, s], which would allow two overlapping plates, or plates with
transparency over plates. This is the largest single gain the research found and it needs a timing
experiment, not a design.

**5.2 The image field cannot be loaded at boot.** At about 1 MB a second, 46 MB is most of a minute, and
"nothing ever loads" would stop being true. It has to arrive on demand through the card path, at a
latency the law states, as SD slots already do (`SD_LATENCY`).

**5.3 The small save is a real advantage and the design endangers it.** The rivals take 17-30 seconds to
save or wake because the Pocket writes at about 0.1 MB a second. Zeta's 153 KiB would take under two. A
2 MB field and megabytes of far state would give that away unless a save holds only what was written.

**5.4 The nearest rival is the Nintendo DS, not the PlayStation.** It is the only machine here built
around a fixed number of polygons a frame at 60, with hardware geometry, exact perspective, no filtering,
outlines, and a comparable screen. Zeta proposed has twice its polygon cap, more pixels, exact edges and
light a pixel; the DS has far larger textures, toon shading, edge smoothing and shadow volumes.

**5.5 Light a pixel is confirmed as the distinguishing feature.** Nothing below the Dreamcast lit finer
than a corner, and the Dreamcast's bump mapping was hardly used.

**5.6 Depth a pixel in pre-drawn scenery is confirmed as new for the generation.** The PlayStation's
Resident Evil 2 stored rectangles of mask, each with a single depth.

**5.7 My earlier polygon figures were too generous to the consoles.** I wrote 1,500-3,000 triangles a
frame for the PlayStation and N64. The only sourced game figure is about 1,000 drawn in Crash Bandicoot.
Zeta-0's measured 731-1,173 at 60 is already 44,000-70,000 a second, inside the range real games of that
generation reached.

**5.8 Resolution is Zeta's choice.** The Pocket would take 800 x 720. Not proposed: at a clock a pixel,
four times the pixels do not fit in a frame.

## 6. Where it stands after all of it

- **Above every machine surveyed:** bounded 60, perception, the field, the seal, small saves.
- **Above the fifth generation and the DS:** light a pixel, depth in pre-drawn scenery, polygons a second.
- **About level with the fifth generation:** polygons a frame, sound.
- **Below the PlayStation, Saturn and DS:** texture size.
- **Below the N64:** filtering, processor.
- **Far below the PSP and Dreamcast** on every measure of the picture except light a pixel in still
  scenery. They are a generation on and not a fair target.

## 7. Main sources

- Console architecture articles (source repository): https://github.com/flipacholas/Architecture-of-consoles
- PlayStation hardware: https://github.com/psx-spx/psx-spx.github.io
- Resident Evil 2 room format: https://github.com/pmandin/reevengi-tools/wiki
- DS and GBA hardware (GBATEK mirror): https://github.com/mgba-emu/gbatek
- N64 display processor interface: https://github.com/DragonMinded/libdragon
- Dreamcast graphics interface: https://github.com/KallistiOS/KallistiOS
- PSP graphics interface: https://github.com/pspdev/pspsdk
- 3DO SDK documents: https://github.com/trapexit/3do-devkit ; MAME driver notes: https://github.com/mamedev/mame
- Pocket core template: https://github.com/open-fpga/core-template
- PlayStation core: https://github.com/GuardianSoul/openfpga-PlayStation
- N64 core: https://github.com/tortugaveloz/MIRLO64
