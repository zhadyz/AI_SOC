"""Exercise real TCP acceptance, revocation and restoration on ephemeral ports."""
import asyncio

from lab.target import gateway


async def test_gateway_closes_existing_connections_and_restores_ingress(tmp_path, monkeypatch):
    acl = tmp_path / 'policy.json'
    acl.write_text('[]')
    monkeypatch.setattr(gateway, 'ACL', acl)
    monkeypatch.setattr(gateway, 'ACTIVE', {})
    async def echo(reader, writer):
        try:
            while chunk := await reader.read(64):
                writer.write(chunk)
                await writer.drain()
        finally:
            writer.close()
    backend = await asyncio.start_server(echo, '127.0.0.1', 0)
    port = backend.sockets[0].getsockname()[1]
    ingress = await asyncio.start_server(lambda r, w: gateway.connection(r, w, port), '127.0.0.1', 0)
    ingress_port = ingress.sockets[0].getsockname()[1]
    watcher = asyncio.create_task(gateway.enforce_existing_connections())
    writers = []
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', ingress_port)
        writers.append(writer)
        writer.write(b'baseline')
        await writer.drain()
        assert await asyncio.wait_for(reader.read(64), 2) == b'baseline'
        acl.write_text('["127.0.0.1"]')
        assert await asyncio.wait_for(reader.read(64), 2) == b''
        for policy in ['["127.0.0.1"]', '{broken']:
            acl.write_text(policy)
            denied, writer = await asyncio.open_connection('127.0.0.1', ingress_port)
            writers.append(writer)
            assert await asyncio.wait_for(denied.read(64), 2) == b''
        acl.write_text('[]')
        restored, writer = await asyncio.open_connection('127.0.0.1', ingress_port)
        writers.append(writer)
        writer.write(b'restored')
        await writer.drain()
        assert await asyncio.wait_for(restored.read(64), 2) == b'restored'
    finally:
        for writer in writers:
            writer.close()
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        for server in [ingress, backend]:
            server.close()
            await server.wait_closed()
