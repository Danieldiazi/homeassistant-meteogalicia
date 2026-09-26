"""Config flow for MeteoGalicia integration."""

from __future__ import annotations

import voluptuous as vol
import requests

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import const
from .intervals import get_scan_interval, merge_entry_data

_INVALID_INTERVAL_MESSAGE = "Expected a positive integer"

CONF_CONFIGURATION_METHOD = "configuration_method"
CONF_PROVINCE = "province"
CONF_CONCELLO_SELECTION = "concello_selection"
CONFIGURATION_METHOD_LIST = "list"
CONFIGURATION_METHOD_MANUAL = "manual"
PROVINCES = ("A Coruña", "Lugo", "Ourense", "Pontevedra")


def _validate_interval(value):
    """Accept positive whole seconds or an explicitly cleared default."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise vol.Invalid(_INVALID_INTERVAL_MESSAGE)
    try:
        interval = int(value)
    except ValueError as err:
        raise vol.Invalid(_INVALID_INTERVAL_MESSAGE) from err
    if interval < 1:
        raise vol.Invalid(_INVALID_INTERVAL_MESSAGE)
    return interval


# Keep the form schema serializable by Home Assistant's frontend. The stricter
# check above also validates direct options-flow submissions before saving.
_INTERVAL_VALIDATOR = vol.Maybe(vol.All(vol.Coerce(int), vol.Range(min=1)))


class CannotConnect(Exception):
    """Raised when MeteoGalicia cannot be reached."""


class InvalidIdentifier(Exception):
    """Raised when MeteoGalicia does not recognize an identifier."""


class InvalidMeasure(Exception):
    """Raised when a station does not expose the selected measure."""


class RequestTimeout(Exception):
    """Raised when MeteoGalicia does not answer in time."""


def _first_item(data: dict, key: str) -> dict | None:
    """Return the first mapping in a payload list."""
    if not isinstance(data, dict):
        return None
    items = data.get(key)
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None
    return items[0]


def _station_name_and_measures(data: dict, *, daily: bool) -> tuple[str, set[str]]:
    """Extract the station name and available measure codes from an API payload."""
    if daily:
        day = _first_item(data, "listDatosDiarios")
        station = _first_item(day or {}, "listaEstacions")
    else:
        station = _first_item(data, "listUltimos10min")
    if station is None:
        raise InvalidIdentifier

    name = station.get("estacion")
    if not name:
        raise InvalidIdentifier
    measures = station.get("listaMedidas")
    codes = {
        str(item["codigoParametro"])
        for item in measures or []
        if isinstance(item, dict) and item.get("codigoParametro")
    }
    return str(name), codes


def _request_json(session: requests.Session, url: str) -> dict:
    """Fetch and decode one MeteoGalicia JSON endpoint."""
    response = session.get(url, timeout=const.CONFIG_FLOW_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _station_from_catalog(data: dict, id_estacion: str) -> dict:
    """Return a station from MeteoGalicia's authoritative station catalog."""
    stations = data.get("listaEstacionsMeteo") if isinstance(data, dict) else None
    if not isinstance(stations, list):
        raise CannotConnect
    for station in stations:
        if isinstance(station, dict) and str(station.get("idEstacion")) == id_estacion:
            return station
    raise InvalidIdentifier


def _validate_forecast(
    session: requests.Session, endpoint: str, id_concello: str
) -> str:
    """Validate one municipal forecast identifier."""
    payload = _request_json(session, endpoint.format(id_concello))
    pred_concello = payload.get("predConcello") if isinstance(payload, dict) else None
    if not isinstance(pred_concello, dict) or not pred_concello.get("nome"):
        raise InvalidIdentifier
    return f"MeteoGalicia {pred_concello['nome']}"


