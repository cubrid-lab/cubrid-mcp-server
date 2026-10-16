# Quick Start

> 한국어: [빠른 시작](ko/quickstart.md)

This walkthrough connects one MCP client to a small sample database and reads
from it, without giving the model more than read access to one table.

Three pieces take part:

- **CUBRID** is the database server. It stores the data and must already be
  running; installing this package does not install CUBRID.
- **cubrid-mcp-server** (this project) connects an MCP client to that data.
  It offers *tools* such as `all_table_names` and `execute_query`, and it
  connects to CUBRID with the account you give it.
- An **MCP client** starts the server, lists its tools and calls them: an AI
  chat application, or, in this walkthrough, a short Python script.

The server speaks MCP over **stdio**: the client starts it as a child process
and talks to it through its standard input and output. It is not a web server
and has no URL. Started by hand in a terminal, it prints a banner and then waits
for MCP messages on its input; that is neither a hang nor proof that it reached
the database. Press Ctrl+C to stop it.

The main path below was run as written on Linux (x86_64) with bash, Docker,
Python 3.12, cubrid-mcp-server 0.5.1 from PyPI and its FastMCP 4.1.0 client,
against the `cubrid/cubrid:11.4` image. It keeps the same names throughout:
the database `testdb`, the table `dba.mcp_quickstart_books` and the account
`mcp_reader`.

