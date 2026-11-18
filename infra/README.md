# infra — the toolchain, containerized (FOUNDING step 2)

Why: synthesis was heavy enough to destabilize the discovery desktop.
These images take the heavy jobs off any one machine and make every
gate reproducible.

## The two images

### ghcr.io/rz4/zeta-gates (~1 GB)

Python 3.14 + Verilator 5.052 + pytest/numpy/pygame (headless SDL).
Runs the law tests, the cross, the lint ratchet, the regen gate, the
soak. Pinned to the discovery desktop's exact versions. Built and
pushed automatically by `.github/workflows/images.yml` whenever
`infra/` changes.

### ghcr.io/rz4/zeta-quartus (~15 GB)

Quartus Prime Lite 25.1std Build 1129 + Cyclone V device support — the
exact build behind every fit in the discovery tree (see any
`ap_core.fit.summary`). Runs the fit stage: four corners, the
ALM/M10K/DSP ledger.

Too large for a standard GitHub runner's disk to build comfortably;
build it locally (or on a big self-hosted runner) and push once —
Quartus versions change rarely, the image is effectively static:

    docker build -f infra/quartus.Dockerfile -t ghcr.io/rz4/zeta-quartus:25.1std .
    echo $GH_TOKEN | docker login ghcr.io -u rz4 --password-stdin
    docker push ghcr.io/rz4/zeta-quartus:25.1std

Installer and device file are fetched from Intel's public akdlm CDN
(no account needed for Lite); the Dockerfile passes `--accept_eula 1`,
so building the image is accepting Intel's EULA. Lite needs no
license file, and Cyclone V is fully supported in Lite.

## Version policy

The tree's own discipline applies: versions are PINNED, and a bump is
a commit with a reason, not a drift. The authority for "what version
is real" is the fit summary and the cross — if the images and the law
disagree, the gate fails loudly and the bump is investigated, never
waved through.

    tool        pinned      why this one
    Python      3.14        the law ran on it through discovery
    Verilator   5.052       built every cross since build ~90
    Quartus     25.1std     Build 1129 — all 76 discovery fits
