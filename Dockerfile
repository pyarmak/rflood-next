FROM ghcr.io/hotio/rflood:latest

ENV PYTHONUNBUFFERED=1

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

# Install pyrosimple
RUN pip install --no-cache-dir 'pyrosimple[torque]'

# Install psutil from Alpine packages (avoids compilation)
RUN apk add --no-cache py3-psutil

# Install additional Python dependencies for pyrosimple-manager
RUN pip install --no-cache-dir requests

# Copy pyrosimple-manager scripts into the container
RUN mkdir -p ${APP_DIR}/pyrosimple-manager
COPY pyrosimple-manager/*.py ${APP_DIR}/pyrosimple-manager/
COPY pyrosimple-manager/s6-stage2-hook.sh ${APP_DIR}/pyrosimple-manager/
RUN chmod -R 755 ${APP_DIR}/pyrosimple-manager && \
    ln -s ${APP_DIR}/pyrosimple-manager /scripts

# Set up S6_STAGE2_HOOK for dynamic service control
ENV S6_STAGE2_HOOK=${APP_DIR}/pyrosimple-manager/s6-stage2-hook.sh

# Clean up apk cache
RUN rm -rf /var/cache/apk/*

# Add healthcheck that includes pyrosimple-manager checks
HEALTHCHECK --interval=60s --timeout=20s --start-period=180s --retries=3 \
    CMD python ${APP_DIR}/pyrosimple-manager/healthcheck.py || exit 1