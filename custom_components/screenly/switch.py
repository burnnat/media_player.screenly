"""Support for Screenly OSE asset enablement switches."""
import logging

from homeassistant.components.switch import SwitchDevice

from .const import DATA_SCREENLY

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Screenly asset switches."""
    if DATA_SCREENLY not in hass.data:
        _LOGGER.debug("Screenly media player not loaded yet; delaying load")
        return False;

    _LOGGER.debug("Loading Screenly assets from devices")
    entities = []

    for screenly in hass.data[DATA_SCREENLY]:
        _LOGGER.debug("Adding asset entities for Screenly device: %s", screenly.name)

        for asset_alias, asset_id in screenly.asset_aliases().items():
            asset_entity = ScreenlyAsset(screenly, asset_alias, asset_id)
            entities.append(asset_entity)
            screenly.add_child(asset_entity)

    async_add_entities(entities, update_before_add=True)


class ScreenlyAsset(SwitchDevice):

    def __init__(self, screenly_device, asset_alias, asset_id):
        self._parent = screenly_device
        self._alias = asset_alias
        self._id = asset_id
        self._name = asset_alias
        self._enabled = False
        self._updated = False

    def update_from_raw(self, asset):
        _LOGGER.debug("Updating asset state: %s", self._alias)
        self._name = asset['name']
        self._enabled = asset['enabled']
        self._updated = True
        self.async_schedule_update_ha_state()

    @property
    def alias(self):
        return self._alias

    @property
    def should_poll(self):
        return False

    @property
    def assumed_state(self):
        return not self._updated

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._id

    @property
    def icon(self):
        return "mdi:image"

    @property
    def is_on(self):
        return self._enabled

    async def async_turn_on(self, **kwargs):
        """Enable the asset."""
        return await self._parent.async_enable_asset(self._id)

    async def async_turn_off(self, **kwargs):
        """Disable the asset."""
        return await self._parent.async_disable_asset(self._id)