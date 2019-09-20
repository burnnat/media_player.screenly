"""The Screenly component."""
__version__ = '0.0.2'

from homeassistant.helpers.discovery import async_load_platform

DOMAIN = 'screenly'

async def async_setup(hass, config):
    hass.async_create_task(
        async_load_platform(hass, 'switch', DOMAIN, {}, config))

    return True