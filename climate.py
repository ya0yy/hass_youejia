import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.components.youejia import YouEJiaConfigEntry, YouEJiaCoordinator, YoueJiaApiClient
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import const

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config: YouEJiaConfigEntry,
        add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    devices: list[dict[str, Any]] = config.options.get('include_devices')
    add_entities([ElectricHeater(config.runtime_data, dev[const.DATA_KEY_NAME], dev[const.DATA_KEY_SN],
                                 dev[const.DATA_KEY_PASSWD]) for dev in devices if dev])


class ElectricHeater(CoordinatorEntity, ClimateEntity):
    """电取暖器实现"""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 10.0
    _attr_max_temp = 28.0
    _attr_target_temperature_step = 1.0

    def __init__(self, coordinator: YouEJiaCoordinator, name, sn, password=''):
        super().__init__(coordinator)

        self._attr_name = name
        self._attr_unique_id = f"{sn}_youejia_thermostat"
        self._sn = sn
        self._password = password

        self._target_temp = 20.0  # 默认目标温度

    @property
    def sn(self):
        return self._sn

    @property
    def password(self):
        return self._password

    @property
    def hvac_mode(self) -> HVACMode:
        device_data = self.coordinator.data.get(self.sn)
        k_close = device_data.get('k_close')

        return HVACMode.HEAT if not bool(k_close) else HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        device_data = self.coordinator.data.get(self.sn)
        temp_str = device_data.get('temp')
        return float(temp_str)

    @property
    def target_temperature(self) -> float | None:
        device_data = self.coordinator.data.get(self.sn)
        temp_str = device_data.get('temp_status')
        return float(temp_str)

    @property
    def api(self) -> YoueJiaApiClient:
        return self.coordinator.api

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            # 调用设备API打开取暖器
            _is_on = True
        else:
            # 调用设备API关闭取暖器
            _is_on = False

        if self.sn in self.coordinator.data:
            self.coordinator.data[self.sn]['k_close'] = not _is_on

        self.async_write_ha_state()

        self.coordinator.data[self.sn] = await self.api.async_set_power(self.sn, self._password, power_on=_is_on)

    async def async_set_temperature(self, **kwargs) -> None:
        if temperature := kwargs.get(ATTR_TEMPERATURE):
            self._target_temp = temperature
            # 调用设备API设置目标温度
        self.coordinator.data[self.sn] = await self.api.async_set_temperature(self.sn, self._password, temperature=temperature)
        await self.coordinator.async_request_refresh()
