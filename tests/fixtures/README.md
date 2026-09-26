Warning snapshots were retrieved on 2026-09-26 for municipality 15030 (A Coruña),
with `dia=-1`. Only JSON whitespace was changed. Both requests returned HTTP 200:

- https://servizos.meteogalicia.gal/mgrss/predicion/adversos/jsonAvisosConcellos.action
- https://servizos.meteogalicia.gal/mgrss/predicion/adversos/jsonConcellosNivelMax.action

The integration tests pass these responses through MeteoGalicia-API, the real
coordinators and Home Assistant's entity setup. Additional cases inject a warning
for tomorrow, reorder days, simulate a failed query, and verify recovery.