def _validate_station(
    session: requests.Session,
    user_input: dict,
    daily_endpoint: str,
    last10_endpoint: str,
) -> str:
    """Validate one station identifier and its optional selected measure."""
    id_estacion = user_input[const.CONF_ID_ESTACION]
    catalog = _request_json(session, const.STATIONS_URL)
    station = _station_from_catalog(catalog, id_estacion)
    name = station.get("estacion") or id_estacion
    daily_measure = user_input.get(const.CONF_ID_ESTACION_MEDIDA_DAILY)
    last10_measure = user_input.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN)
    selected_measure = daily_measure or last10_measure
    if selected_measure:
        daily = bool(daily_measure)
        endpoint = daily_endpoint if daily else last10_endpoint
        payload = _request_json(session, endpoint.format(id_estacion))
        try:
            _station_name, measures = _station_name_and_measures(payload, daily=daily)
        except InvalidIdentifier:
            # Daily data can be temporarily empty around midnight. The station is
            # already validated by the catalog, so do not reject it.
            measures = set()
        if measures and selected_measure not in measures:
            raise InvalidMeasure
    return f"MeteoGalicia {name}"


def _validate_api_input(user_input: dict) -> str:
    """Validate config data synchronously and return a descriptive entry title."""
    from meteogalicia_api.const import (
        URL_FORECAST,
        URL_OBSERVATION_DAILYDATA_BY_STATION,
        URL_OBSERVATION_LAST10MINDATA_BY_STATION,
    )

    with requests.Session() as session:
        if id_concello := user_input.get(const.CONF_ID_CONCELLO):
            return _validate_forecast(session, URL_FORECAST, id_concello)
        return _validate_station(
            session,
            user_input,
            URL_OBSERVATION_DAILYDATA_BY_STATION,
            URL_OBSERVATION_LAST10MINDATA_BY_STATION,
        )


async def _async_validate_api_input(hass, user_input: dict) -> str:
    """Validate config data without blocking Home Assistant's event loop."""
    try:
        return await hass.async_add_executor_job(_validate_api_input, user_input)
    except requests.Timeout as err:
        raise RequestTimeout from err
    except requests.RequestException as err:
        raise CannotConnect from err


async def _validated_title(hass, user_input: dict, errors: dict) -> str | None:
    """Run API validation and map failures to config-flow error keys."""
    try:
        return await _async_validate_api_input(hass, user_input)
    except InvalidIdentifier:
        errors["base"] = "unknown_id"
    except InvalidMeasure:
        errors["base"] = "invalid_measure"
    except RequestTimeout:
        errors["base"] = "timeout"
    except CannotConnect:
        errors["base"] = "cannot_connect"
    return None


def _clean_data(data: dict) -> dict:
    return {key: value for key, value in data.items() if value not in ("", None)}


def _unique_id_from_data(data: dict) -> str | None:
    """Return the config-entry unique ID represented by configuration data."""
    if id_concello := data.get(const.CONF_ID_CONCELLO):
        return f"concello_{id_concello}"

    if not (id_estacion := data.get(const.CONF_ID_ESTACION)):
        return None

    id_daily = data.get(const.CONF_ID_ESTACION_MEDIDA_DAILY, "")
    id_last10 = data.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN, "")
    unique_id = f"estacion_{id_estacion}"
    if id_daily or id_last10:
        unique_id = f"{unique_id}_{id_daily}_{id_last10}"
    return unique_id


def _validate_station_measures(user_input: dict, errors: dict) -> None:
    id_daily = user_input.get(const.CONF_ID_ESTACION_MEDIDA_DAILY, "")
    id_last10 = user_input.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN, "")
    if id_daily and id_last10:
        errors[const.CONF_ID_ESTACION_MEDIDA_DAILY] = "only_one_measure"
        errors[const.CONF_ID_ESTACION_MEDIDA_LAST10MIN] = "only_one_measure"



def _select_selector(options: list[SelectOptionDict]) -> SelectSelector:
    """Build a dropdown selector with explicit labels."""
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


def _plain_options(values) -> list[SelectOptionDict]:
    """Return labeled selector options where value and label are identical."""
    return [SelectOptionDict(value=value, label=value) for value in values]


