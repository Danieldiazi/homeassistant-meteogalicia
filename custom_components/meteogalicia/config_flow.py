"""Config flow for MeteoGalicia integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_SCAN_INTERVAL

from . import const


def _clean_data(data: dict) -> dict:
    return {key: value for key, value in data.items() if value not in ("", None)}

def _validate_station_measures(user_input: dict, errors: dict) -> None:
    id_daily = user_input.get(const.CONF_ID_ESTACION_MEDIDA_DAILY, "")
    id_last10 = user_input.get(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN, "")
    if id_daily and id_last10:
        errors[const.CONF_ID_ESTACION_MEDIDA_DAILY] = "only_one_measure"
        errors[const.CONF_ID_ESTACION_MEDIDA_LAST10MIN] = "only_one_measure"

def _merge_entry_data(entry: config_entries.ConfigEntry) -> dict:
    """Merge entry data and options, allowing options to clear values."""
    data = dict(entry.data)
    for key, value in entry.options.items():
        if value in ("", None):
            data.pop(key, None)
        else:
            data[key] = value
    return data


class MeteoGaliciaConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle a config flow for MeteoGalicia."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._source = user_input["source"]
            if self._source == "forecast":
                return await self.async_step_forecast()
            return await self.async_step_station()

        schema = vol.Schema({vol.Required("source"): vol.In(["forecast", "station"])})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_forecast(self, user_input=None):
        errors = {}
        if user_input is not None:
            id_concello = user_input.get(const.CONF_ID_CONCELLO, "")
            if len(id_concello) != 5 or not id_concello.isnumeric():
                errors[const.CONF_ID_CONCELLO] = "invalid_id"
            else:
                unique_id = f"concello_{id_concello}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="MeteoGalicia",
                    data=_clean_data(user_input),
                )

        schema = vol.Schema({vol.Required(const.CONF_ID_CONCELLO): str})
        return self.async_show_form(
            step_id="forecast",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_station(self, user_input=None):
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
                return self.async_create_entry(
                    title="MeteoGalicia",
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
        data = _merge_entry_data(self._config_entry)
        is_forecast = const.CONF_ID_CONCELLO in data

        if user_input is not None:
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
                return self.async_create_entry(title="", data=user_input)

        scan_interval_schema = vol.Optional(
            CONF_SCAN_INTERVAL,
            default=data.get(CONF_SCAN_INTERVAL, ""),
        )
        scan_interval_validator = vol.Any(
            "",
            vol.All(vol.Coerce(int), vol.Range(min=1)),
        )

        if is_forecast:
            schema = vol.Schema(
                {
                    vol.Required(
                        const.CONF_ID_CONCELLO,
                        default=data.get(const.CONF_ID_CONCELLO, ""),
                    ): str,
                    scan_interval_schema: scan_interval_validator,
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
                    scan_interval_schema: scan_interval_validator,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
