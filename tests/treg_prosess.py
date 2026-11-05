"""En prosess som oppfører seg som `DokanalyseProcessor`, men bare venter.

`execute` kjører coroutinen med upstreams `exec_async`, slik
`dokanalyse/processor.py` linje 35 gjør i Process@b9cf49f.
"""
import asyncio
import threading

from pygeoapi.process.base import BaseProcessor
from dokanalyse.utils.async_executor import exec_async

METADATA = {
    'version': '0.0.1',
    'id': 'treg',
    'title': {'en': 'treg'},
    'description': {'en': 'treg'},
    'jobControlOptions': ['sync-execute'],
    'keywords': [],
    'links': [],
    'inputs': {
        'sekunder': {
            'title': 'sekunder',
            'description': 'sekunder',
            'schema': {'type': 'number'},
            'minOccurs': 0,
            'maxOccurs': 1,
        }
    },
    'outputs': {
        'svar': {
            'title': 'svar',
            'description': 'svar',
            'schema': {'type': 'object', 'contentMediaType': 'application/json'},
        }
    },
}

kansellert = threading.Event()
ferdig = threading.Event()


def nullstill() -> None:
    kansellert.clear()
    ferdig.clear()


class TregProsess(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, METADATA)

    def execute(self, data, outputs=None):
        return 'application/json', exec_async(self._vent(float(data.get('sekunder', 0))))

    async def _vent(self, sekunder: float):
        try:
            await asyncio.sleep(sekunder)
        except asyncio.CancelledError:
            kansellert.set()
            raise

        ferdig.set()

        return {'ventet': sekunder}
