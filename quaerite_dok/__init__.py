"""Quaerites innpakning rundt DOK.Arealanalyse.Process (Quaerite-AS/quaerite-platform#3015).

Upstream-koden endres ikke. Innpakningen erstatter noen få navngitte funksjoner
i den pinnede versjonen av `dokanalyse` og i pygeoapi 0.22.0:

- `avbrudd`: analysen avbrytes når klienten kobler fra (del 3a).
- `vern.installer_tidsgrense`: tidsgrense per datasett (del 3b).
- `vern.installer_404_minne`: kartkatalogens 404 huskes en stund (del 3c).

`quaerite_dok.app:APP` er appen gunicorn starter (se `entrypoint.sh`).
Innpakningen er koblet til upstream-symbolene ved navn. Ved oppgradering av
Process eller pygeoapi kjøres testene i `tests/` mot den nye versjonen først.
"""
