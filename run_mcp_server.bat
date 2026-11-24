@echo off
cd /d "%~dp0backend"
echo Install MCP SDK if needed: python -m pip install -r requirements-mcp.txt
python mcp_server.py