!!! note "Which versions this walkthrough describes"
    - **Document source:** the `main` branch, as the notice at the top of the
      site says. `main` can be ahead of the latest published release.
    - **Package release:** `pip install cubrid-mcp-server` installs the newest
      version on [PyPI](https://pypi.org/project/cubrid-mcp-server/) that
      supports your Python; its notes are on the
      [release list](https://github.com/cubrid-lab/cubrid-mcp-server/releases).
      The version in the source (`__version__`, `.mcpb/server.json`) is not
      proof that a version is published, and an open release pull request is
      only a candidate.
    - **Verified combination:** only the main path, as recorded in #356
      (merged 2026-10-16): Linux x86_64, bash, Docker, Python 3.12,
      cubrid-mcp-server 0.5.1 from PyPI, FastMCP 4.1.0 (mcp 2.3.0, pycubrid
      1.13.0) and `cubrid/cubrid:11.4`. That run reached `health_check`
      `"ok":true` and the first query, not only tool discovery. The chat
      clients at the end of this page, other platforms and other CUBRID
      versions were not run.

---

## Step 1: Start a disposable CUBRID lab

This starts a throwaway CUBRID 11.4 server with a database named `testdb`. It
needs [Docker](https://docs.docker.com/get-started/get-docker/). The
`cubrid/cubrid:11.4` image is published for amd64 only, so other architectures
(for example Apple silicon) are unverified.

```bash
docker run -d --name cubrid-mcp-quickstart -e CUBRID_DB=testdb -p 127.0.0.1:33000:33000 cubrid/cubrid:11.4
ready=no; for i in $(seq 36); do if docker exec cubrid-mcp-quickstart csql -u dba testdb -c "SELECT 1" >/dev/null 2>&1; then ready=yes; break; fi; sleep 5; done; if [ "$ready" = yes ]; then echo "CUBRID is ready"; else echo "CUBRID did not answer within 3 minutes; see: docker logs cubrid-mcp-quickstart"; fi
```

`127.0.0.1:` publishes the broker port on this computer only. The second
command waits up to three minutes and prints `CUBRID is ready`. If `docker run`
fails because port 33000 is in use, stop whatever holds it, or run this
walkthrough on another machine, then remove the container with
`docker rm -f -v cubrid-mcp-quickstart` and start again.

The lab's administrator account is `dba` with an empty password. Only the
setup and cleanup scripts below use it, and only because this container is
local and disposable. The MCP server never uses it.

> Already have a CUBRID database? Ask its administrator for a dedicated account
> with `SELECT` on the tables the model may read, as in Step 3 and
> [SECURITY.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md),
> and use its host, port, database and credentials in Step 4. Never give the
> server a `dba` or table-owner account.

---

## Step 2: Install the server in a virtual environment

Check that `python3 --version` prints 3.11 or later, then run in an empty
folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install cubrid-mcp-server
python -c "import cubrid_mcp_server; print(cubrid_mcp_server.__version__)"
which cubrid-mcp-server
```

This installs the server and, with it, the FastMCP client library and the
pycubrid driver that the scripts below use. The last two commands print the
installed version, for example `0.5.1`, and the full path of the server's
command inside `.venv/bin`. Create every file below in
this folder, and run every command in this terminal with the virtual
environment active.

---

## Step 3: Prepare the sample table and the read-only account

This is the one-time **administrator** step. First choose a password for the
new account and keep it in this terminal only:

```bash
export MCP_READER_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(18))")
```

Then save this as `prepare_lab.py`. Running as `dba`, it creates the table
`mcp_quickstart_books` with three rows and the account `mcp_reader`, which may
only `SELECT` from that one table. Both carry a comment that marks them as this
walkthrough's. If either already exists, it stops without changing anything:

```python
"""One-time administrator setup for the quickstart lab: run it as dba, once."""

import os
import re
import sys

import pycubrid

MARK = "created by the cubrid-mcp-server quickstart"
password = os.environ.get("MCP_READER_PASSWORD", "")
if not re.fullmatch(r"[A-Za-z0-9_-]{16,}", password):
    sys.exit("Set MCP_READER_PASSWORD first (see Step 3).")

conn = pycubrid.connect(host="localhost", port=33000, database="testdb", user="dba", password="")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM db_user WHERE name = 'MCP_READER'")
user_exists = cur.fetchone()[0] > 0
cur.execute("SELECT COUNT(*) FROM db_class WHERE class_name = 'mcp_quickstart_books'")
table_exists = cur.fetchone()[0] > 0
if user_exists or table_exists:
    conn.close()
    sys.exit(
        "Stopped without changes: the user mcp_reader or the table mcp_quickstart_books "
        "already exists. Run cleanup_lab.py first, or use a fresh lab."
    )

try:
    cur.execute(
        "CREATE TABLE mcp_quickstart_books ("
        "id INT PRIMARY KEY, title VARCHAR(100), author VARCHAR(100), published INT)"
        f" COMMENT = '{MARK}'"
    )
    cur.executemany(
        "INSERT INTO mcp_quickstart_books VALUES (?, ?, ?, ?)",
        [
            (1, "The Pragmatic Programmer", "Andrew Hunt and David Thomas", 1999),
            (2, "Designing Data-Intensive Applications", "Martin Kleppmann", 2017),
            (3, "SQL Antipatterns", "Bill Karwin", 2010),
        ],
    )
    # CUBRID cannot bind a password in CREATE USER; it was checked above.
    cur.execute(f"CREATE USER mcp_reader PASSWORD '{password}' COMMENT '{MARK}'")
    cur.execute("GRANT SELECT ON mcp_quickstart_books TO mcp_reader")
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
print(
    "Created table mcp_quickstart_books (3 rows) and user mcp_reader (SELECT on that table only)."
)
```

```bash
python prepare_lab.py
```

```text
Created table mcp_quickstart_books (3 rows) and user mcp_reader (SELECT on that table only).
```

Everything is created in one transaction, so an interrupted run leaves nothing
behind. Do not grant `mcp_reader` anything else: the database account is what
really limits the model. The server's read-only checks are a second line of
defense, and even a `SELECT`-only account can read everything it was granted;
see [SECURITY.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md)
before you point the server at real data.

---

## Step 4: Register the server with the client and check the connection

A client needs to know which command starts the server and with which
environment. Save this as `mcp_config.py`. It has the same `mcpServers` shape
as the configuration file of a chat client:

```python
"""How the MCP client starts the CUBRID MCP server: the same shape as a chat client's config."""

import os
import shutil

SERVER = shutil.which("cubrid-mcp-server")
if SERVER is None:
    raise SystemExit("cubrid-mcp-server not found: activate the virtual environment from Step 2.")

PASSWORD = os.environ.get("MCP_READER_PASSWORD")
if not PASSWORD:
    raise SystemExit("MCP_READER_PASSWORD is not set in this terminal (see Step 3).")

CONFIG = {
    "mcpServers": {
        "cubrid": {
            "command": SERVER,
            # The client starts the server with exactly this environment.
            "env": {
                "CUBRID_HOST": "localhost",
                "CUBRID_PORT": "33000",
                "CUBRID_DATABASE": "testdb",
                "CUBRID_USER": "mcp_reader",
                "CUBRID_PASSWORD": PASSWORD,
                "CUBRID_MCP_READONLY": "1",
            },
        }
    }
}
```

The server does not see your terminal's variables: it gets exactly the `env`
block above. The password comes from `MCP_READER_PASSWORD`, so it is never
written into a file. `CUBRID_MCP_READONLY` is `1` by default; it is set here so
that the configuration says so.

Save this as `check_connection.py`:

```python
import asyncio

from fastmcp import Client

from mcp_config import CONFIG


async def main() -> None:
    # Entering the block starts the server over stdio and performs the MCP handshake.
    async with Client(CONFIG) as client:
        tools = await client.list_tools()
        print("Tools:", ", ".join(sorted(tool.name for tool in tools)))
        result = await client.call_tool("health_check", {})
        print("health_check:", result.content[0].text)


asyncio.run(main())
```

```bash
python check_connection.py
```

The server first writes its FastMCP banner and a `Starting MCP server` line to
standard error, and FastMCP may log an HTTP request to `pypi.org`, its own
check for a newer version. These lines only show that the process started.
Then the script prints:

```text
Tools: all_table_names, describe_table, execute_query, explain_query, filter_table_names, health_check, list_class_hierarchy, list_indexes, list_serials, schema_definitions, table_row_counts
health_check: {"ok":true,"server_version":"11.4.6.1963"}
```

The `Tools:` line means the MCP handshake worked: the client found the server's
tools. Only `"ok":true` from `health_check` means the server also connected to
CUBRID as `mcp_reader`. The server version can differ. `execute_write` is not
in the list because write mode is off.

---

## Step 5: Run your first query

Save this as `first_query.py`:

```python
import asyncio

from fastmcp import Client

from mcp_config import CONFIG


async def call(client: Client, tool: str, arguments: dict) -> None:
    result = await client.call_tool(tool, arguments, raise_on_error=False)
    status = "rejected" if result.is_error else "ok"
    print(f"--- {tool} ({status})")
    print(result.content[0].text)


async def main() -> None:
    async with Client(CONFIG) as client:
        await call(client, "all_table_names", {})
        await call(client, "describe_table", {"table_name": "mcp_quickstart_books"})
        await call(
            client,
            "execute_query",
            {"sql": "SELECT id, title, published FROM dba.mcp_quickstart_books ORDER BY id"},
        )
        # The server refuses anything but a read, whatever the model asks for.
        await call(client, "execute_query", {"sql": "DELETE FROM dba.mcp_quickstart_books"})


asyncio.run(main())
```

```bash
python first_query.py
```

```text
--- all_table_names (ok)
["dba.mcp_quickstart_books"]
--- describe_table (ok)
{"table":"dba.mcp_quickstart_books","columns":[{"name":"id","type":"INTEGER","nullable":false,"default":null,"primary_key":true},{"name":"title","type":"STRING","nullable":true,"default":null,"primary_key":false},{"name":"author","type":"STRING","nullable":true,"default":null,"primary_key":false},{"name":"published","type":"INTEGER","nullable":true,"default":null,"primary_key":false}],"primary_key":["id"],"indexes":[{"name":"pk_mcp_quickstart_books_id","unique":true,"primary_key":true,"foreign_key":false,"reverse":false,"key_count":1,"columns":[{"name":"id","order":0,"asc_desc":"ASC"}]}]}
--- execute_query (ok)
{"row_count":3,"truncated":false,"rows":[[1,"The Pragmatic Programmer",1999],[2,"Designing Data-Intensive Applications",2017],[3,"SQL Antipatterns",2010]]}
--- execute_query (rejected)
Error calling tool 'execute_query': DELETE is not permitted in read-only mode; allowed statements: DESC, DESCRIBE, SELECT, SHOW, WITH
```

These are the same calls a chat client makes for you when you ask "What tables
are in this database?" or "Show me the books": it lists the tables, inspects
one, and runs a `SELECT`. The table belongs to `dba`, so `mcp_reader` names it
`dba.mcp_quickstart_books` in SQL. The last call shows the server refusing a
`DELETE` before it reaches the database; the three rows are still there. That
refusal happens in the server, whatever the model asks for.

---

## If something fails

Tool results name only the kind of error, so that database details do not
reach the model. The cause appears in the server's error output, which this
script prints in your terminal; it can include SQL text, so do not paste it
into public issues.

| What you see | What it means | What to check |
|---|---|---|
| `cubrid-mcp-server not found: activate the virtual environment from Step 2.` | The client cannot find the server's command. | Run `source .venv/bin/activate` in this folder. A chat client needs the command's full path instead (`which cubrid-mcp-server`). |
| `MCP_READER_PASSWORD is not set in this terminal (see Step 3).` | The configuration has no password to pass on. | Run the scripts in the terminal where you set it in Step 3, or set it again with the account's password. |
| `configuration error: missing required environment variable: CUBRID_HOST` | The server started without its settings. | The client's `env` block, not your terminal, must hold the `CUBRID_*` variables. |
| `health_check: {"ok":false,"error":"DatabaseError"}` | The client reached the server, but the server could not connect to CUBRID. | The server's error output names the cause: `failed to connect to CUBRID broker` (nothing at that host and port: is the lab running?), `Failed to connect to database server, 'nosuchdb', ...` (wrong database name) or `Incorrect or missing password.` (wrong `MCP_READER_PASSWORD`). |
| `Error calling tool 'execute_query': query failed: ProgrammingError` | CUBRID rejected the statement. | The server's error output says `Unknown class "mcp_reader.mcp_quickstart_books"` (write the owner: `dba.mcp_quickstart_books`) or `SELECT is not authorized on ...` (the account has no `SELECT` grant on that table). |
| `Stopped without changes: the user mcp_reader or the table mcp_quickstart_books already exists.` | An earlier run, or someone else, already created one of them. | Run `cleanup_lab.py` below; it removes only objects this walkthrough created. |

More cases are in [Troubleshooting](TROUBLESHOOTING.md). Do not fix a failure by
using `dba`, granting more privileges or setting `CUBRID_MCP_READONLY=0`.

---

## Clean up

The client stops the server when the script ends, so nothing keeps running.
Save this as `cleanup_lab.py`. It removes `mcp_reader` and the table only if
they carry the walkthrough's comment, and keeps anything else of the same name:

```python
"""Remove the quickstart lab objects, and only those prepare_lab.py created. Run it as dba."""

import pycubrid

MARK = "created by the cubrid-mcp-server quickstart"

conn = pycubrid.connect(host="localhost", port=33000, database="testdb", user="dba", password="")
cur = conn.cursor()
try:
    cur.execute("SELECT comment FROM db_user WHERE name = 'MCP_READER'")
    user = cur.fetchone()
    cur.execute(
        "SELECT comment FROM db_class"
        " WHERE class_name = 'mcp_quickstart_books' AND owner_name = 'DBA'"
    )
    table = cur.fetchone()
    for kind, name, row, drop in [
        ("user", "mcp_reader", user, "DROP USER mcp_reader"),
        ("table", "mcp_quickstart_books", table, "DROP TABLE mcp_quickstart_books"),
    ]:
        if row is None:
            print(f"No {kind} {name}: nothing to remove.")
        elif row[0] != MARK:
            print(f"Kept {kind} {name}: it was not created by this quickstart.")
        else:
            cur.execute(drop)
            print(f"Removed {kind} {name}.")
    conn.commit()
finally:
    conn.close()
```

```bash
python cleanup_lab.py
```

```text
Removed user mcp_reader.
Removed table mcp_quickstart_books.
```

Run again, it prints `No user mcp_reader: nothing to remove.` and
`No table mcp_quickstart_books: nothing to remove.`, and `prepare_lab.py` can
then start over. To remove the whole lab, run
`docker rm -f -v cubrid-mcp-quickstart`. The image keeps its databases in an
anonymous Docker volume that belongs to this container; `-v` deletes that
volume too, and with it `testdb` and everything in it. Without `-v` the
container goes but the volume stays behind (`docker volume ls` lists it).

---

## Optional: use the same server from a chat client

A chat client takes the same three things as `mcp_config.py`: the command, its
arguments and the `env` block. These configurations were **not** run for this
walkthrough; check the client's current documentation for the file location,
and restart the client after editing it. Use the full path that
`which cubrid-mcp-server` prints, because a chat client does not activate your
virtual environment, and put the account's real password only into the
client's local configuration, never into a file you commit or share.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "/path/to/.venv/bin/cubrid-mcp-server",
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_DATABASE": "testdb",
        "CUBRID_USER": "mcp_reader",
        "CUBRID_PASSWORD": "the mcp_reader password"
      }
    }
  }
}
```

### Claude Code

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "/path/to/.venv/bin/cubrid-mcp-server",
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_DATABASE": "testdb",
        "CUBRID_USER": "mcp_reader",
        "CUBRID_PASSWORD": "the mcp_reader password"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "/path/to/.venv/bin/cubrid-mcp-server",
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_DATABASE": "testdb",
        "CUBRID_USER": "mcp_reader",
        "CUBRID_PASSWORD": "the mcp_reader password"
      }
    }
  }
}
```

Instead of a virtual environment, a client can also start the server with
[`uvx`](https://docs.astral.sh/uv/guides/tools/) (`"command": "uvx"`,
`"args": ["cubrid-mcp-server"]`) when uv is installed where the client can find
it.

---

## Next steps

- [Tools reference](TOOLS.md) — every tool, resource, and prompt
- [Configuration](https://github.com/cubrid-lab/cubrid-mcp-server#configure) — all settings, such as row and output limits, query timeout and audit logging
- [Security Model](SECURITY_MODEL.md) — what the read-only checks do and do not protect, and opt-in write mode
- [Multi-Connection](MULTI_CONNECTION.md) — serve several databases from one process
- [Troubleshooting](TROUBLESHOOTING.md) — when something does not connect
