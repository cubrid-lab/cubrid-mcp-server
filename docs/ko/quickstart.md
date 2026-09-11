# 빠른 시작 (한국어)

> 🌐 [quickstart.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/quickstart.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 커뮤니티 기여 번역과 같은 경고 수준의 동기화 규칙을 따릅니다.

CUBRID MCP 서버를 구성하고 LLM 클라이언트를 연결하는 방법을 몇 분 안에 안내합니다.

## 1. 설정

필수 환경 변수:

```bash
export CUBRID_HOST=localhost
export CUBRID_PORT=33000        # 선택, 기본값: 33000
export CUBRID_USER=readonly_user   # SELECT 권한만 가진 CUBRID 사용자 (보안 모델 참고)
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb
```

선택 설정:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CUBRID_MCP_READONLY` | `1` | 읽기 전용 SQL 화이트리스트 강제 |
| `CUBRID_MCP_MAX_CHARS` | `4000` | 쿼리 출력 최대 글자 수 |
| `CUBRID_MCP_MAX_ROWS` | `1000` | `execute_query` 최대 행 수 (초과 시 잘림) |
| `CUBRID_MCP_MAX_SQL_LENGTH` | `65536` | 제출 가능한 SQL 최대 길이 (글자 수) |
| `CUBRID_MCP_QUERY_TIMEOUT` | `30` | 문장별 소켓 읽기 타임아아웃(초). 서버가 이 시간 내에 데이터를 보내지 않으면 쿼리가 중단되고 연결이 재설정됩니다. 서버 측 문장 타임아웃이 아닙니다. |
| `CUBRID_MCP_AUDIT_LOG` | `0` | 옵트인 감사 로그. 활성화 시 실행된 문장마다 재던션-safe JSON 기록을 **stderr**에 출력 (연결별 적용: `CUBRID_<NAME>_MCP_AUDIT_LOG`) |
| `CUBRID_MCP_WRITE` | `0` | 옵트인 쓰기 모드. `1`로 설정하면 단일 DML용 `execute_write` 도구가 등록됩니다 (연결별 적용: `CUBRID_<NAME>_MCP_WRITE`). 기본은 꺼짐 |

## 2. 실행

PyPI에서 [`uvx`](https://docs.astral.sh/uv/guides/tools/)로 바로 실행:

```bash
uvx cubrid-mcp-server
```

또는 `pipx`로:

```bash
pipx run cubrid-mcp-server
```

소스에서 실행:

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
cd cubrid-mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -e .
cubrid-mcp-server
```

서버는 MCP를 stdio로 통신합니다. 터미널에서 단독 실행이 목적이 아니라, MCP 클라이언트에 서버로 등록하는 것이 사용 방법입니다.

## 3. 클라이언트 연결

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`에 추가:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "readonly_user",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

### Claude Code

프로젝트 루트의 `.mcp.json`에 추가:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "readonly_user",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

### Cursor

`.cursor/mcp.json`에 추가:

```json
{
  "mcpServers": {
    "cubrid": {
      "command": "uvx",
      "args": ["cubrid-mcp-server"],
      "env": {
        "CUBRID_HOST": "localhost",
        "CUBRID_USER": "readonly_user",
        "CUBRID_PASSWORD": "secret",
        "CUBRID_DATABASE": "mydb"
      }
    }
  }
}
```

## 4. 첫 쿼리

클라이언트가 연결되면 다음을 시도해 보세요:

1. *"이 DB에 어떤 테이블이 있어?"* — 클라이언트가 `all_table_names`를 호출합니다.
2. *"`orders` 테이블 구조 보여줘"* — `describe_table`이 컬럼·기본 키·인덱스를 반환합니다.
3. *"매출 상위 5개 상품은?"* — `execute_query`가 `SELECT`를 실행하고 잘림 처리된, 컨텍스트 안전한 출력을 반환합니다.

모델에게 테이블 삭제를 요청하면 읽기 전용 화이트리스트가 거부합니다 — 이 강제는 프롬프트가 아니라 서버에 있습니다. 전체 설계는 [보안 모델](SECURITY_MODEL.ko.md)을 참고하세요.

## 다음 단계

- [도구 참조](TOOLS.ko.md) — 모든 도구·리소스·프롬프트
- [멀티커넥션](MULTI_CONNECTION.ko.md) — 하나의 프로세스로 여러 데이터베이스 서빙
- [문제 해결](TROUBLESHOOTING.ko.md) — 연결이 안 될 때
