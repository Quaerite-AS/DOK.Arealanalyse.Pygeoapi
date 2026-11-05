"""Felles oppsett for testene.

GDAL finnes ikke i testmiljøet. `osgeo` erstattes derfor med en tom modul før
`dokanalyse` importeres; testene kaller ikke kode som bruker GDAL.

pygeoapi leser konfigurasjon og OpenAPI-dokument ved import, så de skrives til
en midlertidig katalog før `pygeoapi.starlette_app` importeres.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

for _navn in ['osgeo', 'osgeo.ogr', 'osgeo.osr', 'osgeo.gdal', 'osgeo.gdalconst']:
    sys.modules.setdefault(_navn, MagicMock())

_KATALOG = Path(tempfile.mkdtemp(prefix='quaerite-dok-test-'))
(_KATALOG / 'config').mkdir()
os.environ.setdefault('DOKANALYSE_APP_FILES_DIR', str(_KATALOG))
os.environ.setdefault('DOKANALYSE_DATASETS_CONFIG_DIR', str(_KATALOG / 'config'))

_PYGEOAPI_CONFIG = _KATALOG / 'pygeoapi-config.yml'
_PYGEOAPI_CONFIG.write_text("""
server:
  bind: {host: 0.0.0.0, port: 5000}
  url: http://localhost:5000
  mimetype: application/json; charset=UTF-8
  encoding: utf-8
  languages: [en]
  limits: {default_items: 20, max_items: 50}
  map:
    url: https://tile.openstreetmap.org/{z}/{x}/{y}.png
    attribution: OSM
logging:
  level: ERROR
metadata:
  identification:
    title: {en: test}
    description: {en: test}
    keywords: {en: [test]}
    keywords_type: theme
    terms_of_service: https://example.org
    url: https://example.org
  license: {name: CC-BY 4.0, url: https://example.org}
  provider: {name: test, url: https://example.org}
  contact: {name: test, email: test@example.org, url: https://example.org}
resources:
  treg:
    type: process
    processor:
      name: tests.treg_prosess.TregProsess
""", encoding='utf-8')
os.environ['PYGEOAPI_CONFIG'] = str(_PYGEOAPI_CONFIG)

_PYGEOAPI_OPENAPI = _KATALOG / 'openapi.yml'
os.environ['PYGEOAPI_OPENAPI'] = str(_PYGEOAPI_OPENAPI)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pygeoapi.openapi import generate_openapi_document  # noqa: E402

with _PYGEOAPI_CONFIG.open(encoding='utf-8') as _fil:
    _PYGEOAPI_OPENAPI.write_text(
        generate_openapi_document(_fil, 'yaml'), encoding='utf-8')
