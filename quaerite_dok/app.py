"""ASGI-appen gunicorn starter: pygeoapis Starlette-app med Quaerites vern.

`entrypoint.sh` setter `WSGI_APP=quaerite_dok.app:APP`. Uten den starter
pygeoapi-bildet `pygeoapi.starlette_app:APP` uten vern.
"""
import pygeoapi
import dokanalyse.processor as prosess
import dokanalyse.services.analyses as analyses
import dokanalyse.services.kartkatalog as kartkatalog
from pygeoapi import starlette_app

from . import avbrudd, innstillinger, vern

vern.installer_tidsgrense(analyses, innstillinger.DATASETT_TIDSGRENSE_S)
vern.installer_404_minne(kartkatalog, innstillinger.KARTKATALOG_404_MINNE_S)

if innstillinger.AVBRYT_VED_FRAKOBLING:
    avbrudd.installer_prosess(prosess)
    avbrudd.installer_starlette(starlette_app, pygeoapi.__version__)

APP = starlette_app.APP
