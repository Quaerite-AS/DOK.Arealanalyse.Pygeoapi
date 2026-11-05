#!/bin/bash

if [ -n "${DOKANALYSE_CACHE_ON_STARTUP+x}" ] && [ "$DOKANALYSE_CACHE_ON_STARTUP" = "true" ]; then
    /venv/bin/build-dokanalyse-cache
fi

# Quaerites vern rundt pygeoapi-appen (quaerite_dok/app.py, #3015). Settes her og
# ikke bare i Dockerfile, slik at en WSGI_APP i tjenestens miljø ikke slår det av.
if [ "${WSGI_APP:-}" != "quaerite_dok.app:APP" ]; then
    echo "WSGI_APP=${WSGI_APP:-<tom>} erstattes med quaerite_dok.app:APP"
fi
export WSGI_APP=quaerite_dok.app:APP

/entrypoint.sh
