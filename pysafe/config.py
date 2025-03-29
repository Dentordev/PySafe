from pysafe.hfilesize import FileSize
from msgspec import Struct, field, Meta
from msgspec.yaml import decode
from aiohttp import web
from typing import Union, Annotated, cast
from pathlib import Path
from datetime import timedelta
import re


class Config(Struct):
    port: int
    path_name: str = field(name="path")
    size_limit: Union[int, str] = field(name="limit")
    expires: Annotated[str, Meta(pattern=r"[0-9]+\s+(week|day|month|year)s?")] = (
        "1 week"
    )
    api: bool = False

    @property
    def size(self):
        return FileSize(self.size_limit)

    @property
    def path(self):
        return Path(self.path_name)

    @property
    def expiration_time(self):
        _match = re.search(r"([0-9]+)\s+(week|day|month|year)s?", self.expires)
        return timedelta(**{_match.group(2) + "s": int(_match.group(1))})

    @classmethod
    def read(cls):
        with open("config.yaml", "r") as r:
            t = decode(r.read(), type=cls)
        return t


def init_config(app: web.Application):
    app["PYSAFE-CONFIG"] = Config.read()


def get_config(app: web.Application) -> Config:
    return cast(Config, app["PYSAFE-CONFIG"])


# @lru_cache


def get_upload_limit(app: web.Application) -> FileSize:
    return get_config(app).size


# @lru_cache


def get_upload_path(app: web.Application) -> Path:
    return get_config(app).path


def get_expiration_time(app: web.Application) -> timedelta:
    return get_config(app).expiration_time
