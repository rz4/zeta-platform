# zeta-quartus: the fit stage. Quartus Prime Lite 25.1std + Cyclone V —
# the exact Build 1129 that produced every fit in the discovery tree.
# Image: ghcr.io/rz4/zeta-quartus   (~15 GB installed; build locally or
# on a large runner — see infra/README.md)
#
# Intel serves the installer only to a browser session, so the two
# files are downloaded BY A HUMAN (who thereby sees Intel's terms) into
# infra/quartus-dist/ (gitignored), and the build copies them in:
#   QuartusLiteSetup-25.1std.0.1129-linux.run
#   cyclonev-25.1std.0.1129.qdz
# Build: docker build -f infra/quartus.Dockerfile -t ghcr.io/rz4/zeta-quartus:25.1std .

FROM ubuntu:24.04

ARG QSETUP=QuartusLiteSetup-25.1std.0.1129-linux.run
ARG QDEV=cyclonev-25.1std.0.1129.qdz

# python3-numpy/-pygame: the fit driver (infra/fit_ci.py) assembles the
# cart and regenerates silicon/gen from spec.py before Quartus runs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates libglib2.0-0 locales \
        make g++ python3 python3-numpy python3-pygame \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8

# The device file must sit beside the installer; Lite needs no license.
COPY infra/quartus-dist/${QSETUP} infra/quartus-dist/${QDEV} /tmp/q/
RUN cd /tmp/q \
    && chmod +x ${QSETUP} \
    && ./${QSETUP} --mode unattended --accept_eula 1 \
         --installdir /opt/quartus \
    && rm -rf /tmp/q /opt/quartus/uninstall

ENV PATH=/opt/quartus/quartus/bin:$PATH \
    QUARTUS_ROOTDIR=/opt/quartus/quartus

RUN quartus_sh --version
