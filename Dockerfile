FROM geopython/pygeoapi:0.22.0

# Upstream-koden er pinnet til faste commiter (Quaerite-AS/quaerite-platform#3015).
# Begge er det dok-motor-test kjørte fra bygget 2026-10-02 (Render bygger uten
# lagbuffer, og upstream main hadde ikke endret seg siden):
# - Process b9cf49f (2026-04-16, «Minor changes»), pakkeversjon 0.1.8.
# - Config ba1828e (2026-07-29, «Merge branch 'sikkerhet/clean-up'»).
#
# Slik oppgraderes de:
# 1. Les upstream-endringene mellom pinnet og ny commit (git log -p).
# 2. Bytt full SHA her. Byggets pip og git henter nøyaktig den commiten.
# 3. Kjør testene i tests/ mot ny Process (se .github/workflows/test.yml, som
#    leser SHA-en fra denne filen). Innpakningen i quaerite_dok/ er koblet til
#    upstream-funksjoner ved navn og må stemme med ny versjon.
# 4. Kontroller config/*.yml mot ny Config og ny DatasetConfig-modell.
# 5. Merge til main bygger dok-motor-test. Les loggen før prod-porten.
ARG DOKANALYSE_PROCESS_REF=b9cf49f3dc188531ee70ed2dd17741511ee66a43
ARG DOKANALYSE_CONFIG_REF=ba1828e62022077f1cb4ffb1cafebf0239ba09d5

ARG DEB_PACKAGES="\
    git \
    gdal-bin \
    libgdal-dev"

ARG PYTHON_PACKAGES="\
    starlette \
    uvicorn \
    git+https://github.com/kartverket/DOK.Arealanalyse.Process.git@${DOKANALYSE_PROCESS_REF}"

COPY pygeoapi-config.yml /pygeoapi/pygeoapi-config.yml
COPY entrypoint.sh /dokanalyse-entrypoint.sh

RUN apt update -y \
    && apt --no-install-recommends install -y ${DEB_PACKAGES} \
    && /venv/bin/python3 -m pip install --no-cache-dir gdal==$(gdal-config --version) ${PYTHON_PACKAGES} \
    && git init -q /mnt/dokanalyse/config \
    && git -C /mnt/dokanalyse/config fetch -q --depth 1 https://github.com/kartverket/DOK.Arealanalyse.Config.git ${DOKANALYSE_CONFIG_REF} \
    && git -C /mnt/dokanalyse/config checkout -q FETCH_HEAD \
    && chmod +x /dokanalyse-entrypoint.sh

COPY config/*.yml /mnt/dokanalyse/config/
COPY quaerite_dok /quaerite/quaerite_dok

ENV PYGEOAPI_CONFIG=/pygeoapi/pygeoapi-config.yml \
    WSGI_APP=quaerite_dok.app:APP \
    PYTHONPATH=/quaerite \
    DOKANALYSE_APP_FILES_DIR=/mnt/dokanalyse \
    DOKANALYSE_DATASETS_CONFIG_DIR=/mnt/dokanalyse/config \
    DOKANALYSE_CACHE_ON_STARTUP=false \
    DOKANALYSE_CLIENT_TIMEOUT=30 \
    DOKANALYSE_LOG_LEVEL=INFO \
    QUAERITE_DOK_DATASETT_TIDSGRENSE_S=30 \
    QUAERITE_DOK_KARTKATALOG_404_MINNE_S=3600 \
    QUAERITE_DOK_AVBRYT_VED_FRAKOBLING=true

ENTRYPOINT [ "/dokanalyse-entrypoint.sh" ]
