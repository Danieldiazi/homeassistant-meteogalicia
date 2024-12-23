"""Constants for the MeteoGalicia integration."""

DOMAIN = "meteogalicia"
INTEGRATION_NAME = "MeteoGalicia"

FORECAST_MAX_TEMPERATURE = "Forecast max temp. "
FORECAST_MIN_TEMPERATURE = "Forecast min temp. "
FORECAST_RAIN_PROBABILITY = "Forecast precipitation probability. "


CONF_ID_CONCELLO = "id_concello"
CONF_ID_ESTACION = "id_estacion"
CONF_ID_ESTACION_MEDIDA_DAILY = "id_estacion_medida_diarios"
CONF_ID_ESTACION_MEDIDA_LAST10MIN = "id_estacion_medida_ultimos_10_min"

#Timeout por defecto
TIMEOUT = 60 

STRING_NOT_UPDATE_SENSOR = "[%s] Couldn't update sensor (%s),%s"
STRING_UPDATE_SENSOR_COMPLETED = "[%s] Update of sensor completed"
STRING_NOT_UPDATE_AVAILABLE = "[%s] Still no update available (%s)"
STRING_MEASURE_NOT_AVAILABLE="Couldn't update sensor with measure %s, it's unavailable for station id: %s"
