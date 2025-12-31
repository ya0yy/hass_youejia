"""youejia 接口客户端。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from enum import IntEnum
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_UBUS_PATH = "/ubus"
_DEFAULT_ID = 1
_DEFAULT_JSONRPC = "2.0"
_DEFAULT_METHOD = "call"
_DEFAULT_FLAVOR = "UeHome"
_DEFAULT_LANG = 1
_DEFAULT_PLATFORM = 1
_DEFAULT_VERSION = 1


class YoueJiaApiError(Exception):
    """youejia 接口调用异常。"""


class YoueJiaMode(IntEnum):
    """工作模式枚举。"""

    CONSTANT = 0  # 恒温模式
    SMART = 1  # 智能模式
    VACATION = 2  # 休假模式


class YoueJiaApiClient:
    """基于 aiohttp 的 youejia API 客户端。"""

    def __init__(
            self,
            token: str,
            user_id: str,
            *,
            session: aiohttp.ClientSession | None = None,
            base_url: str = "https://cn.zncn.net.cn",
    ) -> None:
        """初始化客户端，暴露 token、user_id。"""
        self.token = token
        self.user_id = user_id
        self._session: aiohttp.ClientSession | None = session
        self._base_url = base_url.rstrip("/")
        self._session_owner = session is None
        self._request_id = _DEFAULT_ID

    async def async_close(self) -> None:
        """关闭内部创建的会话。"""
        if self._session_owner and self._session and not self._session.closed:
            await self._session.close()

    async def async_get_user_info(self) -> dict[str, Any]:
        """获取用户信息。"""
        payload = {
            "flavor": _DEFAULT_FLAVOR,
            "lang": _DEFAULT_LANG,
            "platform": _DEFAULT_PLATFORM,
            "user_id": self.user_id,
            "version": _DEFAULT_VERSION,
        }
        params: list[Any] = [self.token, "db_agent2", "user_get_info", payload]
        result = await self._async_post_ubus(params)
        return result

    async def async_get_devices(self, serial_numbers: Iterable[str]) -> dict[str, Any]:
        """批量获取设备信息。"""
        sn_list = list(serial_numbers)
        if not sn_list:
            raise YoueJiaApiError("设备序列号列表为空")

        payload = {
            "dev_sn": sn_list,
            "flavor": _DEFAULT_FLAVOR,
            "lang": _DEFAULT_LANG,
            "platform": _DEFAULT_PLATFORM,
            "version": _DEFAULT_VERSION,
        }
        params: list[Any] = [self.token, "user_mgr", "user_dev_info", payload]
        result = await self._async_post_ubus(params)
        return result

    async def async_set_power(
            self, serial_number: str, password: str, *, power_on: bool
    ) -> dict[str, Any]:
        """设置设备开关机。"""
        payload = {
            "flavor": _DEFAULT_FLAVOR,
            "k_close": not power_on,
            "lang": _DEFAULT_LANG,
            "p_w": password,
            "platform": _DEFAULT_PLATFORM,
            "version": _DEFAULT_VERSION,
        }
        params: list[Any] = [self.token, serial_number, "set", payload]
        result = await self._async_post_ubus(params)
        return result

    async def async_set_temperature(
            self, serial_number: str, password: str, *, temperature: int
    ) -> dict[str, Any]:
        """设置设备目标温度。"""
        payload = {
            "flavor": _DEFAULT_FLAVOR,
            "hw_temp_set": int(temperature),
            "lang": _DEFAULT_LANG,
            "p_w": password,
            "platform": _DEFAULT_PLATFORM,
            "version": _DEFAULT_VERSION,
        }
        params: list[Any] = [self.token, serial_number, "set", payload]
        result = await self._async_post_ubus(params)
        return result

    async def async_set_mode(
            self, serial_number: str, password: str, *, mode: YoueJiaMode
    ) -> dict[str, Any]:
        """设置设备工作模式。"""
        try:
            enum_mode = YoueJiaMode(mode)
        except ValueError as err:
            raise YoueJiaApiError(f"mode 超出范围: {mode}") from err

        payload = {
            "flavor": _DEFAULT_FLAVOR,
            "lang": _DEFAULT_LANG,
            "mode": int(enum_mode),
            "p_w": password,
            "platform": _DEFAULT_PLATFORM,
            "version": _DEFAULT_VERSION,
        }
        params: list[Any] = [self.token, serial_number, "set", payload]
        result = await self._async_post_ubus(params)
        return result

    async def _async_post_ubus(self, params: list[Any]) -> dict[str, Any]:
        """向 /ubus 发送请求并解析结果。"""
        session = await self._async_get_session()
        self._request_id += 1
        body = {
            "id": self._request_id,
            "jsonrpc": _DEFAULT_JSONRPC,
            "method": _DEFAULT_METHOD,
            "params": params,
        }
        url = f"{self._base_url}{_UBUS_PATH}"
        try:
            async with session.post(url, json=body) as response:
                if response.status != 200:
                    text = await response.text()
                    raise YoueJiaApiError(
                        f"接口返回非 200 状态码，status: {response.status}, body: {text}"
                    )
                data = await response.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise YoueJiaApiError("接口请求超时") from err
        except aiohttp.ClientError as err:
            raise YoueJiaApiError(f"接口请求异常: {err}") from err

        result = self._extract_result(data)
        return result

    @staticmethod
    def _extract_result(data: dict[str, Any]) -> dict[str, Any]:
        """从响应中提取结果字段。"""
        if "result" not in data:
            raise YoueJiaApiError("响应中缺少 result 字段")

        result = data["result"]
        if (
                not isinstance(result, list)
                or len(result) < 2
                or not isinstance(result[1], dict)
        ):
            raise YoueJiaApiError(f"result 格式不正确: {result}")

        error_code = result[0]
        payload: dict[str, Any] = result[1]
        if error_code != 0:
            raise YoueJiaApiError(f"接口返回错误码: {error_code}")

        return payload

    async def _async_get_session(self) -> aiohttp.ClientSession:
        """获取可用的 aiohttp 会话。"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._session_owner = True

        return self._session
