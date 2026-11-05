"""Del 3b og 3c mot upstreams egen kode i dokanalyse (Process@b9cf49f)."""
import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

import aiohttp
import pytest

import dokanalyse.services.analyses as analyses
import dokanalyse.services.kartkatalog as kartkatalog
from dokanalyse.models import ResultStatus

from quaerite_dok import vern


class _Analyse:
    def __init__(self):
        self.result_status = None
        self.status_code = 200
        self.duration = None


@pytest.fixture
def datasett(monkeypatch):
    """Upstreams `_run_analysis` med falske oppslag rundt `run_single_analysis`."""
    analyse = _Analyse()
    config = SimpleNamespace(name='flom_aktsomhets_omr', config_id=uuid4())

    async def get_dataset_config(_config_id):
        return config

    async def set_defaults(_analysis):
        return None

    monkeypatch.setattr(analyses, 'get_dataset_config', get_dataset_config)
    monkeypatch.setattr(analyses, 'set_analysis_defaults', set_defaults)
    monkeypatch.setattr(analyses, '_create_analysis', lambda *a: analyse)

    def kjor(varighet=None, feil=None):
        async def run_single_analysis(analysis, *_args):
            if feil:
                raise feil
            await asyncio.sleep(varighet)
            analysis.result_status = ResultStatus.NO_HIT_GREEN

        monkeypatch.setattr(analyses, 'run_single_analysis', run_single_analysis)
        vern.installer_tidsgrense(analyses, 0.2, sett=monkeypatch.setattr)
        emitter = SimpleNamespace(send_message=lambda *_a: None)

        return asyncio.run(analyses._run_analysis(
            config.config_id, True, None, 25833, None, 0, '', False, False, emitter))

    return kjor


def test_treigt_datasett_blir_error_408(datasett):
    start = time.monotonic()
    resultat = datasett(varighet=5)

    assert time.monotonic() - start < 1
    assert resultat.result_status == ResultStatus.ERROR
    assert resultat.status_code == vern.TIDSGRENSE_STATUSKODE


def test_raskt_datasett_er_uendret(datasett):
    resultat = datasett(varighet=0.01)

    assert resultat.result_status == ResultStatus.NO_HIT_GREEN
    assert resultat.status_code == 200


def test_eget_tidsavbrudd_i_datasettet_beholder_upstreams_kode(datasett):
    resultat = datasett(feil=asyncio.TimeoutError())

    assert resultat.result_status == ResultStatus.ERROR
    assert resultat.status_code == 500


def test_tidsgrense_0_slaar_av(monkeypatch):
    assert not vern.installer_tidsgrense(analyses, 0, sett=monkeypatch.setattr)


def test_installeres_bare_en_gang(monkeypatch):
    assert vern.installer_tidsgrense(analyses, 1, sett=monkeypatch.setattr)
    assert not vern.installer_tidsgrense(analyses, 1, sett=monkeypatch.setattr)


def _404(url: str) -> aiohttp.ClientResponseError:
    info = aiohttp.RequestInfo(url, 'GET', {}, url)
    return aiohttp.ClientResponseError(info, (), status=404, message='Not Found')


def test_404_fra_kartkatalogen_huskes(monkeypatch):
    kall = []

    async def hent(metadata_id, _session, *a, **k):
        kall.append(metadata_id)
        raise _404(f'https://kartkatalog.geonorge.no/api/getdata/{metadata_id}')

    monkeypatch.setattr(kartkatalog, 'get_or_create_kartkatalog_metadata', hent)
    monkeypatch.setattr(kartkatalog, 'get_session', lambda: None)
    assert vern.installer_404_minne(kartkatalog, 60, sett=monkeypatch.setattr)

    metadata_id = uuid4()

    async def tre_ganger():
        return [await kartkatalog.get_kartkatalog_metadata(metadata_id) for _ in range(3)]

    assert asyncio.run(tre_ganger()) == [None, None, None]
    assert kall == [str(metadata_id)]


def test_404_glemmes_etter_minnetiden(monkeypatch):
    kall = []

    async def hent(metadata_id, _session, *a, **k):
        kall.append(metadata_id)
        raise _404('x')

    monkeypatch.setattr(kartkatalog, 'get_or_create_kartkatalog_metadata', hent)
    monkeypatch.setattr(kartkatalog, 'get_session', lambda: None)
    vern.installer_404_minne(kartkatalog, 0.05, sett=monkeypatch.setattr)

    metadata_id = uuid4()

    async def to_ganger():
        await kartkatalog.get_kartkatalog_metadata(metadata_id)
        await asyncio.sleep(0.1)
        await kartkatalog.get_kartkatalog_metadata(metadata_id)

    asyncio.run(to_ganger())
    assert len(kall) == 2


def test_andre_feil_huskes_ikke(monkeypatch):
    kall = []

    async def hent(metadata_id, _session, *a, **k):
        kall.append(metadata_id)
        raise aiohttp.ClientConnectionError('nede')

    monkeypatch.setattr(kartkatalog, 'get_or_create_kartkatalog_metadata', hent)
    monkeypatch.setattr(kartkatalog, 'get_session', lambda: None)
    vern.installer_404_minne(kartkatalog, 60, sett=monkeypatch.setattr)

    metadata_id = uuid4()

    async def to_ganger():
        await kartkatalog.get_kartkatalog_metadata(metadata_id)
        await kartkatalog.get_kartkatalog_metadata(metadata_id)

    asyncio.run(to_ganger())
    assert len(kall) == 2
