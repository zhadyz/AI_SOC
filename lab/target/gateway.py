#!/usr/bin/env python3
"""Capability-free ingress ACL for the disposable lab's HTTP and SSH services."""
import asyncio
import json
from pathlib import Path

ACL = Path('/run/ai-soc/blocked-ips.json')
ACTIVE = {}


def blocked():
    # A malformed policy closes ingress rather than silently allowing traffic.
    try:
        values = json.loads(ACL.read_text())
        if not isinstance(values, list) or not all(isinstance(ip, str) for ip in values):
            raise ValueError('Invalid ACL')
        return set(values)
    except (OSError, ValueError):
        return None


async def connection(reader, writer, backend):
    peer = writer.get_extra_info('peername')[0]
    remote = None
    policy = blocked()
    if policy is None or peer in policy:
        writer.close()
        await writer.wait_closed()
        return
    ACTIVE[writer] = peer
    async def pipe(source, destination):
        while chunk := await source.read(65536):
            destination.write(chunk)
            await destination.drain()
    tasks = []
    try:
        upstream, remote = await asyncio.open_connection('127.0.0.1', backend)
        tasks = [asyncio.create_task(pipe(reader, remote)), asyncio.create_task(pipe(upstream, writer))]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (ConnectionError, OSError):
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        ACTIVE.pop(writer, None)
        writer.close()
        if remote:
            remote.close()


async def enforce_existing_connections():
    while True:
        policy = blocked()
        for writer, peer in list(ACTIVE.items()):
            if policy is None or peer in policy:
                writer.close()
        await asyncio.sleep(0.25)


async def main():
    servers = []
    for port, backend in [(8080, 18080), (2222, 12222)]:
        servers.append(await asyncio.start_server(lambda r, w, b=backend: connection(r, w, b), '0.0.0.0', port))
    await asyncio.gather(enforce_existing_connections(), *(server.serve_forever() for server in servers))


if __name__ == '__main__':
    asyncio.run(main())
