"""Implemented on over from stem's python library for use with asynchronous processes..."""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from contextlib import asynccontextmanager
from typing import AnyStr, Awaitable, Callable, Optional, TypeVar, Union

T = TypeVar("T")


NO_TORRC = "<no torrc>"
DEFAULT_INIT_TIMEOUT = 90


def encode_bytes(data: AnyStr):
    return (
        data.encode("utf-8", errors="surrogateescape")
        if isinstance(data, str)
        else data
    )


# One thing stem tor lacks is typehinting and annotations for pyright's sake.
# Here, we don't give a flying shit because were using 3.9 and above (At least Hope you are).
async def launch_tor(
    tor_cmd="tor",
    args: Optional[list[str]] = None,
    torrc_path=None,
    completion_percent=100,
    init_msg_handler: Optional[Callable[[AnyStr], Union[None, Awaitable[None]]]] = None,
    take_ownership=False,
    close_output=True,
    stdin: Optional[AnyStr] = None,
) -> asyncio.subprocess.Process:
    """Launches tor over an asynchronous process"""

    # TODO: (This might not be required?)
    # if platform.system() == 'Windows':
    #     if timeout is not None and timeout != DEFAULT_INIT_TIMEOUT:
    #         raise OSError('You cannot launch tor with a timeout on Windows')

    runtime_args, temp_file = [tor_cmd], None

    if args:
        runtime_args += args

    if torrc_path:
        if torrc_path == NO_TORRC:
            temp_file = tempfile.mkstemp(prefix="empty-torrc-", text=True)[1]
            runtime_args += ["-f", temp_file]
        else:
            runtime_args += ["-f", torrc_path]

    if take_ownership:
        runtime_args += ["__OwningControllerProcess", str(os.getpid())]

    tor_process = None

    try:
        tor_process = await asyncio.create_subprocess_shell(
            " ".join(runtime_args),
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if stdin:
            tor_process.stdin.write(encode_bytes(stdin))
            await tor_process.stdin.drain()
            tor_process.stdin.close()

        bootstrap_line = re.compile("Bootstrapped ([0-9]+)%")
        problem_line = re.compile("\\[(warn|err)\\] (.*)$")
        last_problem = "Timed out"

        while True:
            init_line = (await tor_process.stdout.readline()).decode("utf-8", "replace")

            if not init_line:
                raise OSError("Process terminated: %s" % last_problem)

            if init_msg_handler:
                if asyncio.iscoroutinefunction(init_msg_handler):
                    await init_msg_handler(init_line)
                else:
                    init_msg_handler(init_line)

            bootstrap_match = bootstrap_line.search(init_line)
            problem_match = problem_line.search(init_line)

            if bootstrap_match and int(bootstrap_match.group(1)) >= completion_percent:
                return tor_process

            elif problem_match:
                _, msg = problem_match.groups()
                if "see warnings above" not in msg:
                    if ": " in msg:
                        msg.split(": ")[-1].strip()
                    last_problem = msg

    except:
        if tor_process and (tor_process.returncode is None):
            tor_process.kill()
            await tor_process.wait()
        raise

    finally:
        if tor_process and close_output and (tor_process.returncode is None):
            tor_process.terminate()

        if temp_file:
            try:
                os.remove(temp_file)
            except:
                pass


async def lauch_tor_with_config(
    config: dict,
    tor_cmd: str = "tor",
    completion_percent=100,
    init_msg_handler=None,
    take_ownership=False,
    close_output=True,
):
    if "Log" in config:
        stdout_options = ["DEBUG stdout", "INFO stdout", "NOTICE stdout"]
        if isinstance(config["Log"], str):
            config["Log"] = [config["Log"]]

        has_stdout = False
        for log_config in config["Log"]:
            if log_config in stdout_options:
                has_stdout = True
                break

        if not has_stdout:
            config["Log"].append("NOTICE stdout")

    config_str = ""

    for key, values in list(config.items()):
        if isinstance(values, str):
            config_str += "%s %s\n" % (key, values)
        else:
            for value in values:
                config_str += "%s %s\n" % (key, value)

    return await launch_tor(
        tor_cmd,
        ["-f", "-"],
        None,
        completion_percent,
        init_msg_handler,
        take_ownership,
        close_output,
        stdin=config_str,
    )


@asynccontextmanager
async def lauch_tor_with_context(
    config: dict,
    tor_cmd: str = "tor",
    completion_percent=100,
    init_msg_handler: Optional[Callable[[AnyStr], Union[None, Awaitable[None]]]] = None,
    take_ownership=False,
    close_output=True,
):
    """
    Provides built-in process handling within an
    asynchronous context manager

    process will be killed after context is allowed
    to exit, This provides the the ability to setup
    without the stress of needing to close here we have
    a minimal example of how that works

    ::

        from asynctor import launch_tor_with_context
        from aiohttp_socks import ProxyConnector
        from aiohttp import request


        async def tor_request(proxy_port:int = 9050, ctrlport:int = 9051):
            async with lauch_tor_with_context(
                {
                    'SocksPort': str(proxy_port),
                    'ControlPort': str(ctrl_port)
                },
                take_ownership=True):
                async with ProxyConnector.from_url("socks5://127.0.0.1:9150") as con:
                    async with request("GET", "https://httpbin.org/ip") as resp:
                        data = await resp.json()
                        print(data['origin'])

    ::
    """
    try:
        process = await lauch_tor_with_config(
            config,
            tor_cmd,
            completion_percent,
            init_msg_handler,
            take_ownership,
            close_output,
        )
        yield
    finally:
        pass
