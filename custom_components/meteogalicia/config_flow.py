"""Config flow for MeteoGalicia integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from . import const


def _validate_ids(data):
    errors = {}
    id_concello = data.get(const.CONF_ID_CONCELLO, "")
    id_estacion = data.get(const.CONF_ID_ESTACION, "")

    if id_concello and id_estacion:
        errors["base"] = "choose_one"
        return errors
    if not id_concello and not id_estacion:
        errors["base"] = "missing_id"
        return errors

    if id_concello and (len(id_concello) != 5 or not id_concello.isnumeric()):
        errors[const.CONF_ID_CONCELLO] = "invalid_id"
    if id_estacion and (len(id_estacion) != 5 or not id_estacion.isnumeric()):
        errors[const.CONF_ID_ESTACION] = "invalid_id"
    return errors


class MeteoGaliciaConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle a config flow for MeteoGalicia."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _validate_ids(user_input)
            if not errors:
                if user_input.get(const.CONF_ID_CONCELLO):
                    unique_id = f"concello_{user_input[const.CONF_ID_CONCELLO]}"
                else:
                    unique_id = f"estacion_{user_input[const.CONF_ID_ESTACION]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="MeteoGalicia",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Optional(const.CONF_ID_CONCELLO): str,
                vol.Optional(const.CONF_ID_ESTACION): str,
                vol.Optional(const.CONF_ID_ESTACION_MEDIDA_DAILY): str,
                vol.Optional(const.CONF_ID_ESTACION_MEDIDA_LAST10MIN): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
