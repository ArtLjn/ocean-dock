"""Ocean Dock MCP Server — 将 session 管理能力暴露为 MCP 协议"""

from ocean_dock.mcp.server import mcp, register_tools

__all__ = ["mcp", "register_tools"]
