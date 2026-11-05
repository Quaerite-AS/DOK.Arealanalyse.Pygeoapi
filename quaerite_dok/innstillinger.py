"""Innstillinger fra miljøet. Standardverdiene står i `Dockerfile`."""
from os import getenv


def _tall(navn: str, standard: float) -> float:
    verdi = getenv(navn, '').strip()

    if not verdi:
        return standard

    try:
        tall = float(verdi)
    except ValueError:
        return standard

    return tall if tall > 0 else 0


# Lengste tid ett datasett får bruke (dekning, spørringer, veiledning). 0 slår av.
DATASETT_TIDSGRENSE_S: float = _tall('QUAERITE_DOK_DATASETT_TIDSGRENSE_S', 30)

# Hvor lenge en 404 fra kartkatalogen huskes per metadata-id. 0 slår av.
KARTKATALOG_404_MINNE_S: float = _tall('QUAERITE_DOK_KARTKATALOG_404_MINNE_S', 3600)

# `false` slår av avbrudd ved frakobling.
AVBRYT_VED_FRAKOBLING: bool = getenv(
    'QUAERITE_DOK_AVBRYT_VED_FRAKOBLING', 'true').strip().lower() != 'false'
