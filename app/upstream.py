"""上游吉利接口调用：HMAC-SHA256 签名 + HTTP 请求。"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import HTTPException

from .config import get_settings


class UpstreamBusinessError(Exception):
    """上游返回 HTTP 200 但业务失败（success=false），携带上游真实原因。

    与网关/网络故障区分开：这类错误是可以并且应该告诉调用方的正常业务情况，
    例如“车辆不在线”。
    """

    def __init__(self, code: Any, msg: str | None) -> None:
        self.code = code
        self.msg = (msg or "").strip() or "上游业务处理失败"
        super().__init__(self.msg)


def _compact_json(body: dict[str, Any] | None) -> str:
    if body is None:
        return ""
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def _request_raw(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    method = method.upper()
    query = query or {}

    sorted_query_string = urllib.parse.urlencode(
        sorted((str(k), str(v)) for k, v in query.items())
    )
    request_body = _compact_json(body)

    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(10)
    string_to_sign = f"{timestamp}\n{nonce}\n{sorted_query_string}\n{request_body}"
    signature = hmac.new(
        settings.t6_sk.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    url = f"{settings.base_url}{path}"
    if sorted_query_string:
        url = f"{url}?{sorted_query_string}"

    headers = {
        "AccessKey": settings.t6_ak,
        "Timestamp": timestamp,
        "Nonce": nonce,
        "Signature": signature,
        "Accept": "application/json",
    }
    data = None
    if request_body:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = request_body.encode("utf-8")

    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=settings.upstream_timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            http_status = resp.status
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8", errors="replace")
        http_status = error.code
    except urllib.error.URLError as error:
        return {"httpStatus": None, "networkError": str(error.reason)}

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        payload = text
    return {"httpStatus": http_status, "response": payload}


def call_upstream(method: str, path: str, **kwargs: Any) -> Any:
    """调用上游并做统一校验，返回 data 字段。

    - 网关/网络真故障 → HTTPException(502)（脱敏，不暴露上游细节）。
    - 上游业务失败（success=false）→ UpstreamBusinessError（携带真实原因，可透传给调用方）。
    """
    result = _request_raw(method, path, **kwargs)
    if result.get("networkError") or result.get("httpStatus") != 200:
        raise HTTPException(status_code=502, detail="上游服务暂时不可用")
    response = result.get("response")
    if not isinstance(response, dict):
        raise HTTPException(status_code=502, detail="上游服务返回异常")
    if not response.get("success"):
        raise UpstreamBusinessError(response.get("code"), response.get("msg"))
    return response.get("data")
