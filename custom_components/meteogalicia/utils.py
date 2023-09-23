from . import const

def check_connection(self_connected, connected, self_state, self_id, self_exception, logger):
    state = self_state
    # Handle connection messages here.
    if self_connected:
        if not connected:
            state = None
            logger.warning(
                const.STRING_NOT_UPDATE_SENSOR,
                self_id,
                self_exception,
            )

    else:
        if connected:
            logger.info(const.STRING_UPDATE_SENSOR_COMPLETED, self_id)
        else:
            state = None
            logger.warning(
                const.STRING_NOT_UPDATE_AVAILABLE, self_id, self_exception
            )
    return state