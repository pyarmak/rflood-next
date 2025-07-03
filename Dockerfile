# ============================
# Stage 1: Build libtorrent
# ============================
FROM alpine:3.21 AS libtorrent-builder

ARG LIBTORRENT_VERSION=0.15.5
ENV LIBTORRENT_VERSION=${LIBTORRENT_VERSION}

# Install build tools and libtorrent's makedepends
RUN apk add --no-cache \
    curl \
    libcurl \
    alpine-sdk \
    autoconf \
    automake \
    libsigc++-dev \
    libtool \
    linux-headers \
    openssl-dev \
    zlib-dev

WORKDIR /build

# Download libtorrent source
RUN curl -fsSL "https://github.com/rakshasa/libtorrent/archive/refs/tags/v${LIBTORRENT_VERSION}.tar.gz" | \
    tar -xz --strip-components=1 -C .

# Copy patches
# COPY patches/0001-missing-header-algorithm.patch .

# Apply libtorrent patches
# RUN patch -p1 < 0001-missing-header-algorithm.patch

# Run prepare steps
RUN autoreconf -ivf

# Run build steps
RUN ./configure \
        --prefix=/usr \
        --disable-debug
RUN make

# Run package step into a staging directory
RUN make DESTDIR=/staging install

# ============================
# Stage 2: Build rtorrent
# ============================
FROM alpine:3.21 AS rtorrent-builder

ARG RTORRENT_VERSION=0.15.5
ENV RTORRENT_VERSION=${RTORRENT_VERSION}

# Install build tools and rtorrent's makedepends
RUN apk add --no-cache \
    curl \
    alpine-sdk \
    autoconf \
    automake \
    curl-dev \
    libsigc++-dev \
    libtool \
    ncurses-dev \
    tinyxml2-dev

# Copy compiled libtorrent (headers and libs) from the previous stage
COPY --from=libtorrent-builder /staging/usr/include /usr/include
COPY --from=libtorrent-builder /staging/usr/lib /usr/lib

WORKDIR /build

# Download rtorrent source
RUN curl -fsSL "https://github.com/rakshasa/rtorrent/archive/refs/tags/v${RTORRENT_VERSION}.tar.gz" | \
    tar -xz --strip-components=1 -C .

# Run rtorrent prepare steps (autoreconf only, no patches)
RUN autoreconf -ivf

# Run rtorrent build steps (should link against the copied libtorrent)
RUN ./configure \
        --prefix=/usr \
        --sysconfdir=/etc \
        --mandir=/usr/share/man \
        --localstatedir=/var \
        --enable-ipv6 \
        --disable-debug \
        --with-xmlrpc-tinyxml2
RUN make

# Run package step into a staging directory
RUN make DESTDIR=/staging install
RUN install -Dm644 doc/rtorrent.rc "/staging/usr/share/doc/rtorrent/rtorrent.rc"

# ============================
# Stage 3: Final Image
# ============================
FROM ghcr.io/hotio/base:alpinevpn

EXPOSE 3000 5000

ARG FLOOD_VERSION=4.9.3
ARG RTORRENT_VERSION=0.15.5

ENV PYTHONUNBUFFERED=1
ENV APP_DIR=/app \
    CONFIG_DIR=/config
ENV FLOOD_AUTH="false" \
    WEBUI_PORTS="3000/tcp,3000/udp,5000/tcp,5000/udp"

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
    curl \
    nginx \
    openssl \
    zlib \
    libsigc++ \
    ncurses-libs \
    tinyxml2 \
    libcurl \
    xmlrpc-c \
    xmlrpc-c-tools \
    mediainfo \
    libstdc++

# Install pyrosimple
RUN pip install --no-cache-dir 'pyrosimple[torque]'

# Install additional Python dependencies for pyrosimple-manager
RUN pip install --no-cache-dir requests

# Create APP_DIR and CONFIG_DIR if they might not exist
RUN mkdir -p ${APP_DIR} ${CONFIG_DIR}/rpc2

# Copy the compiled libtorrent shared libraries from the libtorrent-builder stage
COPY --from=libtorrent-builder /staging/usr/lib/libtorrent.so.* /usr/lib/

# Copy the compiled rtorrent binary from the rtorrent-builder stage
COPY --from=rtorrent-builder /staging/usr/bin/rtorrent "${APP_DIR}/rtorrent"

RUN chmod 755 "${APP_DIR}/rtorrent"

# Copy the example rtorrent.rc config file from the rtorrent-builder stage
COPY --from=rtorrent-builder /staging/usr/share/doc/rtorrent/rtorrent.rc /usr/share/doc/rtorrent/rtorrent.rc.example

# Create the symbolic link
RUN ln -s "${CONFIG_DIR}/rpc2/basic_auth_credentials" "${APP_DIR}/basic_auth_credentials"

# Download Flood
RUN curl -fsSL "https://github.com/jesec/flood/releases/download/v${FLOOD_VERSION}/flood-linux-x64" > "${APP_DIR}/flood" && \
    chmod 755 "${APP_DIR}/flood"

# Copy application configuration/scripts
COPY root/ /

# Ensure init scripts have execute permissions
RUN chmod +x /etc/cont-init.d/* 2>/dev/null || true && \
    chmod +x /etc/s6-overlay/s6-rc.d/*/run 2>/dev/null || true

# Copy pyrosimple-manager scripts into the container
RUN mkdir -p ${APP_DIR}/pyrosimple-manager
COPY pyrosimple-manager/*.py ${APP_DIR}/pyrosimple-manager/
RUN chmod +x ${APP_DIR}/pyrosimple-manager/main.py && \
    # Create directory for pyrosimple-manager config \
    mkdir -p ${CONFIG_DIR}/pyrosimple-manager && \
    # Create symlink for easier access from rtorrent \
    ln -s ${APP_DIR}/pyrosimple-manager /scripts

# Add healthcheck that includes pyrosimple-manager checks
HEALTHCHECK --interval=60s --timeout=20s --start-period=180s --retries=3 \
    CMD python ${APP_DIR}/pyrosimple-manager/healthcheck.py || exit 1

# Clean up apk cache
RUN rm -rf /var/cache/apk/*