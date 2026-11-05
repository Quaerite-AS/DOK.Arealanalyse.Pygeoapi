"""Tidsgrense per datasett og 404-minne for kartkatalogen (#3015 del 3b og 3c).

Begge erstatter en modulvariabel i `dokanalyse` (pinnet i `Dockerfile`). Upstream
slår opp navnene ved kall, så erstatningen virker uten å endre upstream-koden:

- `dokanalyse.services.analyses.run_single_analysis` og `_run_analysis`
  (`services/analyses.py` linje 16, 117–167 i Process@b9cf49f).
- `dokanalyse.services.kartkatalog.get_or_create_kartkatalog_metadata` og
  `_get_kartkatalog_metadata` (`services/kartkatalog.py` linje 7, 25–34).
"""
import asyncio
import time
from types import ModuleType
from typing import Any, Callable, Dict

import aiohttp
import structlog

_logger = structlog.get_logger('quaerite_dok.vern')

# Samme kode som upstream-adapterne gir egne tidsavbrudd (408 Request Timeout).
TIDSGRENSE_STATUSKODE = 408

_MERKE = '__quaerite_vern__'
_TIDSGRENSE_ATTR = '_quaerite_tidsgrense'


class DatasettTidsgrense(TimeoutError):
    """Datasettet brukte lengre tid enn tidsgrensen."""


def _allerede(funksjon: Callable) -> bool:
    return getattr(funksjon, _MERKE, False)


def _merk(funksjon: Callable) -> Callable:
    setattr(funksjon, _MERKE, True)
    return funksjon


def installer_tidsgrense(analyses: ModuleType, grense_s: float, sett: Callable = setattr) -> bool:
    """Ett datasett som overskrider `grense_s`, blir `ERROR` med `statusCode` 408.

    Upstreams `_run_analysis` fanger unntaket, setter `ERROR` og logger
    «Analysis failed». De andre datasettene i samme kall påvirkes ikke.
    """
    if grense_s <= 0 or _allerede(analyses.run_single_analysis):
        return False

    kjor_ett = analyses.run_single_analysis
    kjor_med_oppsett = analyses._run_analysis

    async def run_single_analysis(analysis: Any, *args: Any, **kwargs: Any) -> None:
        frist = asyncio.timeout(grense_s)

        try:
            async with frist:
                return await kjor_ett(analysis, *args, **kwargs)
        except TimeoutError:
            if not frist.expired():
                raise

            setattr(analysis, _TIDSGRENSE_ATTR, True)
            raise DatasettTidsgrense(
                f'Datasettet brukte mer enn {grense_s:g} s') from None

    async def _run_analysis(*args: Any, **kwargs: Any) -> Any:
        analysis = await kjor_med_oppsett(*args, **kwargs)

        if analysis is not None and getattr(analysis, _TIDSGRENSE_ATTR, False):
            analysis.status_code = TIDSGRENSE_STATUSKODE

        return analysis

    sett(analyses, 'run_single_analysis', _merk(run_single_analysis))
    sett(analyses, '_run_analysis', _merk(_run_analysis))
    _logger.info('Tidsgrense per datasett slått på', sekunder=grense_s)

    return True


def installer_404_minne(kartkatalog: ModuleType, minne_s: float, sett: Callable = setattr) -> bool:
    """En metadata-id som ga 404, spørres ikke på nytt før `minne_s` er gått.

    Svaret blir det samme som upstream gir ved 404: ingen `runOnDataset`.
    Minnet gjelder én arbeidsprosess og forsvinner ved omstart.
    """
    if minne_s <= 0 or _allerede(kartkatalog.get_or_create_kartkatalog_metadata):
        return False

    hent = kartkatalog.get_or_create_kartkatalog_metadata
    les = kartkatalog._get_kartkatalog_metadata
    husket: Dict[str, float] = {}

    def er_husket(metadata_id: str) -> bool:
        frist = husket.get(metadata_id)
        return frist is not None and frist > time.monotonic()

    async def get_or_create_kartkatalog_metadata(metadata_id: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return await hent(metadata_id, *args, **kwargs)
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                ny = not er_husket(metadata_id)
                husket[metadata_id] = time.monotonic() + minne_s

                if ny:
                    _logger.warning('Kartkatalog svarte 404, husket',
                                    metadata_id=metadata_id, sekunder=minne_s)
            raise

    async def _get_kartkatalog_metadata(metadata_id: Any) -> Any:
        if er_husket(str(metadata_id)):
            return None

        return await les(metadata_id)

    sett(kartkatalog, 'get_or_create_kartkatalog_metadata',
         _merk(get_or_create_kartkatalog_metadata))
    sett(kartkatalog, '_get_kartkatalog_metadata', _merk(_get_kartkatalog_metadata))
    _logger.info('404-minne for kartkatalogen slått på', sekunder=minne_s)

    return True
