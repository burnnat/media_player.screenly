"""Support for Screenly OSE digital signage."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_PLAYER_SCHEMA, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    DOMAIN, MEDIA_TYPE_IMAGE, MEDIA_TYPE_URL, MEDIA_TYPE_VIDEO,
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL, CONF_TIMEOUT,
    STATE_OFF, STATE_ON)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DATA_SCREENLY = 'screenly'
DEFAULT_NAME = 'Screenly'
CONF_ASSETS = 'assets'

SUPPORT_SCREENLY = (
    SUPPORT_PLAY_MEDIA | SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=80): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=5): cv.positive_int,
    vol.Optional(CONF_ASSETS): {
        cv.string: cv.string
    }
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Screenly media player platform."""
    if DATA_SCREENLY not in hass.data:
        hass.data[DATA_SCREENLY] = []

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    ssl = config.get(CONF_SSL)
    timeout = config.get(CONF_TIMEOUT)
    assets = config.get(CONF_ASSETS)

    screenly = ScreenlyDevice(async_get_clientsession(
        hass, verify_ssl=False), name, host, port, ssl, timeout, assets)

    hass.data[DATA_SCREENLY].append(screenly)
    async_add_entities([screenly], update_before_add=True)


class ScreenlyDevice(MediaPlayerDevice):
    """Representation of Screenly digital signage device."""

    def __init__(
            self, websession, name, host, port, encryption, timeout, assets):
        """Initialize entity to control Screenly device."""
        import aiohttp
        import screenly_ose as screenly

        self._name = name
        self._assets = assets
        self._state = None

        client_timeout = aiohttp.ClientTimeout(total=timeout)
        self._screenly = screenly.Screenly(
            websession, host, port=port, timeout=timeout)

    async def async_update(self):
        """Update state of device."""
        asset = await self._screenly.get_current_asset()

        if asset:
            self._state = STATE_ON
            self._asset = asset
        else:
            self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def media_content_id(self):
        """ID of current asset."""
        return self._asset['id']

    @property
    def media_content_type(self):
        """Content type of current asset."""
        from screenly_ose.const import (TYPE_IMAGE, TYPE_WEBPAGE)

        type = self._asset['type']

        if type == TYPE_WEBPAGE:
            return MEDIA_TYPE_URL
        elif type == TYPE_IMAGE:
            return MEDIA_TYPE_IMAGE
        else:
            return None

    @property
    def media_title(self):
        """Title of current asset."""
        return self._asset['name']

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_SCREENLY

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Switch asset to given ID."""
        if media_type in [MEDIA_TYPE_IMAGE, MEDIA_TYPE_VIDEO, MEDIA_TYPE_URL]:
            if media_id in self._assets:
                asset_id = self._assets[media_id]
                _LOGGER.debug("Found matching id '%s' for alias '%s'",
                    asset_id, media_id)
            else:
                asset_id = media_id

            response = await self._screenly.switch_asset(asset_id)
            return bool(response)
        else:
            _LOGGER.error(
                "Invalid media type %s. Only %s and %s are supported",
                media_type, MEDIA_TYPE_IMAGE, MEDIA_TYPE_VIDEO,
                MEDIA_TYPE_URL)

    async def async_media_next_track(self):
        """Skip to next."""
        response = await self._screenly.next_asset()
        return bool(response)

    async def async_media_previous_track(self):
        """Skip to previous."""
        response = await self._screenly.previous_asset()
        return bool(response)
