"""Del 3a: frakobling avbryter analysen, mot ekte pygeoapi 0.22.0 Starlette-app."""
import asyncio
import json
import time

import pytest
import pygeoapi
from pygeoapi import starlette_app

from quaerite_dok import avbrudd
from tests import treg_prosess


@pytest.fixture(autouse=True)
def vern(monkeypatch):
    assert avbrudd.installer_prosess(treg_prosess, sett=monkeypatch.setattr)
    assert avbrudd.installer_starlette(starlette_app, pygeoapi.__version__,
                                       sett=monkeypatch.setattr)
    treg_prosess.nullstill()


def _scope(metode: str, sti: str) -> dict:
    return {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': metode, 'scheme': 'http', 'path': sti, 'raw_path': sti.encode(),
        'root_path': '', 'query_string': b'',
        'headers': [(b'host', b'localhost'), (b'content-type', b'application/json')],
        'client': ('127.0.0.1', 1), 'server': ('localhost', 5000),
    }


async def _kall(metode: str, sti: str, kropp: dict | None, frakobling_etter: float | None):
    """Kaller appen som uvicorn gjør; `frakobling_etter` sender `http.disconnect`."""
    meldinger = [{'type': 'http.request',
                  'body': json.dumps(kropp).encode() if kropp else b'',
                  'more_body': False}]
    svar: dict = {'status': None, 'kropp': b''}

    async def receive():
        if meldinger:
            return meldinger.pop(0)

        if frakobling_etter is None:
            await asyncio.Event().wait()

        await asyncio.sleep(frakobling_etter)

        return {'type': 'http.disconnect'}

    async def send(melding):
        if melding['type'] == 'http.response.start':
            svar['status'] = melding['status']
        elif melding['type'] == 'http.response.body':
            svar['kropp'] += melding.get('body', b'')

    await starlette_app.APP(_scope(metode, sti), receive, send)

    return svar


def test_frakobling_kansellerer_analysen():
    start = time.monotonic()
    svar = asyncio.run(_kall('POST', '/processes/treg/execution',
                             {'inputs': {'sekunder': 10}}, frakobling_etter=0.3))
    brukt = time.monotonic() - start

    assert treg_prosess.kansellert.wait(2), 'analysen ble ikke kansellert'
    assert not treg_prosess.ferdig.is_set()
    assert svar['status'] == avbrudd.KLIENT_BORTE
    assert brukt < 3, f'brukte {brukt:.1f} s, analysen fikk gå videre'


def test_uten_frakobling_svarer_som_for():
    svar = asyncio.run(_kall('POST', '/processes/treg/execution',
                             {'inputs': {'sekunder': 0.1}}, frakobling_etter=None))

    assert svar['status'] == 200
    assert json.loads(svar['kropp']) == {'ventet': 0.1}
    assert treg_prosess.ferdig.is_set()
    assert not treg_prosess.kansellert.is_set()


def test_frakobling_etter_svar_endrer_ingenting():
    svar = asyncio.run(_kall('POST', '/processes/treg/execution',
                             {'inputs': {'sekunder': 0.1}}, frakobling_etter=1))

    assert svar['status'] == 200
    assert treg_prosess.ferdig.is_set()


def test_andre_ruter_bruker_upstream():
    svar = asyncio.run(_kall('GET', '/processes', None, frakobling_etter=None))

    assert svar['status'] == 200
    assert 'treg' in svar['kropp'].decode()


def test_ukjent_pygeoapi_versjon_gir_upstream_oppforsel(monkeypatch):
    class Modul:
        execute_from_starlette = staticmethod(lambda *a, **k: None)

    assert not avbrudd.installer_starlette(Modul, '0.23.0', sett=monkeypatch.setattr)


def test_exec_async_uten_avbrudd_er_upstream():
    # Utenfor en forespørsel (ingen trådbinding) brukes upstreams exec_async.
    async def svar():
        return 42

    assert treg_prosess.exec_async(svar()) == 42
