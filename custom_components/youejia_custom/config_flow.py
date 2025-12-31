"""youejia 集成的配置流程。"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.exceptions import HomeAssistantError
from . import YoueJiaApiClient
from . import const

from .const import DOMAIN
from ...const import CONF_TOKEN

_LOGGER = logging.getLogger(__name__)
_CONF_USER_ID = 'user_id'


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("token"): str,
        vol.Required("user_id"): str,
    }
)


class PlaceholderHub:
    """占位类，用于让测试通过。

    TODO 移除此占位类并使用你的 PyPI 包中的实现。
    """

    def __init__(self, host: str) -> None:
        """初始化。"""
        self.host = host

    async def authenticate(self, username: str, password: str) -> list[dict[str, Any]]:
        """测试是否能通过主机验证。"""
        return [{
            "sn": "746011256372",
            "nickname": "智能温控器",
            "offline": False,
            "type": 29,
            "subtype": 0,
            "next_time": -1,
            "k_close": True,
            "h_s": 0,
            "version": 3,
            "mode": 1,
            "is_key_lock": False,
            "hw_temp_set": 20,
            "xj_temp_set": 15,
            "temp_status": 15,
            "xj_hours": 0,
            "sw": "19.0",
            "temp": "19.0",
            "temp_max": 23,
            "temp_min": 14,
            "temp_avg": 18,
            "temp_floor": "14.0",
            "code": 0,
            "bg_cfg": [
                0,
                50,
                1,
                50,
                0,
                20,
                1
            ],
            "STemp": 15,
            "is_heat": False,
            "E_on": False,
            "t_f_show": True,
            "sys_lock": 1,
            "cool_heat": 0,
            "rssi": -57,
            "fan_speed": 0,
            "is_fan_work": False,
            "mcu_type": 181,
            "key_P": 0,
            "key_V": 0,
            "devtype": 2,
            "protectstatus": 0,
            "mcu_version": 12,
            "mcu_version2": 18,
            "fg_open": False,
            "E_stats": 0,
            "E_price": "0.00",
            "E_price_save": "0.00",
            "E_price_cur": 0,
            "tempOUT": 0,
            "tempJN": 3,
            "tempSS": 0,
            "fgp_status": 0,
            "crc_error": 0,
            "hum_time_remain_hour": 0,
            "hum_time_remain_mins": 0,
            "is_fg_valid": False,
            "E_FGP": [
                "0.00",
                "0.00",
                "0.00"
            ]
        }]


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, Any]:
    _api_client = YoueJiaApiClient(user_input[CONF_TOKEN], user_input[_CONF_USER_ID])
    user_info = await _api_client.async_get_user_info()
    await _api_client.async_close()
    return user_info

class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """处理 youejia 的配置流程。"""

    VERSION = 1

    def __init__(self):
        self.device_list: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """处理初始步骤。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._api_data = user_input
                user_info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("发生未预期异常")
                errors["base"] = "unknown"
            else:
                if user_info['devices']:
                    for dev in user_info['devices']:
                        if dev['type'] == 29:
                            _LOGGER.info("找到YoueJia设备, name: %s, sn: %s", dev['nickname'], dev[const.DATA_KEY_NAME])
                            self.device_list.append(dev)
                return await self.async_step_devices()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_devices(self, user_input: dict[str, Any] | None = None):
        """第二步：让用户从列表中勾选设备."""

        if user_input is not None:
            # user_input["selected_devices"] 将是一个包含选中 ID 的列表
            # e.g., ['dev1', 'dev3']

            # 将选中的设备 ID 合并到最终的配置数据中
            final_data = {
                "api_data": self._api_data,
            }

            final_options = {
                "include_devices": [dev for dev in self.device_list if dev[const.DATA_KEY_SN] in user_input["selected_devices"]] # 选中的设备列表
            }

            # 4. 创建配置条目 (完成！)
            return self.async_create_entry(
                title=f"YouEJia ({len(user_input['selected_devices'])} devices)",
                data=final_data, options=final_options
            )

        # 构建下拉多选框的选项列表
        # options 格式: [{"value": "id1", "label": "Name1"}, ...]
        select_options = [
            selector.SelectOptionDict(value=device[const.DATA_KEY_SN], label=device[const.DATA_KEY_NAME]) for device in self.device_list
        ]

        # 定义 Schema：多选下拉框
        schema = vol.Schema({
            vol.Required("selected_devices", description="请选择设备",
                         default=list(device[const.DATA_KEY_SN] for device in self.device_list))
            : selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=select_options,
                    multiple=True,  # 允许由多选
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        })

        return self.async_show_form(
            step_id="devices",
            data_schema=schema,
            description_placeholders={"count": str(len(self.device_list))} # 可以在 strings.json 里用 {count}
        )


class CannotConnect(HomeAssistantError):
    """无法连接时抛出的错误。"""


class InvalidAuth(HomeAssistantError):
    """认证无效时抛出的错误。"""
