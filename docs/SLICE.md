# THE VERTICAL SLICE — the whole machine, once, thin

Defined 2026-11-19. The goal that orders everything else:

    power on the Pocket
      -> the boot film (face.zol, ten seconds, the machine's own chord)
      -> a menu on the glass
      -> select TEAR
      -> play it

with every layer underneath proven: the bitstream fitted ON CI with
all four corners quoted, the suite green, the shell launch bit-equal
to a direct boot (the cross across a launch, SEAMS 2's gate), and any
frame of it witnessable from a Menu+Start capture. When this exists,
the project has exercised everything it owns except the link.

## The stages, in dependency order

    1. THE FIT ON CI          blocked on a human browser download:
                              QuartusLiteSetup-25.1std.0.1129-linux.run
                              + cyclonev-25.1std.0.1129.qdz into
                              infra/quartus-dist/, then the image build
                              and push. The fit workflow is already
                              wired and will go green (or honestly red)
                              the moment the image exists. Its first
                              job gates build 101.
    2. THE GLASS QUEUE        every Claim carries its glass status;
                              `zeta suite --glass-queue` prints what
                              has never been witnessed on the Pocket.
                              The queue is burned down with sd push /
                              Menu+Start / sd witness.
    3. THE SHELL              face.zol ends by launching TEAR: the
                              library .zbin (shell + N games' images
                              and segments), OVL_* for the program,
                              DMA for the state, SEG_BASE so a game's
                              segment offsets survive relocation --
                              the slice's one law amendment. Gate: the
                              cross across a launch (shell -> game
                              bit-equal to the game booted directly,
                              from the launch frame on).
    4. TEAR, GROWN            FLAGSHIP.md stages 1-3: the second
                              attack, block, hitstop, the input
                              buffer; pad 2; best-of-three and a
                              results screen. The TND photographs in
                              FLAGSHIP.md are the art target for
                              stage 4, after the slice ships.
    5. THE FERRY AND THE EYE  zeta sd push; play; Menu+Start;
                              zeta sd witness. The thirty-fifth
                              witnessing closes the slice.

## What the slice deliberately leaves out

The link (two Pockets), the audio PLL seam (SEAMS 1 -- it should ride
the first silicon build after the slice, since DIV=6 needs the second
PLL anyway), the panning plates, and all of TEAR stage 4+. A slice is
thin on purpose; its job is to prove the column, not to furnish it.
