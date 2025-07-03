# ============================
# Stage 1: Build libtorrent and rtorrent
# ============================
FROM alpine AS builder

ARG LIBTORRENT_VERSION=0.15.5
ARG RTORRENT_VERSION=0.15.5
ENV LIBTORRENT_VERSION=${LIBTORRENT_VERSION}
ENV RTORRENT_VERSION=${RTORRENT_VERSION}

# Install build tools and libtorrent's makedepends
RUN apk add --no-cache \
    curl \
    curl-dev \
    libcurl \
    alpine-sdk \
    autoconf \
    automake \
    libsigc++-dev \
    libtool \
    linux-headers \
    openssl-dev \
    zlib-dev \
    ncurses-dev \
    tinyxml2-dev

WORKDIR /build

# Download libtorrent source
RUN mkdir "/tmp/libtorrent" && \
    curl -fsSL "https://github.com/rakshasa/libtorrent/archive/refs/tags/v${LIBTORRENT_VERSION}.tar.gz" | \
    tar -xzf - -C "/tmp/libtorrent" --strip-components=1 && \
    cd "/tmp/libtorrent" && \
    autoreconf -ivf && \
    ./configure --disable-debug --disable-shared --enable-static --enable-aligned && \
    make -j$(nproc) CXXFLAGS="-w -O3 -flto -Werror=odr -Werror=lto-type-mismatch -Werror=strict-aliasing" && \
    make install

RUN mkdir "/tmp/rtorrent" && \
    curl -fsSL "https://github.com/rakshasa/rtorrent/archive/refs/tags/v${RTORRENT_VERSION}.tar.gz" | \
    tar -xzf - -C "/tmp/rtorrent" --strip-components=1 && \
    cd "/tmp/rtorrent" && \
    autoreconf -ivf && \
    ./configure --disable-debug --disable-shared --enable-static --enable-aligned --with-xmlrpc-tinyxml2 && \
    make -j$(nproc) CXXFLAGS="-w -O3 -flto -Werror=odr -Werror=lto-type-mismatch -Werror=strict-aliasing" && \
    make install


# ============================
# Stage 2: Final Image
# ============================
FROM ghcr.io/hotio/base:alpinevpn

EXPOSE 3000

ARG FLOOD_VERSION=4.9.3
ARG RTORRENT_VERSION=0.15.5

ENV PYTHONUNBUFFERED=1
ENV APP_DIR=/app \
    CONFIG_DIR=/config
ENV FLOOD_AUTH="false" \
    WEBUI_PORTS="3000/tcp,3000/udp"

# Install Python 3 and pip
RUN echo "**** install Python ****" && \
    apk add --no-cache python3 && \
    if [ ! -e /usr/bin/python ]; then ln -sf python3 /usr/bin/python ; fi && \
    \
    echo "**** install pip ****" && \
    rm /usr/lib/python3.12/EXTERNALLY-MANAGED && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    pip install --no-cache-dir --upgrade pip setuptools wheel

# Install RUNTIME dependencies for custom libtorrent and rtorrent, plus other tools
RUN apk add --no-cache \
    openssl \
    mediainfo 

# Install pyrosimple
RUN pip install --no-cache-dir 'pyrosimple[torque]'

# Install additional Python dependencies for pyrosimple-manager
RUN pip install --no-cache-dir requests

# Create APP_DIR and CONFIG_DIR if they might not exist
RUN mkdir -p ${APP_DIR} ${CONFIG_DIR}

COPY --from=builder /usr/local/bin/rtorrent "${APP_DIR}/rtorrent"

# Download Flood
RUN curl -fsSL "https://github.com/jesec/flood/releases/download/v${FLOOD_VERSION}/flood-linux-x64" > "${APP_DIR}/flood" && \
    chmod 755 "${APP_DIR}/flood"

# Copy pyrosimple-manager scripts into the container
RUN mkdir -p ${APP_DIR}/pyrosimple-manager
COPY pyrosimple-manager/*.py ${APP_DIR}/pyrosimple-manager/
RUN chmod 755 ${APP_DIR}/pyrosimple-manager/main.py && \
    # Create directory for pyrosimple-manager config \
    mkdir -p ${CONFIG_DIR}/pyrosimple-manager && \
    chmod 755 ${CONFIG_DIR}/pyrosimple-manager && \
    # Create symlink for easier access from rtorrent \
    ln -s ${APP_DIR}/pyrosimple-manager /scripts

# Clean up apk cache
RUN rm -rf /var/cache/apk/*

# Copy application configuration/scripts
COPY root/ /

# Add healthcheck that includes pyrosimple-manager checks
HEALTHCHECK --interval=60s --timeout=20s --start-period=180s --retries=3 \
    CMD python ${APP_DIR}/pyrosimple-manager/healthcheck.py || exit 1