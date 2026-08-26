FROM geopython/pygeoapi:0.22.0

ARG DEB_PACKAGES="\
    git \
    gdal-bin \
    libgdal-dev"

ARG PYTHON_PACKAGES="\
    starlette \
    uvicorn \
    git+https://github.com/kartverket/DOK.Arealanalyse.Process.git@main"

COPY pygeoapi-config.yml /pygeoapi/pygeoapi-config.yml
COPY entrypoint.sh /dokanalyse-entrypoint.sh

RUN apt update -y \
    && apt --no-install-recommends install -y ${DEB_PACKAGES} \
    && /venv/bin/python3 -m pip install --no-cache-dir gdal==$(gdal-config --version) ${PYTHON_PACKAGES} \
    && git clone --depth 1 https://github.com/kartverket/DOK.Arealanalyse.Config.git /mnt/dokanalyse/config \
    && chmod +x /dokanalyse-entrypoint.sh

COPY config/*.yml /mnt/dokanalyse/config/

ENV PYGEOAPI_CONFIG=/pygeoapi/pygeoapi-config.yml \
    WSGI_APP=pygeoapi.starlette_app:APP \
    DOKANALYSE_APP_FILES_DIR=/mnt/dokanalyse \
    DOKANALYSE_DATASETS_CONFIG_DIR=/mnt/dokanalyse/config \
    DOKANALYSE_CACHE_ON_STARTUP=false \
    DOKANALYSE_CLIENT_TIMEOUT=30 \
    DOKANALYSE_LOG_LEVEL=INFO

ENTRYPOINT [ "/dokanalyse-entrypoint.sh" ]
