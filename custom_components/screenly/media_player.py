"""Support for Screenly OSE digital signage."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    DOMAIN, MEDIA_TYPE_IMAGE, MEDIA_TYPE_URL, MEDIA_TYPE_VIDEO,
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL, CONF_TIMEOUT,
    STATE_OFF, STATE_ON)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DATA_SCREENLY

_LOGGER = logging.getLogger(__name__)

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

SERVICE_ENABLE_ASSET = 'screenly_enable_asset'
SERVICE_DISABLE_ASSET = 'screenly_disable_asset'

ATTR_ASSET_ID = 'asset_id'

ASSET_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.comp_entity_ids,
    vol.Required(ATTR_ASSET_ID): cv.string
})

SERVICE_TO_METHOD = {
    SERVICE_ENABLE_ASSET: {
        'method': 'async_enable_asset',
        'schema': ASSET_SCHEMA},
    SERVICE_DISABLE_ASSET: {
        'method': 'async_disable_asset',
        'schema': ASSET_SCHEMA},
}

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

    _LOGGER.debug("Adding Screenly device entity: %s", name)

    hass.data[DATA_SCREENLY].append(screenly)
    async_add_entities([screenly], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on ScreenlyDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        if not method:
            return

        params = {
            key: value for key, value in service.data.items()
            if key != 'entity_id'}

        entity_ids = service.data.get('entity_id')
        target_devices = [
            player for player in hass.data[DATA_SCREENLY]
            if player.entity_id in entity_ids]

        for device in target_devices:
            await getattr(device, method['method'])(**params)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]['schema']
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema)

class ScreenlyDevice(MediaPlayerDevice):
    """Representation of Screenly digital signage device."""

    def __init__(
            self, websession, name, host, port, encryption, timeout, assets):
        """Initialize entity to control Screenly device."""
        import aiohttp
        import screenly_ose as screenly

        self._name = name
        self._asset_alias_to_id = assets
        self._state = None

        self._asset_entities = {}

        client_timeout = aiohttp.ClientTimeout(total=timeout)
        self._screenly = screenly.Screenly(
            websession, host, port=port, timeout=timeout)

    def asset_aliases(self):
        return self._asset_alias_to_id

    def add_child(self, asset_entity):
        asset_id = asset_entity.unique_id
        _LOGGER.debug("Registering asset entity '%s' for device %s with id: %s", asset_entity.alias, self._name, asset_id)
        self._asset_entities[asset_id] = asset_entity

    async def async_update(self):
        """Update state of device."""
        assets = await self._screenly.list_assets()
        active = None

        if assets:
            for asset in assets:
                if asset['active']:
                    active = asset
                
                asset_id = asset['id']

                if asset_id in self._asset_entities:
                    self._asset_entities[asset_id].update_from_raw(asset)

        if active:
            self._state = STATE_ON
            self._asset = active
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

    def lookup_asset(self, asset_alias):
        """Converts an asset alias from component configuration to a true Screenly ID."""
        if asset_alias in self._asset_alias_to_id:
            asset_id = self._asset_alias_to_id[asset_alias]
            _LOGGER.debug("Found matching id '%s' for alias '%s'",
                asset_id, asset_alias)
            return asset_id
        else:
            return asset_alias

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Switch asset to given ID."""
        if media_type in [MEDIA_TYPE_IMAGE, MEDIA_TYPE_VIDEO, MEDIA_TYPE_URL]:
            _LOGGER.debug("Displaying asset: %s", media_id)
            response = await self._screenly.switch_asset(self.lookup_asset(media_id))
            return bool(response)
        else:
            _LOGGER.error(
                "Invalid media type %s. Only %s and %s are supported",
                media_type, MEDIA_TYPE_IMAGE, MEDIA_TYPE_VIDEO,
                MEDIA_TYPE_URL)

    async def async_media_next_track(self):
        """Skip to next."""
        _LOGGER.debug("Switching to next asset")
        response = await self._screenly.next_asset()
        return bool(response)

    async def async_media_previous_track(self):
        """Skip to previous."""
        _LOGGER.debug("Switching to previous asset")
        response = await self._screenly.previous_asset()
        return bool(response)

    async def async_enable_asset(self, asset_id):
        """Enable asset with the given ID."""
        _LOGGER.debug("Enabling asset: %s", asset_id)
        asset_id = self.lookup_asset(asset_id)
        response = await self._screenly.enable_asset(asset_id)

        if asset_id in self._asset_entities:
            await self.async_update_ha_state(force_refresh=True)

        return bool(response)

    async def async_disable_asset(self, asset_id):
        """Disable asset with the given ID."""
        _LOGGER.debug("Disabling asset: %s", asset_id)
        asset_id = self.lookup_asset(asset_id)
        response = await self._screenly.disable_asset(asset_id)

        if asset_id in self._asset_entities:
            await self.async_update_ha_state(force_refresh=True)

        return bool(response)