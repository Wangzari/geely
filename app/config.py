"""应用配置：全部来自 .env（通过 pydantic-settings 读取）。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 上游吉利接口（服务端保密，切勿外泄）----
    base_url: str = "https://express-geelycv.gofurther.cn/m4api"
    t6_ak: str
    t6_sk: str
    default_vehicle_code: str = "LA9CABED8TW100164"
    upstream_timeout: int = 20

    # ---- 对外服务安全配置 ----
    service_api_keys: str = ""          # 逗号分隔，允许调用方的密钥
    service_allowed_vehicles: str = ""  # 逗号分隔，允许查询的车辆编码
    service_cors_origins: str = ""      # 逗号分隔，允许的跨域来源
    service_trusted_hosts: str = "*"    # 逗号分隔，允许的 Host 头
    service_rate_limit: int = 60        # 每个 Key 每分钟最大请求数

    @staticmethod
    def _split(value: str) -> set[str]:
        return {item.strip() for item in value.split(",") if item.strip()}

    @property
    def api_keys(self) -> set[str]:
        return self._split(self.service_api_keys)

    @property
    def allowed_vehicles(self) -> set[str]:
        return self._split(self.service_allowed_vehicles) or {self.default_vehicle_code}

    @property
    def cors_origins(self) -> list[str]:
        return sorted(self._split(self.service_cors_origins))

    @property
    def trusted_hosts(self) -> list[str]:
        return sorted(self._split(self.service_trusted_hosts)) or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
