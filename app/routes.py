"""三个对外接口：开启多路视频、实时车辆位置、查询车辆详情。"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Path, Query

from .models import (
    FailedChannel,
    LocationResponse,
    TireInfo,
    VehicleDetailResponse,
    VideoResponse,
    VideoStream,
)
from .security import authenticate, ensure_vehicle_allowed
from .upstream import UpstreamBusinessError, call_upstream

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])

CHANNELS = {0: "前", 1: "后", 2: "左", 3: "右"}
LOCATION_STATUS_TEXT = {0: "有效", 1: "定位中", 2: "定位无效", 3: "未识别"}
VEHICLE_STATUS_TEXT = {0: "正常", 1: "故障", 2: "锁定"}
ONLINE_TEXT = {0: "下线", 1: "在线"}
CHARGE_TYPE_TEXT = {0: "未充电", 1: "有线充电", 2: "无线充电", -1: "UNRECOGNIZED"}
TIRE_POSITION_TEXT = {"LF": "左前轮", "RF": "右前轮", "LR": "左后轮", "RR": "右后轮"}
VEHICLE_CODE_PATTERN = r"^[A-Za-z0-9]{6,32}$"


def _extract_m3u8(data: Any) -> str | None:
    if isinstance(data, dict):
        url = data.get("m3u8")
        if isinstance(url, str) and url:
            return url
    return None


def _as_number(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _parse_channels(raw: str) -> list[int]:
    from fastapi import HTTPException

    result: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit() or int(token) not in CHANNELS:
            raise HTTPException(status_code=422, detail=f"非法通道：{token}")
        if int(token) not in result:
            result.append(int(token))
    if not result:
        raise HTTPException(status_code=422, detail="未指定有效通道")
    return result


@router.post(
    "/vehicles/{vehicle_code}/video",
    response_model=VideoResponse,
    summary="开启多路视频并返回播放地址",
)
def open_video(
    vehicle_code: str = Path(..., pattern=VEHICLE_CODE_PATTERN),
    channels: str = Query("0,1,2,3", description="通道，逗号分隔。0前 1后 2左 3右。"),
) -> VideoResponse:
    from fastapi import HTTPException

    ensure_vehicle_allowed(vehicle_code)

    requested = _parse_channels(channels)
    streams: list[VideoStream] = []
    failed: list[FailedChannel] = []
    for channel in requested:
        try:
            data = call_upstream(
                "POST",
                "/openapi/vehicle/video/open",
                body={"vehicleCode": vehicle_code, "videoChannel": channel},
            )
        except UpstreamBusinessError as error:
            # 上游业务失败（如“车辆不在线”＝未开机），记录真实原因。
            failed.append(
                FailedChannel(channel=channel, direction=CHANNELS[channel], reason=error.msg)
            )
            continue

        url = _extract_m3u8(data)
        if url:
            streams.append(VideoStream(channel=channel, direction=CHANNELS[channel], m3u8=url))
        else:
            failed.append(
                FailedChannel(
                    channel=channel, direction=CHANNELS[channel], reason="上游未返回播放地址"
                )
            )

    # 全部通道都失败：整车没开机/离线，明确返回 409，避免调用方误以为服务故障。
    if not streams and failed:
        raise HTTPException(status_code=409, detail=failed[0].reason)

    return VideoResponse(
        vehicleCode=vehicle_code,
        streams=streams,
        failedChannels=failed,
        timestamp=int(time.time() * 1000),
    )


@router.get(
    "/vehicles/{vehicle_code}/location",
    response_model=LocationResponse,
    summary="实时返回车辆位置",
)
def get_location(
    vehicle_code: str = Path(..., pattern=VEHICLE_CODE_PATTERN),
) -> LocationResponse:
    from fastapi import HTTPException

    ensure_vehicle_allowed(vehicle_code)

    data = call_upstream("GET", "/openapi/vehicle/list")
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="上游服务返回异常")

    vehicle = next(
        (v for v in data if isinstance(v, dict) and v.get("vehicleCode") == vehicle_code),
        None,
    )
    if vehicle is None:
        raise HTTPException(status_code=404, detail="未找到该车辆")

    location_status = _as_int(vehicle.get("locationStatus"))
    return LocationResponse(
        vehicleCode=vehicle_code,
        vehicleName=vehicle.get("vehicleName") or None,
        online=_as_int(vehicle.get("online")),
        status=_as_int(vehicle.get("status")),
        longitude=_as_number(vehicle.get("longitude")),
        latitude=_as_number(vehicle.get("latitude")),
        azimuth=_as_number(vehicle.get("azimuth")),
        locationStatus=location_status,
        locationStatusText=LOCATION_STATUS_TEXT.get(location_status)
        if location_status is not None
        else None,
        timestamp=int(time.time() * 1000),
    )


@router.get(
    "/vehicles/{vehicle_code}/detail",
    response_model=VehicleDetailResponse,
    summary="查询车辆详情",
)
def get_vehicle_detail(
    vehicle_code: str = Path(..., pattern=VEHICLE_CODE_PATTERN),
) -> VehicleDetailResponse:
    from fastapi import HTTPException

    ensure_vehicle_allowed(vehicle_code)

    try:
        data = call_upstream(
            "GET", "/openapi/vehicle/detail", query={"vehicleCode": vehicle_code}
        )
    except UpstreamBusinessError as error:
        raise HTTPException(status_code=409, detail=error.msg)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="上游服务返回异常")

    status = _as_int(data.get("status"))
    online = _as_int(data.get("online"))
    charge_type = _as_int(data.get("chargeType"))
    location_status = _as_int(data.get("locationStatus"))

    tire_list = data.get("tireInfoList")
    tires: list[TireInfo] | None = None
    if isinstance(tire_list, list):
        tires = [
            TireInfo(
                name=t.get("name") or None,
                positionDesc=t.get("positionDesc")
                or TIRE_POSITION_TEXT.get(str(t.get("name") or "")),
                pressure=_as_number(t.get("pressure")),
            )
            for t in tire_list
            if isinstance(t, dict)
        ]

    return VehicleDetailResponse(
        vehicleCode=vehicle_code,
        vehicleId=str(data["vehicleId"]) if data.get("vehicleId") is not None else None,
        siteId=str(data["siteId"]) if data.get("siteId") is not None else None,
        vehicleName=data.get("vehicleName") or None,
        licensePlateNumber=data.get("licensePlateNumber") or None,
        vin=data.get("vin") or None,
        vehicleFrameNo=data.get("vehicleFrameNo") or None,
        vehicleModelName=data.get("vehicleModelName") or None,
        status=status,
        statusText=VEHICLE_STATUS_TEXT.get(status) if status is not None else None,
        online=online,
        onlineText=ONLINE_TEXT.get(online) if online is not None else None,
        chargeType=charge_type,
        chargeTypeText=CHARGE_TYPE_TEXT.get(charge_type)
        if charge_type is not None
        else None,
        residualFuel=_as_number(data.get("residualFuel")),
        executeTaskId=str(data["executeTaskId"])
        if data.get("executeTaskId") is not None
        else None,
        mapVersion=data.get("mapVersion") or None,
        programVersion=data.get("programVersion") or None,
        longitude=_as_number(data.get("longitude")),
        latitude=_as_number(data.get("latitude")),
        azimuth=_as_number(data.get("azimuth")),
        locationStatus=location_status,
        locationStatusText=LOCATION_STATUS_TEXT.get(location_status)
        if location_status is not None
        else None,
        tireInfoList=tires,
        timestamp=int(time.time() * 1000),
    )
