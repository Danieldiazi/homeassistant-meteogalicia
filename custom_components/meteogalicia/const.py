"""Constants for the MeteoGalicia integration."""

DOMAIN = "meteogalicia"
INTEGRATION_NAME = "MeteoGalicia"

FORECAST_MAX_TEMPERATURE = "Forecast max temp. "
FORECAST_MIN_TEMPERATURE = "Forecast min temp. "
FORECAST_RAIN_PROBABILITY = "Forecast precipitation probability. "

LOG_PREFIX = "[MeteoGalicia]"

# Claves comunes de atributos
ATTR_INFORMATION = "information"
ATTR_INTEGRATION = "integration"
ATTR_ID = "id"
ATTR_FORECAST_DATE = "forecast_date"
ATTR_RAIN_PROB_NOON = "rain_probability_noon"
ATTR_RAIN_PROB_AFTERNOON = "rain_probability_afternoon"
ATTR_RAIN_PROB_NIGHT = "rain_probability_night"


CONF_ID_CONCELLO = "id_concello"
CONF_ID_ESTACION = "id_estacion"
CONF_ID_ESTACION_MEDIDA_DAILY = "id_estacion_medida_diarios"
CONF_ID_ESTACION_MEDIDA_LAST10MIN = "id_estacion_medida_ultimos_10_min"

# Timeout por defecto
TIMEOUT = 60 

# Mensajes de log (en inglés se mantienen claves, pero prefijados con LOG_PREFIX)
STRING_NOT_UPDATE_SENSOR = f"{LOG_PREFIX} [%s] Couldn't update sensor (%s),%s"
STRING_UPDATE_SENSOR_COMPLETED = f"{LOG_PREFIX} [%s] Update of sensor completed"
STRING_NOT_UPDATE_AVAILABLE = f"{LOG_PREFIX} [%s] Still no update available (%s)"
STRING_MEASURE_NOT_AVAILABLE = f"{LOG_PREFIX} Couldn't update sensor with measure %s, it's unavailable for station id: %s"
ATTR_CONNECTED_AT = "connected_at"
ATTR_API_LATENCY_MS = "api_latency_ms"
ATTR_SCAN_INTERVAL_S = "scan_interval_s"
