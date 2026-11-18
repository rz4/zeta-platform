# zeta-quartus: the fit stage. Quartus Prime Lite 25.1std + Cyclone V —
# the exact Build 1129 that produced every fit in the discovery tree.
# Image: ghcr.io/rz4/zeta-quartus   (~15 GB installed; build locally or
# on a large runner — see infra/README.md)

FROM ubuntu:24.04

ARG QBASE=https://downloads.intel.com/akdlm/software/acdsinst/25.1std/1129/ib_installers
ARG QSETUP=QuartusLiteSetup-25.1std.0.1129-linux.run
ARG QDEV=cyclonev-25.1std.0.1129.qdz

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates libglib2.0-0 locales \
        make g++ python3 \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8

# The device file must sit beside the installer; unattended mode takes
# the EULA by flag (the human decision is made by whoever builds this
# image — Lite requires no license file).
RUN mkdir /tmp/q && cd /tmp/q \
    && curl -fL -o ${QSETUP} ${QBASE}/${QSETUP} \
    && curl -fL -o ${QDEV}   ${QBASE}/${QDEV} \
    && chmod +x ${QSETUP} \
    && ./${QSETUP} --mode unattended --accept_eula 1 \
         --installdir /opt/quartus \
    && rm -rf /tmp/q /opt/quartus/uninstall

ENV PATH=/opt/quartus/quartus/bin:$PATH \
    QUARTUS_ROOTDIR=/opt/quartus/quartus

RUN quartus_sh --version
