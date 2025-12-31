from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import YoueJiaApiClient
from .const import DOMAIN, DATA_KEY_SN
from ...helpers import json

_LOGGER = logging.getLogger(__name__)

class YouEJiaCoordinator(DataUpdateCoordinator):
    """用于管理优E家数据的协调器。"""

    def __init__(self, hass: HomeAssistant, api_client: YoueJiaApiClient, ce: ConfigEntry) -> None:
        """初始化协调器。"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # 这里设置轮询间隔，比如 30 秒
            update_interval=timedelta(seconds=30),
        )
        self.api = api_client
        self.ce = ce

    async def _async_update_data(self):
        """在这里执行那个“批量查询”的 API 调用。"""
        # _LOGGER.warning("进入更新: _async_update_data", )
        try:
            data = await self.api.async_get_devices([dev.get(DATA_KEY_SN) for dev in self.ce.options.get('include_devices')])
            # _LOGGER.warning("YoueJiaCoordinator: update_data: %s", json.json_dumps(data))
            dev_list = data.get('dev')
            return {dev[DATA_KEY_SN]: dev for dev in dev_list}
        except Exception as err:
            # 如果抛出 UpdateFailed，所有关联实体都会变成“不可用”状态
            raise UpdateFailed(f"Error communicating with API: {err}")