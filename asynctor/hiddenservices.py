"""This script allows you to host hidden services or many in a single line of code
and it has optional enhancments if msgspec can be imported and used...
"""

from __future__ import annotations

import asyncio
import importlib.util as iutil
import inspect
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Awaitable, Callable

from .controller import open_controller
from .launcher import lauch_tor_with_context

DEFAULT_HOST = "127.0.0.1"


# Msgspec is an improvement because it can deserlize YAML format
# which is good for users who are looking to configure tor
# hidden-services before they start hosting their servers.

if iutil.find_spec("msgspec"):
    from typing import Annotated

    from msgspec import Meta, Struct, field

    PortInt = Annotated[int, Meta(gt=0, lt=65536)]

    class HiddenService(Struct, frozen=True):
        """A tor Hidden Service configuration block
        This can be used to setup a single hidden service"""

        port: PortInt
        host: str = DEFAULT_HOST
        hs_dir: Path | str | None = None
        ssl_port: PortInt | None = None

    class BatchService(Struct):
        """Used for helping setup one or multiple tor hidden services"""

        ctrl_port: PortInt
        client_port: PortInt | None = None
        password: str | None = None
        services: list[HiddenService] = field(default_factory=list)

        def add_service(
            self,
            port: int,
            host: str = DEFAULT_HOST,
            hs_dir: Path | str | None = None,
            ssl_port: int | None = None,
        ):
            """Adds a hidden service to your batch for hosting via life-span"""
            self.services.append(HiddenService(port, host, hs_dir, ssl_port))
            # Allow chaining...
            return self

        def __iter__(self):
            yield from self.services


# Fallback...
else:
    from dataclasses import dataclass, field

    @dataclass
    class HiddenService:
        """A tor Hidden Service configuration block
        This can be used to setup a single hidden service"""

        port: int
        host: str = DEFAULT_HOST
        hs_dir: Path | str | None = None
        ssl_port: int | None = None

        def __validate_port(self, port_name: str):
            """Private Method do not use!!!"""
            i = getattr(self, port_name)
            if i is None:
                return

            if not isinstance(i, int):
                raise TypeError(
                    f"{port_name} Should be an integer Not {type(i).__name__}"
                )

            elif i < 0 or i > 65536:
                raise ValueError(f"{port_name} should be between 0 <-> 65536  Not {i}")

        def __post_init__(self):
            self.__validate_port("port")
            self.__validate_port("ssl_port")

    @dataclass
    class BatchService:
        """Used for helping setup one or multiple tor hidden services"""

        ctrl_port: int
        client_port: int | None = None
        """Optional, allows a client proxy to be configured alongside the server..."""
        password: str | None = None
        services: list[HiddenService] = field(default_factory=list)

        def __validate_port(self, port_name: str):
            """Private Method do not use!!!"""
            i = getattr(self, port_name)
            if i is None:
                return

            if not isinstance(i, int):
                raise TypeError(
                    f"{port_name} Should be an integer Not {type(i).__name__}"
                )

            elif i < 0 or i > 65536:
                raise ValueError(f"{port_name} should be between 0 <-> 65536  Not {i}")

        def __post_init__(self):
            self.__validate_port("ctrl_port")
            self.__validate_port("client_port")

        def add_service(
            self,
            port: int,
            host: str = DEFAULT_HOST,
            hs_dir: Path | str | None = None,
            ssl_port: int | None = None,
        ):
            """Adds a hidden service to your batch for hosting via life-span"""
            self.services.append(HiddenService(port, host, hs_dir, ssl_port))
            # Allow chaining...
            return self

        def __iter__(self):
            yield from self.services


async def __handle_callback(cb: Callable[[str], Awaitable[None] | None], item: str):
    if inspect.iscoroutinefunction(cb):
        await cb(item)
    else:
        await asyncio.to_thread(cb, item)


@asynccontextmanager
async def host_multiple(
    batch: BatchService,
    msg_handle_callback: Callable[[str], Awaitable[None] | None] | None = None,
    onion_launched_callback: Callable[[str], Awaitable[None] | None] | None = None,
):
    """Launches up multiple tor hidden services from one BatchService"""

    assert batch.services, "Batch requires at least 1 hidden service before running..."

    config = {"ControlPort": str(batch.ctrl_port)}
    if batch.client_port is not None:
        config["SocksPort"] = str(batch.client_port)

    async with lauch_tor_with_context(
        config, init_msg_handler=msg_handle_callback, take_ownership=True
    ):
        async with open_controller(
            batch.ctrl_port, auto_auth=True, password=batch.password
        ) as ctrl:
            if onion_launched_callback is not None:
                for hs in batch:
                    h = await ctrl.host_hidden_service(
                        hs.port, hs.host, hs.hs_dir, hs.ssl_port
                    )
                    await __handle_callback(onion_launched_callback, h)
            else:
                for hs in batch:
                    await ctrl.host_hidden_service(
                        hs.port, hs.host, hs.hs_dir, hs.ssl_port
                    )

        # Keep the process alive...
        yield


def host_single(
    ctrl_port: int,
    server_port: int,
    server_ssl_port: int | None = None,
    hidden_service_dir: Path | str | None = None,
    client_port: int | None = None,
    password: str | None = None,
    msg_handle_callback: Callable[[str], Awaitable[None] | None] | None = None,
    onion_launched_callback: Callable[[str], Awaitable[None] | None] | None = None,
):
    """Hosts a single hidden service over a lifespan of it's context manager"""

    return host_multiple(
        batch=BatchService(ctrl_port, client_port, password).add_service(
            port=server_port, ssl_port=server_ssl_port, hs_dir=hidden_service_dir
        ),
        msg_handle_callback=msg_handle_callback,
        onion_launched_callback=onion_launched_callback,
    )
