"""
Ralph Wiggum pipe for OpenWebUI.

title: Ralph Wiggum
description: Claude Code-like experience with OpenHands sandbox
version: 0.1.0
"""

import html as html_lib
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from httpx_sse import aconnect_sse
from pydantic import BaseModel, Field


class Pipe:
    """OpenWebUI Pipe for Ralph - lightweight HTTP client."""

    class Valves(BaseModel):
        """Configuration options exposed in OpenWebUI admin."""

        RALPH_SERVICE_URL: str = Field(
            default="http://host.docker.internal:8200",
            description="URL of the Ralph backend service",
        )
        ENABLE_LOGGING: bool = Field(
            default=True,
            description="Enable detailed logging",
        )

    def __init__(self) -> None:
        self.name = "Ralph Wiggum"
        self.valves = self.Valves()

    async def on_startup(self) -> None:
        if self.valves.ENABLE_LOGGING:
            print(f"Ralph Pipe started. Service: {self.valves.RALPH_SERVICE_URL}")

    async def on_shutdown(self) -> None:
        if self.valves.ENABLE_LOGGING:
            print("Ralph Pipe stopped")

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message with streaming."""
        # Extract messages (full history from OpenWebUI)
        messages = body.get("messages", [])
        if not messages:
            return "Error: No messages provided."

        # Extract user info
        user_id = __user__.get("id") if __user__ else None
        if not user_id:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": "Error: Could not identify user. Please log in."},
                    }
                )
            return ""

        # Get chat context
        chat_id = __metadata__.get("chat_id") if __metadata__ else None
        if not chat_id:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": "Error: No chat context available."},
                    }
                )
            return ""

        if self.valves.ENABLE_LOGGING:
            print(f"Ralph: user={user_id}, chat={chat_id}, messages={len(messages)}")

        try:
            async with (
                httpx.AsyncClient(timeout=300.0) as client,
                aconnect_sse(
                    client,
                    "POST",
                    f"{self.valves.RALPH_SERVICE_URL}/chat/stream",
                    json={
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "messages": [
                            {"role": m.get("role", "user"), "content": m.get("content", "")}
                            for m in messages
                        ],
                    },
                ) as event_source,
            ):
                async for sse in event_source.aiter_sse():
                    if sse.data:
                        await self._handle_sse_event(sse.data, __event_emitter__)
        except httpx.TimeoutException:
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "message", "data": {"content": "Error: Request timed out."}}
                )
        except httpx.ConnectError:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": "Error: Could not connect to Ralph service."},
                    }
                )
        except Exception as e:
            error_str = str(e)
            if "incomplete chunked read" in error_str or "peer closed" in error_str:
                if self.valves.ENABLE_LOGGING:
                    print("Ralph: stream closed (message delivered)")
            else:
                if self.valves.ENABLE_LOGGING:
                    print(f"Ralph error: {e}")
                if __event_emitter__:
                    await __event_emitter__(
                        {"type": "message", "data": {"content": f"Error: {error_str}"}}
                    )
        return ""

    @staticmethod
    def _format_tool_html(
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any] | str,
        done: bool,
        result: str | None = None,
    ) -> str:
        """Format a tool call as OpenWebUI <details> HTML."""
        if isinstance(arguments, dict):
            args_str = json.dumps(arguments, indent=2)
        else:
            args_str = str(arguments)

        attrs = (
            f'type="tool_calls" '
            f'done="{str(done).lower()}" '
            f'id="{html_lib.escape(tool_call_id)}" '
            f'name="{html_lib.escape(tool_name)}" '
            f'arguments="{html_lib.escape(args_str)}"'
        )
        if done and result is not None:
            attrs += f' result="{html_lib.escape(str(result))}"'

        summary = "Tool Executed" if done else "Executing..."
        return f"<details {attrs}>\n<summary>{summary}</summary>\n</details>\n\n"

    async def _handle_sse_event(
        self,
        data: str,
        emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
    ) -> None:
        """Handle SSE event from Ralph backend."""
        if not emitter:
            return
        try:
            event = json.loads(data)
            event_type = event.get("type")
            if event_type == "status":
                await emitter(
                    {
                        "type": "status",
                        "data": {
                            "description": event.get("content", "Processing..."),
                            "done": False,
                        },
                    }
                )
            elif event_type == "message":
                await emitter({"type": "message", "data": {"content": event.get("content", "")}})
            elif event_type == "done":
                await emitter({"type": "status", "data": {"description": "Complete", "done": True}})
            elif event_type == "error":
                await emitter(
                    {
                        "type": "message",
                        "data": {"content": f"Error: {event.get('message', 'Unknown')}"},
                    }
                )
            elif event_type == "tool_call_start":
                await emitter(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Running {event.get('tool_name', 'tool')}...",
                            "done": False,
                        },
                    }
                )
            elif event_type == "tool_call_complete":
                tool_html = self._format_tool_html(
                    tool_call_id=event.get("tool_call_id", ""),
                    tool_name=event.get("tool_name", ""),
                    arguments=event.get("tool_args", {}),
                    done=True,
                    result=event.get("result", ""),
                )
                await emitter({"type": "message", "data": {"content": tool_html}})
            elif event_type == "tool_call_error":
                tool_html = self._format_tool_html(
                    tool_call_id=event.get("tool_call_id", ""),
                    tool_name=event.get("tool_name", ""),
                    arguments={},
                    done=True,
                    result=f"Error: {event.get('error', 'Unknown')}",
                )
                await emitter({"type": "message", "data": {"content": tool_html}})
        except json.JSONDecodeError:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to parse SSE: {data}")
