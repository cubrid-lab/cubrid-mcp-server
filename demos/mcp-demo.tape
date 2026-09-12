# cubrid-mcp-server — MCP protocol demo (programmatic, no Claude Desktop)
Output ../docs/demo.gif
Set FontSize 16
Set Width 1200
Set Height 600
Set Theme "Catppuccin Mocha"
Set Shell bash

Type@50ms "pip install cubrid-mcp-server"
Enter
Sleep 3s

Type@50ms "python3"
Enter
Sleep 1s

Type@30ms "import subprocess, json, os"
Enter
Sleep 300ms

Type@30ms '# Start the MCP server as a subprocess'
Enter

Type@30ms 'env = {**os.environ, "CUBRID_HOST": "localhost", "CUBRID_DATABASE": "testdb", "CUBRID_USER": "dba"}'
Enter
Sleep 500ms

Type@30ms 'proc = subprocess.Popen(["python", "-m", "cubrid_mcp_server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True)'
Enter
Sleep 500ms

Type@30ms '# Initialize MCP session'
Enter

Type@30ms 'req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "demo", "version": "1.0"}}}'
Enter
Sleep 300ms

Type@30ms 'proc.stdin.write(json.dumps(req) + "\n"); proc.stdin.flush()'
Enter
Sleep 1s

Type@30ms 'resp = json.loads(proc.stdout.readline())'
Enter
Sleep 300ms

Type@30ms 'print(f"Server: {resp[\"result\"][\"serverInfo\"][\"name\"]}")'
Enter
Sleep 1s

Type@30ms 'print("12 tools available — read-only by default")'
Enter
Sleep 1s

Type@30ms 'proc.terminate()'
Enter
Sleep 500ms

Ctrl+D
