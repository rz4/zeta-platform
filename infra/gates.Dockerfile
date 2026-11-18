# zeta-gates: the law, the cross, and the lint ratchet.
# Pinned to the discovery desktop's exact tools (2026-08):
#   Python 3.14, Verilator 5.052.
# Image: ghcr.io/rz4/zeta-gates

FROM python:3.14-slim-trixie AS verilator-build

ARG VERILATOR_VERSION=v5.052

RUN apt-get update && apt-get install -y --no-install-recommends \
        git make g++ autoconf flex bison help2man ca-certificates \
        libfl-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch ${VERILATOR_VERSION} \
        https://github.com/verilator/verilator /tmp/verilator \
    && cd /tmp/verilator \
    && autoconf && ./configure --prefix=/opt/verilator \
    && make -j"$(nproc)" && make install \
    && rm -rf /tmp/verilator

FROM python:3.14-slim-trixie

# g++/make: the cross compiles the Verilated model and the frame server.
# SDL -dev headers: pygame 2.6.1 has no cp314 wheel and builds from
# source, exactly as the discovery desktop's did. The cabinet runs
# headless under SDL_VIDEODRIVER=dummy.
RUN apt-get update && apt-get install -y --no-install-recommends \
        make g++ perl ccache pkg-config \
        libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
        libfreetype6-dev libportmidi-dev libjpeg62-turbo-dev \
        libfl2 zlib1g git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=verilator-build /opt/verilator /opt/verilator
ENV PATH=/opt/verilator/bin:$PATH \
    SDL_VIDEODRIVER=dummy \
    SDL_AUDIODRIVER=dummy

# Pinned to the discovery desktop (2026-11 survey): the law ran on these.
RUN pip install --no-cache-dir "setuptools<81" \
    && pip install --no-cache-dir \
        pytest==9.1.1 pytest-cov==7.1.0 numpy==2.5.3 pygame==2.6.1 pillow

RUN verilator --version && python --version
