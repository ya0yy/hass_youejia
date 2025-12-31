import logging
from typing import Any

from homeassistant.components.climate import (
    PRESET_BOOST,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from . import YouEJiaConfigEntry, YouEJiaCoordinator, YoueJiaApiClient
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

    _NORMAL_PRESET = "正常"
    _FORCE_PRESET = PRESET_BOOST  # 使用标准预设常量表示强制加热
    _FORCE_TEMPERATURE = 30.0  # 强制加热时的目标温度
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.PRESET_MODE
    )
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
        self._last_temp: float | None = None  # 记录进入强制模式前的温度

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
    def preset_modes(self) -> list[str]:
        """返回支持的预设模式。"""
        return [self._NORMAL_PRESET, self._FORCE_PRESET]

    @property
    def preset_mode(self) -> str:
        """判断当前是否处于强制加热模式。"""
        if self.target_temperature == self._FORCE_TEMPERATURE:
            return self._FORCE_PRESET
        return self._NORMAL_PRESET

    @property
    def api(self) -> YoueJiaApiClient:
        return self.coordinator.api

    @property
    def hvac_action(self) -> HVACAction:
        """返回当前的动作 (UI 靠这个来决定图标准不准亮)."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        device_data = self.coordinator.data.get(self.sn)
        is_heat = device_data.get('is_heat')

        if is_heat:
            return HVACAction.HEATING
        else:
            return HVACAction.IDLE # 达温停机

        # 兜底
        return HVACAction.IDLE

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

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """处理预设模式切换。"""
        if preset_mode == self._FORCE_PRESET:
            # 记忆切换前的温度，便于恢复
            current = self.target_temperature
            if current is not None:
                self._last_temp = current
            await self.async_set_temperature(temperature=self._FORCE_TEMPERATURE)
            return

        # 恢复为普通模式，优先恢复记忆温度，否则设为 22℃
        restore_temp = self._last_temp if self._last_temp is not None else 22.0
        self._last_temp = None
        await self.async_set_temperature(temperature=restore_temp)
