from sqlalchemy.orm import MappedAsDataclass, DeclarativeBaseNoMeta
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy import select
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from typing import Optional, TYPE_CHECKING, ClassVar
import secrets
import aiofiles

from aiohttp import web
from aiohttp.multipart import BodyPartReader
from pathlib import Path
import hashlib
from aiohttp_sqlalchemy import get_session
import os
import pysafe.config as config


from mimetypes import guess_extension

from msgspec.json import Encoder


class SQLBase(MappedAsDataclass, DeclarativeBaseNoMeta):
    if TYPE_CHECKING:
        __encoder__: ClassVar[Encoder]

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def __init_subclass__(cls, **kw):
        cls.__encoder__ = Encoder()
        return super().__init_subclass__(**kw)

    def json(self):
        return self.__encoder__.encode(self)


FILE_TYPE_DICT = {
    ".webp": "image/webp",
    ".png": "image/apng",
    ".apng": "image/apng",
}


class File(SQLBase):
    name: Mapped[str] = mapped_column(String, unique=True)
    original_name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    size: Mapped[str] = mapped_column(String)

    # TODO: Make repeated uploads unqiue, sha1 has collisions or use
    # sha256+sha1 to prevent collisions.

    sha1_hash: Mapped[str] = mapped_column(String)
    uploaded: Mapped[datetime] = mapped_column(DateTime)
    expires: Mapped[datetime] = mapped_column(DateTime)
    id: Mapped[Optional[int]] = mapped_column(Integer, primary_key=True, default=None)

    def get_destination(self, req: web.Request):
        """Obtains where the file is located"""
        return config.get_upload_path(req.app) / (self.name + self.type)

    def json_response(self):
        """The API Response"""
        return web.Response(
            body=self.json(), status=200, content_type="application/json"
        )

    def content_type(self):
        # "application/octet-stream"
        return guess_extension(self.original_name)

    def url_response(self):
        """Formats the url's upload location"""
        return f"/uploads/{self.name}"

    def stream_file(self, req: web.Request):
        resp = web.FileResponse(
            self.get_destination(req),
            status=200,
        )
        # Aiohttp has trouble identifying some files so let's assist it...
        resp.content_type = self.content_type()
        return resp


async def new_file(req: web.Request, part: BodyPartReader, filename: str, limit: int):
    sha1 = hashlib.sha1()
    name = secrets.token_urlsafe(10)
    file_type = Path(filename).suffix
    upload_path = config.get_upload_path(req.app)
    size = 0

    async with aiofiles.open(upload_path / (name + file_type), "wb") as w:
        while bits := await part.read_chunk(10240):
            size += len(bits)
            if size > limit:
                await w.close()
                # Delete bad file...
                os.remove(upload_path / (name + file_type))
                raise web.HTTPConflict(
                    body=b'{"error": "file is too big to upload"}',
                    content_type="application/json",
                )
            await w.write(bits)
            sha1.update(bits)

    file = File(
        name,
        filename,
        type=file_type,
        size=str(size),
        sha1_hash=sha1.hexdigest(),
        uploaded=datetime.now(),
        expires=datetime.now() + config.get_expiration_time(req.app),
    )

    async with get_session(req) as s:
        await s.merge(file)
        await s.commit()

    return file


async def find_file(req: web.Request, name: str):
    async with get_session(req) as s:
        scalar = await s.execute(select(File).where(File.name == name))
        file = scalar.scalar_one_or_none()

    if file is None:
        raise web.HTTPNotFound(
            body=f"<html><body><h1>Not Found</h1><p>Could not find {name}</p></body></html>",
            content_type="text/html",
        )

    return file
