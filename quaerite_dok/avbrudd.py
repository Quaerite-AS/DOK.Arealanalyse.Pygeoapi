"""Avbryt analysen når klienten kobler fra (#3015 del 3a).

Slik kjører pygeoapi 0.22.0 prosessen (lest i `pygeoapi/starlette_app.py`):
`execute_from_starlette` kjører API-kallet i en executor-tråd og setter
uvicorns hovedløkke som trådens løkke (`call_api_threadsafe`). Upstreams
`exec_async` (`dokanalyse/utils/async_executor.py` linje 40–47 i Process@b9cf49f)
finner den løkka og kjører analysen som en task på den med
`run_coroutine_threadsafe`, mens tråden venter på `future.result()`. Ingenting
lytter etter frakobling, så analysen går ferdig selv om ingen venter.

Her erstattes to navn:

- `pygeoapi.starlette_app.execute_from_starlette`, bare for
  `POST /processes/{id}/execution`: kallet kjøres som før, men samtidig ventes
  det på `http.disconnect`. Kommer den først, avbrytes analysen og svaret blir
  499 (klienten er borte).
- `exec_async` i prosessmodulen: framtiden fra `run_coroutine_threadsafe`
  registreres, slik at avbruddet kan kansellere tasken. Kansellering når alle
  datasett-tasker i upstreams `TaskGroup` og de åpne aiohttp-kallene.
"""
import asyncio
import threading
import time
from concurrent.futures import Future
from http import HTTPStatus
from types import ModuleType
from typing import Any, Callable, Coroutine

import structlog

_logger = structlog.get_logger('quaerite_dok.avbrudd')

# Ikke-standard kode for «klienten lukket forbindelsen» (nginx). Ingen leser den.
KLIENT_BORTE = 499

PYGEOAPI_VERSJON = '0.22.0'

_MERKE = '__quaerite_avbrudd__'
_lokal = threading.local()


class Avbrudd:
    """Bindeleddet mellom forespørselen (hovedløkka) og prosessen (tråden)."""

    def __init__(self) -> None:
        self._laas = threading.Lock()
        self._framtid: Future | None = None
        self.avbrutt = False

    def registrer(self, framtid: Future) -> None:
        with self._laas:
            self._framtid = framtid

            if self.avbrutt:
                framtid.cancel()

    def avbryt(self) -> None:
        with self._laas:
            self.avbrutt = True

            if self._framtid is not None:
                self._framtid.cancel()


def gjeldende() -> Avbrudd | None:
    return getattr(_lokal, 'avbrudd', None)


def _kjor_i_traad(avbrudd: Avbrudd, kall: Callable, *args: Any) -> Any:
    _lokal.avbrudd = avbrudd

    try:
        return kall(*args)
    finally:
        _lokal.avbrudd = None


def _kjorende_loekke() -> asyncio.AbstractEventLoop | None:
    # Samme oppslag som upstreams `_get_running_event_loop`.
    try:
        loekke = asyncio.get_event_loop()
    except RuntimeError:
        return None

    return loekke if loekke.is_running() else None


def installer_prosess(prosessmodul: ModuleType, sett: Callable = setattr) -> bool:
    """Erstatter `exec_async` i modulen som kjører analysen."""
    original = prosessmodul.exec_async

    if getattr(original, _MERKE, False):
        return False

    def exec_async(coro: Coroutine) -> Any:
        avbrudd = gjeldende()
        loekke = _kjorende_loekke()

        if avbrudd is None or loekke is None:
            return original(coro)

        framtid = asyncio.run_coroutine_threadsafe(coro, loekke)
        avbrudd.registrer(framtid)

        return framtid.result()

    setattr(exec_async, _MERKE, True)
    sett(prosessmodul, 'exec_async', exec_async)

    return True


async def _vent_paa_frakobling(request: Any) -> None:
    while True:
        melding = await request.receive()

        if melding.get('type') == 'http.disconnect':
            return


def installer_starlette(starlette_app: ModuleType, versjon: str, sett: Callable = setattr) -> bool:
    """Erstatter `execute_from_starlette` for prosesskjøring.

    Koden under er `execute_from_starlette` fra pygeoapi 0.22.0, med venting på
    frakobling og trådbinding lagt til. Andre versjoner får upstream-oppførselen.
    """
    original = starlette_app.execute_from_starlette

    if getattr(original, _MERKE, False):
        return False

    if versjon != PYGEOAPI_VERSJON:
        _logger.warning('Avbrudd ved frakobling er ikke slått på: ukjent pygeoapi-versjon',
                        versjon=versjon, forventet=PYGEOAPI_VERSJON)
        return False

    prosess_api = starlette_app.processes_api.execute_process

    async def execute_from_starlette(api_function: Callable, request: Any, *args: Any,
                                     skip_valid_check: bool = False,
                                     alternative_api: Any = None) -> Any:
        if api_function is not prosess_api or alternative_api is not None:
            return await original(api_function, request, *args,
                                  skip_valid_check=skip_valid_check,
                                  alternative_api=alternative_api)

        api = starlette_app.api_
        api_request = await starlette_app.APIRequest.from_starlette(request, api.locales)

        if not skip_valid_check and not api_request.is_valid():
            headers, status, content = api.get_format_exception(api_request)
            return starlette_app._to_response(headers, status, content)

        loekke = asyncio.get_running_loop()
        avbrudd = Avbrudd()
        start = time.monotonic()
        arbeid = loekke.run_in_executor(
            None, _kjor_i_traad, avbrudd, starlette_app.call_api_threadsafe,
            loekke, api_function, api, api_request, *args)
        vakt = asyncio.ensure_future(_vent_paa_frakobling(request))

        try:
            await asyncio.wait({arbeid, vakt}, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            avbrudd.avbryt()
            vakt.cancel()
            raise

        if not arbeid.done():
            avbrudd.avbryt()
            _logger.warning('Analyse avbrutt: klienten koblet fra',
                            sekunder=round(time.monotonic() - start, 2),
                            prosess=args[0] if args else None)

            try:
                await arbeid
            except Exception:
                pass

            return starlette_app.Response(status_code=KLIENT_BORTE)

        vakt.cancel()
        headers, status, content = arbeid.result()

        if status != HTTPStatus.NO_CONTENT:
            content = starlette_app.apply_gzip(headers, content)

        return starlette_app._to_response(headers, status, content)

    setattr(execute_from_starlette, _MERKE, True)
    sett(starlette_app, 'execute_from_starlette', execute_from_starlette)
    _logger.info('Avbrudd ved frakobling slått på')

    return True
