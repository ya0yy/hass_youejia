"""youejia 集成。"""

from __future__ import annotations

from .coordinator import YouEJiaCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_TOKEN
from homeassistant.core import HomeAssistant

from homeassistant.components.youejia.api import YoueJiaApiClient

_PLATFORMS: list[Platform] = [Platform.CLIMATE]

type YouEJiaConfigEntry = ConfigEntry[YouEJiaCoordinator]  # noqa: F821


async def async_setup_entry(hass: HomeAssistant, entry: YouEJiaConfigEntry) -> bool:
    """从 config entry 设置 youejia。"""

    api_data = entry.data.get('api_data')
    api_client = YoueJiaApiClient(api_data[CONF_TOKEN], api_data['user_id'])
    cd = YouEJiaCoordinator(hass, api_client, entry)
    await cd.async_config_entry_first_refresh()

    entry.runtime_data = cd
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: YouEJiaConfigEntry) -> bool:
    """卸载 config entry。"""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
