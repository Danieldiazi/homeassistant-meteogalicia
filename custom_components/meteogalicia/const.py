"""Constants for the MeteoGalicia integration."""

DOMAIN = "meteogalicia"
INTEGRATION_NAME = "MeteoGalicia"

FORECAST_MAX_TEMPERATURE = "Forecast max temp. "
FORECAST_MIN_TEMPERATURE = "Forecast min temp. "
FORECAST_RAIN_PROBABILITY = "Forecast precipitation probability. "

URL_FORECAST_CONCELLO = "https://servizos.meteogalicia.gal/mgrss/predicion/jsonPredConcellos.action?idConc={}"
URL_OBS_CONCELLO = "https://servizos.meteogalicia.gal/mgrss/observacion/observacionConcellos.action?idConcello={}"
CONF_ID_CONCELLO = "id_concello"
