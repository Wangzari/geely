"""对外接口的响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class VideoStream(BaseModel):
    channel: int
    direction: str
    m3u8: str


class FailedChannel(BaseModel):
    channel: int
    direction: str
    reason: str


class VideoResponse(BaseModel):
    vehicleCode: str
    streams: list[VideoStream]
    failedChannels: list[FailedChannel]
    timestamp: int


class LocationResponse(BaseModel):
    vehicleCode: str
    vehicleName: str | None = None
    online: int | None = None
    status: int | None = None
    longitude: float | None = None
    latitude: float | None = None
    azimuth: float | None = None
    locationStatus: int | None = None
    locationStatusText: str | None = None
    timestamp: int


class TireInfo(BaseModel):
    name: str | None = None
    positionDesc: str | None = None
    pressure: float | None = None


class VehicleDetailResponse(BaseModel):
    vehicleCode: str
    vehicleId: str | None = None
    siteId: str | None = None
    vehicleName: str | None = None
    licensePlateNumber: str | None = None
    vin: str | None = None
    vehicleFrameNo: str | None = None
    vehicleModelName: str | None = None
    status: int | None = None
    statusText: str | None = None
    online: int | None = None
    onlineText: str | None = None
    chargeType: int | None = None
    chargeTypeText: str | None = None
    residualFuel: float | None = None
    executeTaskId: str | None = None
    mapVersion: str | None = None
    programVersion: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    azimuth: float | None = None
    locationStatus: int | None = None
    locationStatusText: str | None = None
    tireInfoList: list[TireInfo] | None = None
    timestamp: int
