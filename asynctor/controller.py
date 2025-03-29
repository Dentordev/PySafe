"""Asynchronous version of stem's controller system (bare minimum) functionality"""

from __future__ import annotations

import asyncio
import collections
import os
import pathlib
import sys
from contextlib import asynccontextmanager
from typing import AnyStr, Dict, List, Optional, Tuple, Union


class AsyncController:
    """used primarally for communications with tor over asyncio"""

    def __init__(
        self, streams=Tuple[asyncio.StreamReader, asyncio.StreamWriter]
    ) -> None:
        self.reader, self.writer = streams

    async def authenticate(self, password: Optional[AnyStr] = None):
        if password:
            self.writer.write(f'AUTHENTICATE "{self.password}"\r\n'.encode("utf-8"))
        else:
            self.writer.write(b"AUTHENTICATE\r\n")
        await self.writer.drain()
        resp = await self.reader.read(8)
        if resp != b"250 OK\r\n":
            raise RuntimeError(
                'Authentication Failed "{}"'.format(resp.decode("utf-8", "replace"))
            )

    async def signal_newnym(self):
        self.writer.write(b"SIGNAL NEWNYM\r\n")
        await self.writer.drain()
        resp = await self.reader.read(8)
        if resp != b"250 OK\r\n":
            raise RuntimeError("Could not rotate tor exit node...")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.writer.close()
        await self.writer.wait_closed()

    async def set_options(
        self, params: Union[List[Tuple[str, str]], Dict[str, str]], reset=False
    ):
        # constructs the SETCONF or RESETCONF query
        query_comp = ["RESETCONF" if reset else "SETCONF"]

        if isinstance(params, dict):
            params = list(params.items())

        for param, value in params:
            if isinstance(value, str):
                query_comp.append('%s="%s"' % (param, value.strip()))
            elif isinstance(value, collections.abc.Iterable):
                query_comp.extend(['%s="%s"' % (param, val.strip()) for val in value])
            elif not value:
                query_comp.append(param)
            else:
                raise ValueError(
                    "Cannot set %s to %s since the value was a %s but we only accept strings"
                    % (param, value, type(value).__name__)
                )

        query = " ".join(query_comp)

        self.writer.write(query.encode("utf-8", errors="replace") + b"\r\n")
        await self.writer.drain()

        data = await self.reader.read(1024)

        assert data == b"250 OK\r\n", f"GOT {data}"

    async def host_hidden_service(
        self,
        port: int,
        host: str = "127.0.0.1",
        hs_dir: str = None,
        ssl_port: Optional[int] = None,
    ) -> str:
        """Sets a hidden service to be hosted, returns with the host's name by default..."""
        if not hs_dir:
            hs_dir = os.path.join(os.getcwd(), ".hidden-service")
            if not os.path.exists(hs_dir):
                os.mkdir(".hidden-service")

        if sys.platform == "win32":
            # NOTE: There is no documentation about this but
            # Tor has problems with parsing normal windows
            # directories given with "\\" <- this string,
            # swaping directory from windows to posix paths
            # solves the problem

            hs_dir = pathlib.Path(hs_dir).as_posix()

        args = [
            ("HiddenServiceDir", hs_dir),
            ("HiddenServicePort", "80 %s:%s" % (host, str(port))),
        ]
        if ssl_port:
            args.append(("HiddenServicePort", "443 %s:%s" % (host, str(ssl_port))))

        await self.set_options(args)

        return (pathlib.Path(hs_dir) / "hostname").read_text().strip()


@asynccontextmanager
async def open_controller(
    ctrl_port: int = 9150,
    host: str = "127.0.0.1",
    auto_auth: bool = True,
    password: str | None = None,
):
    """Opens asynchronous sockets to the tor controller being used"""
    streams = await asyncio.open_connection(host, ctrl_port)
    async with AsyncController(streams) as ac:
        if auto_auth:
            await ac.authenticate()
        yield ac
