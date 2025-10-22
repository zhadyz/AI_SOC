#!/usr/bin/env python3
"""
Simple MCP Server for MarkItDown
Converts documents (PDF, Word, Excel, PowerPoint, images, audio) to Markdown

Since markitdown-mcp has dependency issues on Python 3.14, this is a lightweight wrapper
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Any

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    print("Error: markitdown not installed. Run: pip install markitdown", file=sys.stderr)
    sys.exit(1)


class MarkItDownMCPServer:
    """Simple MCP server for MarkItDown"""

    def __init__(self):
        self.md = MarkItDown()

    async def handle_request(self, request: dict) -> dict:
        """Handle MCP request (JSON-RPC 2.0 format)"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "markitdown-mcp",
                        "version": "0.1.0"
                    }
                }
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "convert_to_markdown",
                            "description": "Convert a document (PDF, Word, Excel, PowerPoint, image, audio) to Markdown",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "file_path": {
                                        "type": "string",
                                        "description": "Path to the file to convert"
                                    }
                                },
                                "required": ["file_path"]
                            }
                        }
                    ]
                }
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name == "convert_to_markdown":
                    file_path = arguments.get("file_path")

                    if not file_path:
                        raise ValueError("file_path is required")

                    result_obj = self.md.convert(file_path)
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": result_obj.text_content
                            }
                        ]
                    }
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }

                raise ValueError(f"Unknown tool: {tool_name}")

            else:
                raise ValueError(f"Unknown method: {method}")

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

    async def run(self):
        """Run the MCP server (stdio mode)"""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )

                if not line:
                    break

                request = json.loads(line)
                response = await self.handle_request(request)
                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                error_response = {
                    "error": f"Invalid JSON: {str(e)}"
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                error_response = {
                    "error": f"Server error: {str(e)}"
                }
                print(json.dumps(error_response), flush=True)


async def main():
    server = MarkItDownMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
