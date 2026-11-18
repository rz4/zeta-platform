# pocket/ — the deploy layer

`zeta_glass.v` is the whole console with a video head: 60 Hz, 400×360 total,
320×288 active, one pixel per `ce_pix`. Frame work runs entirely inside
vblank (144,000 clocks at DIV=5 / 43.2 MHz vs tear.zol's ~126k worst
frame), so there is no tearing and no double buffer. `zeta glass CART`
proves its pixel stream bit-equal to the virtual machine's framebuffer
before anything is synthesized.

## template/ — the vendored APF shell

`template/` is Analogue's openFPGA core template (MIT), vendored via the
sibling zeta-ps15 tree (which compiled it for this same Cyclone V part),
with its core section replaced by 60 lines that instantiate `zeta_glass`:

- **PLL** (`core/mf_pllbase/mf_pllbase_0002.v`): 74.25 MHz ref →
  `clk_zeta` 43.2 MHz (5× dot), `clk_dot` 8.64 MHz, `clk_dot_90` (+90°
  for the scaler's DDR capture).
- **Dot strobe**: edge-detected *from* `clk_dot` inside the `clk_zeta`
  domain (`EXT_CE=1`), so RGB transitions sit at a fixed safe offset after
  each scaler sampling edge. zeta-ps15's first real-glass symptom was a
  floating pixel clock — rainbow noise; the wiring here exists so that
  cannot recur.
- **Pad**: APF `cont1_key` → spec.py bits (dirs/ABXY/L/R line up; start ←
  bit 15, select ← bit 14).
- **Cart**: `ZETA_BAKE_CART` initializes IMEM/DMEM from
  `pocket/gen/cart_*.hex`, written by `zeta deploy CART`.

## Cart loading: no Quartus per game

`cart_loader.v` streams the data slot's `cart.zbin` (4096 IMEM + 16384
DMEM words then the CRAM segment, little-endian, 80 KB + segment —
written by `zeta deploy`) from the
APF bridge into the console's boot port through a toggle-handshake clock
crossing, holding the console in reset until `dataslot_allcomplete`. The
bitstream still bakes the deploy-time cart as a fallback for a missing
file. Swapping games is copying one .zbin file onto the SD card.

## The flow

```
zeta cross CART     VM+GPU framebuffers bit-equal          (proven in sim)
zeta glass CART     scanned 60 Hz pixel stream bit-equal   (proven in sim)
zeta deploy CART    gates on cross + glass + the loader proof
                    (tb_loader: 8192 words across the real clock ratio),
                    writes build/pocket/ (SD tree + Assets/zeta/common/
                    cart.zbin), runs Quartus only if the bitstream is
                    missing, reverses .rbf -> .rbf_r
```

Then copy `build/pocket/{Platforms,Cores,Assets}` onto the SD card.
After the first deploy, new carts are just the one .zbin file.
