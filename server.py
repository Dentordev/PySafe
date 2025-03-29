from aiohttp import web
from pysafe.config import get_upload_limit, init_config, get_config
from pysafe.tables import new_file, SQLBase, find_file
import aiohttp_sqlalchemy
from asynctor import host_single
from pathlib import Path

import asyncio 
import sys


route = web.RouteTableDef()
route.static("/static", "static")

@route.post("/upload")
async def upload_file(request:web.Request):
    multipart = await request.multipart()
    file = None
    while part := await multipart.next():
        if part.name == "file":
            file = await new_file(request, part, part.filename, get_upload_limit(request.app))
            
    assert file is not None
    return web.Response(body=file.url_response().encode(), status=200, content_type="text/html")


@route.get("/uploads/{name}")
async def download_file(request:web.Request):
    return await find_file(request,  request.match_info["name"])

@route.get("/")
async def home(request:web.Request):
    return web.HTTPFound("/static/home.html")

async def app_factory():
    app = web.Application()
    init_config(app)
    config = get_config(app)
    if not config.path.exists():
        print("making default directory under (uploads) is this what you wanted??")
        default_path = Path("uploads")
        default_path.mkdir()
        config.path = default_path
    

    aiohttp_sqlalchemy.setup(
        app,
        [
            aiohttp_sqlalchemy.bind("sqlite+aiosqlite:///uploads.db"),
        ],
    )
    
    app.add_routes(route)

    await aiohttp_sqlalchemy.init_db(app, SQLBase.metadata)
    
    if config.tor:
        async with host_single(ctrl_port=9051, server_port=config.port, onion_launched_callback=print):
            await web._run_app(app, port=config.port)
    else:
        await web._run_app(app, port=config.port)


if __name__ == "__main__":

    try:
        if sys.platform in ["win32", "cygwin", "cli"]:
            import winloop # type: ignore
            winloop.run(app_factory())

        else:
            import uvloop # type: ignore
            uvloop.run(app_factory())
            
    except ModuleNotFoundError:
        # Fallback
        asyncio.run(app_factory())