def _get_concellos_from_api(province: str) -> list[dict]:
    """Return the static concello catalog exposed by MeteoGalicia-API."""
    from meteogalicia_api.interface import MeteoGalicia

    return MeteoGalicia(timeout=const.CONFIG_FLOW_TIMEOUT).get_concellos(province)


def _get_stations_from_api(
    province: str, concello: str | None = None
) -> list[dict]:
    """Return the station catalog exposed by MeteoGalicia-API."""
    from meteogalicia_api.interface import MeteoGalicia

    stations = MeteoGalicia(timeout=const.CONFIG_FLOW_TIMEOUT).get_stations(
        province=province, concello=concello
    )
    if stations is None:
        raise CannotConnect
    return stations


async def _async_get_concellos(hass, province: str) -> list[dict]:
    """Load concellos without blocking Home Assistant."""
    return await hass.async_add_executor_job(_get_concellos_from_api, province)


async def _async_get_stations(
    hass, province: str, concello: str | None = None
) -> list[dict]:
    """Load stations without blocking Home Assistant."""
    return await hass.async_add_executor_job(
        _get_stations_from_api, province, concello
    )


class MeteoGaliciaConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle a config flow for MeteoGalicia."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._source = user_input["source"]
            if self._source == "forecast":
                return await self.async_step_forecast_method()
            return await self.async_step_station_method()

        schema = vol.Schema({vol.Required("source"): vol.In(["forecast", "station"])})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_forecast_method(self, user_input=None):
        """Choose how to configure a municipal forecast."""
        if user_input is not None:
            if user_input[CONF_CONFIGURATION_METHOD] == CONFIGURATION_METHOD_MANUAL:
                return await self.async_step_forecast()
            return await self.async_step_forecast_province()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONFIGURATION_METHOD,
                    default=CONFIGURATION_METHOD_LIST,
                ): _select_selector(
                    [
                        SelectOptionDict(
                            value=CONFIGURATION_METHOD_LIST,
                            label="Lista",
                        ),
                        SelectOptionDict(
                            value=CONFIGURATION_METHOD_MANUAL,
                            label="ID manual",
                        ),
                    ]
                )
            }
        )
        return self.async_show_form(
            step_id="forecast_method",
            data_schema=schema,
        )

    async def async_step_forecast_province(self, user_input=None):
        """Select the province for a municipal forecast."""
        if user_input is not None:
            self._selected_province = user_input[CONF_PROVINCE]
            return await self.async_step_forecast_concello()

        schema = vol.Schema(
            {
                vol.Required(CONF_PROVINCE): _select_selector(
                    _plain_options(PROVINCES)
                )
            }
        )
        return self.async_show_form(
            step_id="forecast_province",
            data_schema=schema,
        )

    async def async_step_forecast_concello(self, user_input=None):
        """Select a concello and save its municipal identifier."""
        errors = {}
        province = self._selected_province
        concellos = await _async_get_concellos(self.hass, province)

        if user_input is not None:
            id_concello = user_input[const.CONF_ID_CONCELLO]
            return await self.async_step_forecast(
                {const.CONF_ID_CONCELLO: id_concello}
            )

        options = [
            SelectOptionDict(
                value=str(item["idConcello"]),
                label=f'{item["concello"]} ({item["idConcello"]})',
            )
            for item in concellos
        ]
        if not options:
            errors["base"] = "no_concellos"

        schema = vol.Schema(
            {
                vol.Required(const.CONF_ID_CONCELLO): _select_selector(options)
            }
        )
        return self.async_show_form(
            step_id="forecast_concello",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_forecast(self, user_input=None):
        """Configure a municipal forecast by explicit concello ID."""
        errors = {}
        if user_input is not None:
            id_concello = user_input.get(const.CONF_ID_CONCELLO, "")
            if len(id_concello) != 5 or not id_concello.isnumeric():
                errors[const.CONF_ID_CONCELLO] = "invalid_id"
            else:
                unique_id = f"concello_{id_concello}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = await _validated_title(self.hass, user_input, errors)
                if title:
                    return self.async_create_entry(
                        title=title,
                        data=_clean_data(user_input),
                    )

        schema = vol.Schema({vol.Required(const.CONF_ID_CONCELLO): str})
        return self.async_show_form(
            step_id="forecast",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_station_method(self, user_input=None):
        """Choose how to configure a weather station."""
        if user_input is not None:
            if user_input[CONF_CONFIGURATION_METHOD] == CONFIGURATION_METHOD_MANUAL:
                return await self.async_step_station()
            return await self.async_step_station_province()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONFIGURATION_METHOD,
                    default=CONFIGURATION_METHOD_LIST,
                ): _select_selector(
                    [
                        SelectOptionDict(
                            value=CONFIGURATION_METHOD_LIST,
                            label="Lista",
                        ),
                        SelectOptionDict(
                            value=CONFIGURATION_METHOD_MANUAL,
                            label="ID manual",
                        ),
                    ]
                )
            }
        )
        return self.async_show_form(
            step_id="station_method",
            data_schema=schema,
        )

    async def async_step_station_province(self, user_input=None):
        """Select the province used to filter weather stations."""
        if user_input is not None:
            self._selected_province = user_input[CONF_PROVINCE]
            return await self.async_step_station_concello()

        schema = vol.Schema(
            {
                vol.Required(CONF_PROVINCE): _select_selector(
                    _plain_options(PROVINCES)
                )
            }
        )
        return self.async_show_form(
            step_id="station_province",
            data_schema=schema,
        )

    async def async_step_station_concello(self, user_input=None):
        """Select a concello that currently has weather stations."""
        errors = {}
        province = self._selected_province
        try:
            stations = await _async_get_stations(self.hass, province)
        except CannotConnect:
            stations = []
            errors["base"] = "cannot_connect"

        concellos = sorted(
            {
                str(station["concello"])
                for station in stations
                if isinstance(station, dict) and station.get("concello")
            }
        )

        if user_input is not None and not errors:
            self._selected_station_concello = user_input[CONF_CONCELLO_SELECTION]
            return await self.async_step_station_select()

        if not concellos and not errors:
            errors["base"] = "no_stations"

        schema = vol.Schema(
            {
                vol.Required(CONF_CONCELLO_SELECTION): _select_selector(
                    _plain_options(concellos)
                )
            }
        )
        return self.async_show_form(
            step_id="station_concello",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_station_select(self, user_input=None):
        """Select a weather station and save its station identifier."""
        errors = {}
        province = self._selected_province
        concello = self._selected_station_concello
        try:
            stations = await _async_get_stations(self.hass, province, concello)
        except CannotConnect:
            stations = []
            errors["base"] = "cannot_connect"

        options = [
            SelectOptionDict(
                value=str(station["idEstacion"]),
                label=f'{station.get("estacion") or station["idEstacion"]} '
                f'({station["idEstacion"]})',
            )
            for station in stations
            if isinstance(station, dict) and station.get("idEstacion") is not None
        ]

        if user_input is not None and not errors:
            return await self.async_step_station(dict(user_input))

        if not options and not errors:
            errors["base"] = "no_stations"

        schema = vol.Schema(
            {
                vol.Required(const.CONF_ID_ESTACION): _select_selector(options),
                vol.Optional(const.CONF_ID_ESTACION_MEDIDA_DAILY): str,
                vol.Optional(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN): str,
            }
        )
        return self.async_show_form(
            step_id="station_select",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_station(self, user_input=None):
        """Configure observations by explicit station ID."""
        errors = {}
        if user_input is not None:
            id_estacion = user_input.get(const.CONF_ID_ESTACION, "")
            if len(id_estacion) != 5 or not id_estacion.isnumeric():
                errors[const.CONF_ID_ESTACION] = "invalid_id"
            _validate_station_measures(user_input, errors)
            if not errors:
                id_daily = user_input.get(const.CONF_ID_ESTACION_MEDIDA_DAILY, "")
                id_last10 = user_input.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN, "")
                unique_id = f"estacion_{id_estacion}"
                if id_daily or id_last10:
                    unique_id = f"{unique_id}_{id_daily}_{id_last10}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = await _validated_title(self.hass, user_input, errors)
                if title:
                    return self.async_create_entry(
                        title=title,
                        data=_clean_data(user_input),
                    )

        schema = vol.Schema(
            {
                vol.Required(const.CONF_ID_ESTACION): str,
                vol.Optional(const.CONF_ID_ESTACION_MEDIDA_DAILY): str,
                vol.Optional(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN): str,
            }
        )
        return self.async_show_form(
            step_id="station",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_import(self, import_data):
        """Import one legacy sensor platform block from YAML."""
        data = _clean_data(dict(import_data))
        unique_id = _unique_id_from_data(data)
        if unique_id is None:
            return self.async_abort(reason="invalid_import")

        id_concello = data.get(const.CONF_ID_CONCELLO)
        if id_concello and (len(id_concello) != 5 or not id_concello.isnumeric()):
            return self.async_abort(reason="invalid_import")
        if not id_concello:
            id_estacion = data[const.CONF_ID_ESTACION]
            errors = {}
            if len(id_estacion) != 5 or not id_estacion.isnumeric():
                return self.async_abort(reason="invalid_import")
            _validate_station_measures(data, errors)
            if errors:
                return self.async_abort(reason="invalid_import")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        identifier = id_concello or data[const.CONF_ID_ESTACION]
        return self.async_create_entry(
            title=f"MeteoGalicia {identifier}",
            data=data,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return MeteoGaliciaOptionsFlowHandler(config_entry)


class MeteoGaliciaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for MeteoGalicia."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        data = merge_entry_data(self._config_entry)
        is_forecast = const.CONF_ID_CONCELLO in data
        interval_keys = (
            (const.CONF_OBSERVATION_INTERVAL, const.CONF_FORECAST_INTERVAL)
            if is_forecast
            else (const.CONF_OBSERVATION_INTERVAL, const.CONF_STATION_DAILY_INTERVAL)
        )

        if user_input is not None:
            user_input = dict(user_input)
            for key in interval_keys:
                try:
                    # The frontend omits an optional field when it is cleared.
                    user_input[key] = _validate_interval(user_input.get(key))
                except vol.Invalid:
                    errors[key] = "invalid_interval"
            if is_forecast:
                id_concello = user_input.get(const.CONF_ID_CONCELLO, "")
                if len(id_concello) != 5 or not id_concello.isnumeric():
                    errors[const.CONF_ID_CONCELLO] = "invalid_id"
            else:
                id_estacion = user_input.get(const.CONF_ID_ESTACION, "")
                if len(id_estacion) != 5 or not id_estacion.isnumeric():
                    errors[const.CONF_ID_ESTACION] = "invalid_id"
                _validate_station_measures(user_input, errors)

            if not errors:
                return self.async_create_entry(
                    title="", data={**self._config_entry.options, **user_input}
                )

        interval_fields = {
            vol.Optional(
                key, description={"suggested_value": get_scan_interval(data, key)}
            ): _INTERVAL_VALIDATOR
            for key in interval_keys
        }

        if is_forecast:
            schema = vol.Schema(
                {
                    vol.Required(
                        const.CONF_ID_CONCELLO,
                        default=data.get(const.CONF_ID_CONCELLO, ""),
                    ): str,
                    vol.Optional(
                        const.CONF_WARNINGS_ENABLED,
                        default=data.get(const.CONF_WARNINGS_ENABLED, False),
                    ): cv.boolean,
                    **interval_fields,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(
                        const.CONF_ID_ESTACION,
                        default=data.get(const.CONF_ID_ESTACION, ""),
                    ): str,
                    vol.Optional(
                        const.CONF_ID_ESTACION_MEDIDA_DAILY,
                        default=data.get(const.CONF_ID_ESTACION_MEDIDA_DAILY, ""),
                    ): str,
                    vol.Optional(
                        const.CONF_ID_ESTACION_MEDIDA_LAST10MIN,
                        default=data.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN, ""),
                    ): str,
                    **interval_fields,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
