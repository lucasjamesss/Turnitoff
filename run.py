"""Launcher. Installed to ~/.turnitoff/run.py so hooks and the MCP server have a stable path.

    run.py mcp          start the MCP server (stdio)
    run.py hook         Claude Code hook (JSON on stdin)
    run.py scan FILE    anything else goes to the turnitoff command line
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if len(sys.argv) > 1 and sys.argv[1] == "mcp":
    from turnitoff.mcp_server import main as mcp_main

    mcp_main()
else:
    from turnitoff.cli import main

    main()
