# 빠른 시작 (한국어)

> 🌐 [quickstart.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/quickstart.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 커뮤니티 기여 번역과 같은 경고 수준의 동기화 규칙을 따릅니다.

이 안내는 MCP 클라이언트 하나를 작은 예제 데이터베이스에 연결해 데이터를 읽는 과정을 다룹니다.
모델에게는 테이블 하나에 대한 읽기 권한만 줍니다.

세 가지 구성 요소가 함께 동작합니다.

- **CUBRID**는 데이터베이스 서버입니다. 데이터를 저장하며 이미 실행 중이어야 합니다. 이
  패키지를 설치해도 CUBRID는 설치되지 않습니다.
- **cubrid-mcp-server**(이 프로젝트)는 MCP 클라이언트를 그 데이터에 연결합니다.
  `all_table_names`, `execute_query` 같은 *도구*를 제공하며, 여러분이 지정한 계정으로 CUBRID에
  접속합니다.
- **MCP 클라이언트**는 서버를 시작하고 도구 목록을 받아 도구를 호출합니다. AI 채팅
  애플리케이션일 수도 있고, 이 안내에서처럼 짧은 Python 스크립트일 수도 있습니다.

서버는 **stdio**로 MCP 통신을 합니다. 클라이언트가 서버를 자식 프로세스로 시작하고 표준 입력과
표준 출력으로 대화합니다. 웹 서버가 아니며 URL도 없습니다. 터미널에서 직접 시작하면 배너를 출력한
뒤 입력으로 들어올 MCP 메시지를 기다립니다. 멈춘 것도 아니고, 데이터베이스에 연결되었다는 뜻도
아닙니다. Ctrl+C로 멈추세요.

아래 기본 경로는 Linux(x86_64), bash, Docker, Python 3.12, PyPI의 cubrid-mcp-server 0.5.1과 함께
설치되는 FastMCP 4.1.0 클라이언트로 `cubrid/cubrid:11.4` 이미지에 대해 그대로 실행해 확인했습니다.
처음부터 끝까지 같은 이름을 사용합니다. 데이터베이스는 `testdb`, 테이블은
`dba.mcp_quickstart_books`, 계정은 `mcp_reader`입니다.

---

## 1단계: 일회용 CUBRID 실습 환경 시작

`testdb` 데이터베이스가 있는 일회용 CUBRID 11.4 서버를 시작합니다.
[Docker](https://docs.docker.com/get-started/get-docker/)가 필요합니다. `cubrid/cubrid:11.4`
이미지는 amd64용으로만 배포되므로 다른 아키텍처(예: Apple silicon)는 검증하지 않았습니다.

```bash
docker run -d --name cubrid-mcp-quickstart -e CUBRID_DB=testdb -p 127.0.0.1:33000:33000 cubrid/cubrid:11.4
ready=no; for i in $(seq 36); do if docker exec cubrid-mcp-quickstart csql -u dba testdb -c "SELECT 1" >/dev/null 2>&1; then ready=yes; break; fi; sleep 5; done; if [ "$ready" = yes ]; then echo "CUBRID is ready"; else echo "CUBRID did not answer within 3 minutes; see: docker logs cubrid-mcp-quickstart"; fi
```

`127.0.0.1:`은 브로커 포트를 이 컴퓨터에만 엽니다. 두 번째 명령은 최대 3분을 기다린 뒤
`CUBRID is ready`를 출력합니다. 포트 33000이 이미 사용 중이라 `docker run`이 실패하면 그 포트를
쓰는 프로그램을 멈추거나 다른 머신에서 진행하고, `docker rm -f -v cubrid-mcp-quickstart`로
컨테이너를 지운 뒤 다시 시작하세요.

실습 환경의 관리자 계정은 비밀번호가 비어 있는 `dba`입니다. 아래의 준비와 정리 스크립트만 이
계정을 쓰며, 이 컨테이너가 로컬 일회용이기 때문에 허용됩니다. MCP 서버는 이 계정을 절대 쓰지
않습니다.

> 이미 CUBRID 데이터베이스가 있나요? 관리자에게 3단계와
> [SECURITY.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md)처럼 모델이
> 읽어도 되는 테이블에만 `SELECT` 권한이 있는 전용 계정을 요청하고, 4단계에서 그 호스트, 포트,
> 데이터베이스, 자격 증명을 사용하세요. 서버에 `dba`나 테이블 소유자 계정을 주지 마세요.

---

## 2단계: 가상 환경에 서버 설치

`python3 --version`이 3.11 이상을 출력하는지 확인한 뒤, 빈 폴더에서 다음을 실행하세요.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install cubrid-mcp-server
python -c "import cubrid_mcp_server; print(cubrid_mcp_server.__version__)"
which cubrid-mcp-server
```

서버와 함께, 아래 스크립트가 사용하는 FastMCP 클라이언트 라이브러리와 pycubrid 드라이버가
설치됩니다. 마지막 두 명령은 설치된 버전(예: `0.5.1`)과 `.venv/bin` 안에 있는 서버 명령의 전체
경로를 출력합니다. 아래의 모든 파일은 이 폴더에 만들고, 모든 명령은 가상 환경이 활성화된 이
터미널에서 실행하세요.

---

## 3단계: 예제 테이블과 읽기 전용 계정 준비

한 번만 하는 **관리자** 단계입니다. 먼저 새 계정의 비밀번호를 정해 이 터미널에만 보관하세요.

```bash
export MCP_READER_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(18))")
```

그런 다음 다음 내용을 `prepare_lab.py`로 저장하세요. `dba`로 실행되어 세 행이 있는 테이블
`mcp_quickstart_books`와, 그 테이블 하나에서만 `SELECT`할 수 있는 계정 `mcp_reader`를 만듭니다.
둘 다 이 안내가 만들었음을 표시하는 주석을 가집니다. 둘 중 하나라도 이미 있으면 아무것도 바꾸지
않고 멈춥니다.

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

모든 것이 한 트랜잭션에서 만들어지므로 실행이 중단되면 아무것도 남지 않습니다. `mcp_reader`에
다른 권한을 주지 마세요. 모델을 실제로 제한하는 것은 데이터베이스 계정입니다. 서버의 읽기 전용
검사는 두 번째 방어선이며, `SELECT`만 가능한 계정이라도 권한을 받은 데이터는 모두 읽을 수
있습니다. 실제 데이터에 서버를 연결하기 전에
[SECURITY.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md)를 읽으세요.

---

## 4단계: 클라이언트에 서버 등록하고 연결 확인

클라이언트는 어떤 명령으로, 어떤 환경으로 서버를 시작할지 알아야 합니다. 다음을
`mcp_config.py`로 저장하세요. 채팅 클라이언트 설정 파일과 같은 `mcpServers` 형태입니다.

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

서버는 터미널의 변수를 보지 못하며, 위의 `env` 블록만 받습니다. 비밀번호는 `MCP_READER_PASSWORD`에서
가져오므로 파일에 기록되지 않습니다. `CUBRID_MCP_READONLY`의 기본값은 `1`이며, 설정이 그 사실을
드러내도록 여기서 명시합니다.

다음을 `check_connection.py`로 저장하세요.

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

서버는 먼저 FastMCP 배너와 `Starting MCP server` 줄을 표준 오류로 출력하며, FastMCP가 새 버전을
확인하려고 `pypi.org`에 보낸 HTTP 요청을 기록할 수도 있습니다. 이 줄들은 프로세스가 시작되었다는
것만 보여 줍니다. 그다음 스크립트가 다음을 출력합니다.

```text
Tools: all_table_names, describe_table, execute_query, explain_query, filter_table_names, health_check, list_class_hierarchy, list_indexes, list_serials, schema_definitions, table_row_counts
health_check: {"ok":true,"server_version":"11.4.6.1963"}
```

`Tools:` 줄은 MCP 핸드셰이크가 성공해 클라이언트가 서버의 도구를 찾았다는 뜻입니다.
`health_check`의 `"ok":true`만이 서버가 `mcp_reader`로 CUBRID에도 연결되었다는 뜻입니다. 서버
버전은 다를 수 있습니다. 쓰기 모드가 꺼져 있으므로 `execute_write`는 목록에 없습니다.

---

## 5단계: 첫 쿼리 실행

다음을 `first_query.py`로 저장하세요.

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

채팅 클라이언트에 "이 데이터베이스에 어떤 테이블이 있어?"나 "책 목록을 보여 줘"라고 물으면
클라이언트가 대신 하는 호출과 같습니다. 테이블 목록을 받고, 테이블 하나를 살펴본 뒤 `SELECT`를
실행합니다. 테이블의 소유자가 `dba`이므로 `mcp_reader`는 SQL에서 `dba.mcp_quickstart_books`로
씁니다. 마지막 호출은 서버가 `DELETE`를 데이터베이스에 보내기 전에 거부하는 모습을 보여 주며, 세
행은 그대로 남아 있습니다. 이 거부는 모델이 무엇을 요청하든 서버에서 일어납니다.

---

## 문제가 생기면

도구 결과에는 데이터베이스의 세부 정보가 모델에 전달되지 않도록 오류의 종류만 나옵니다. 원인은
서버의 오류 출력에 나오며, 이 스크립트는 그것을 터미널에 출력합니다. 오류 출력에는 SQL 텍스트가
포함될 수 있으므로 공개 이슈에 붙여 넣지 마세요.

| 보이는 내용 | 의미 | 확인할 것 |
|---|---|---|
| `cubrid-mcp-server not found: activate the virtual environment from Step 2.` | 클라이언트가 서버 명령을 찾지 못합니다. | 이 폴더에서 `source .venv/bin/activate`를 실행하세요. 채팅 클라이언트에는 대신 명령의 전체 경로(`which cubrid-mcp-server`)가 필요합니다. |
| `MCP_READER_PASSWORD is not set in this terminal (see Step 3).` | 설정이 전달할 비밀번호가 없습니다. | 3단계에서 비밀번호를 설정한 터미널에서 스크립트를 실행하거나, 계정의 비밀번호로 다시 설정하세요. |
| `configuration error: missing required environment variable: CUBRID_HOST` | 서버가 설정 없이 시작되었습니다. | `CUBRID_*` 변수는 터미널이 아니라 클라이언트의 `env` 블록에 있어야 합니다. |
| `health_check: {"ok":false,"error":"DatabaseError"}` | 클라이언트는 서버에 닿았지만 서버가 CUBRID에 연결하지 못했습니다. | 서버의 오류 출력이 원인을 알려 줍니다. `failed to connect to CUBRID broker`(그 호스트와 포트에 아무것도 없음: 실습 환경이 실행 중인가요?), `Failed to connect to database server, 'nosuchdb', ...`(잘못된 데이터베이스 이름), `Incorrect or missing password.`(잘못된 `MCP_READER_PASSWORD`). |
| `Error calling tool 'execute_query': query failed: ProgrammingError` | CUBRID가 문장을 거부했습니다. | 서버의 오류 출력이 `Unknown class "mcp_reader.mcp_quickstart_books"`(소유자를 쓰세요: `dba.mcp_quickstart_books`)나 `SELECT is not authorized on ...`(계정에 그 테이블의 `SELECT` 권한이 없음)라고 알려 줍니다. |
| `Stopped without changes: the user mcp_reader or the table mcp_quickstart_books already exists.` | 이전 실행이나 다른 사람이 이미 둘 중 하나를 만들었습니다. | 아래의 `cleanup_lab.py`를 실행하세요. 이 안내가 만든 객체만 지웁니다. |

더 많은 사례는 [문제 해결](TROUBLESHOOTING.md)에 있습니다. `dba`를 쓰거나, 권한을 더 주거나,
`CUBRID_MCP_READONLY=0`을 설정해서 실패를 해결하지 마세요.

---

## 정리

스크립트가 끝나면 클라이언트가 서버를 멈추므로 계속 실행되는 것은 없습니다. 다음을
`cleanup_lab.py`로 저장하세요. `mcp_reader`와 테이블에 이 안내의 주석이 있을 때만 지우고, 같은
이름의 다른 객체는 그대로 둡니다.

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

다시 실행하면 `No user mcp_reader: nothing to remove.`와
`No table mcp_quickstart_books: nothing to remove.`를 출력하며, 그다음 `prepare_lab.py`로 처음부터
다시 시작할 수 있습니다. 실습 환경 전체를 지우려면 `docker rm -f -v cubrid-mcp-quickstart`를
실행하세요. 이미지는 데이터베이스를 이 컨테이너에 속한 익명 Docker 볼륨에 보관합니다. `-v`가 그
볼륨도 지우므로 `testdb`와 그 안의 모든 데이터가 함께 지워집니다. `-v` 없이 지우면 컨테이너만
지워지고 볼륨은 남습니다(`docker volume ls`에 보입니다).

---

## 선택: 채팅 클라이언트에서 같은 서버 사용

채팅 클라이언트도 `mcp_config.py`와 같은 세 가지, 즉 명령, 인수, `env` 블록을 받습니다. 아래
설정은 이 안내에서 실행해 보지 **않았습니다**. 파일 위치는 클라이언트의 최신 문서에서 확인하고,
수정한 뒤 클라이언트를 다시 시작하세요. 채팅 클라이언트는 가상 환경을 활성화하지 않으므로
`which cubrid-mcp-server`가 출력하는 전체 경로를 사용하세요. 계정의 실제 비밀번호는 클라이언트의
로컬 설정에만 넣고, 커밋하거나 공유하는 파일에는 절대 넣지 마세요.

### Claude Desktop

macOS에서는 `~/Library/Application Support/Claude/claude_desktop_config.json`에 추가합니다.

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

프로젝트 루트의 `.mcp.json`에 추가합니다.

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

`.cursor/mcp.json`에 추가합니다.

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

가상 환경 대신, 클라이언트가 찾을 수 있는 위치에 uv가 설치되어 있다면
[`uvx`](https://docs.astral.sh/uv/guides/tools/)로 서버를 시작할 수도 있습니다(`"command": "uvx"`,
`"args": ["cubrid-mcp-server"]`).

---

## 다음 단계

- [도구 레퍼런스](TOOLS.md) — 모든 도구, 리소스, 프롬프트
- [설정](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/README.ko.md#설정) — 행과 출력 제한, 쿼리 타임아웃, 감사 로그 같은 모든 설정
- [보안 모델](SECURITY_MODEL.md) — 읽기 전용 검사가 보호하는 것과 보호하지 않는 것, 선택적 쓰기 모드
- [다중 연결](MULTI_CONNECTION.md) — 한 프로세스에서 여러 데이터베이스 제공
- [문제 해결](TROUBLESHOOTING.md) — 연결되지 않을 때
