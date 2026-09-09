# cubrid-mcp-server (한국어)

> 영어 원문: [README.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/README.md)

[CUBRID](https://www.cubrid.org/) 데이터베이스를 위한 [Model Context Protocol](https://modelcontextprotocol.io) 서버. LLM 클라이언트가 순수 Python 드라이버 [pycubrid](https://pypi.org/project/pycubrid/)를 통해 스키마를 안전하게 조회하고 **읽기 전용** 쿼리를 실행할 수 있습니다.

## 기능

| 도구 | 설명 |
|------|------|
| `all_table_names` | 데이터베이스의 모든 사용자 테이블 목록 |
| `filter_table_names` | 테이블 이름 부분 문자열 검색 |
| `schema_definitions` | 컬럼 타입, NULL 허용 여부, 기본값, 기본 키 정보 |
| `describe_table` | 컬럼·기본 키·인덱스를 한 번에 조회 |
| `list_indexes` | 테이블의 인덱스 (키 컬럼 및 플래그 포함) |
| `explain_query` | `SELECT`/`WITH` 실행 계획 (CUBRID `SHOW TRACE`) |
| `table_row_counts` | 한 개 이상 테이블의 `COUNT(*)` |
| `list_serials` | CUBRID `SERIAL` 시퀀스 (현재값 및 범위) |
| `list_class_hierarchy` | CUBRID `CLASS` 상속 관계 |
| `execute_query` | 읽기 전용 SQL 실행 (출력 자동 잘림) |
| `health_check` | 데이터베이스 연결 상태 확인 |
| `execute_write` | 단일 `INSERT`/`UPDATE`/`DELETE`를 원자적 트랜잭션으로 실행 (**옵트인 쓰기 모드 활성화 시에만 등록**) |

### 리소스 (Resources)

스키마 메타데이터는 읽기 전용 [MCP Resources](https://modelcontextprotocol.io/docs/concepts/resources)로도 노출됩니다. 리소스는 도구와 동일한 읽기 전용 카탈로그 쿼리를 재사용하므로 데이터 접근 범위는 늘어나지 않습니다.

| 리소스 URI | 설명 |
|--------------|------|
| `cubrid://schema` | 전체 스키마 인덱스 (모든 사용자 테이블과 개별 리소스 URI) |
| `cubrid://schema/{table}` | 테이블별 메타데이터 (컬럼, 기본 키, 인덱스) — `describe_table`과 동일 |

모두 `application/json`을 반환합니다.

### 프롬프트 (Prompts)

일반적인 조회 작업을 안내하는 **MCP 프롬프트 템플릿**도 제공합니다. 프롬프트는 **안내 전용**입니다 — 어떤 읽기 전용 도구를 어떤 순서로 호출할지 알려줄 뿐, 데이터베이스에 접근하거나 SQL을 실행하지 않으며, 전달된 인자는 신뢰할 수 없는 데이터로 취급됩니다.

| 프롬프트 | 인자 | 설명 |
|--------|------|------|
| `summarize_table` | `table` | 테이블 설명 후 제한된 읽기 전용 쿼리로 샘플 조회 |
| `explain_query` | `sql` | `SELECT`/`WITH` 실행 계획 해석 |
| `inspect_schema` | (없음) | 읽기 전용 도구들로 전체 스키마 개요 작성 |
| `find_index_candidates` | `table` | 테이블의 인덱스 커버리지 검토 |

## 빠른 시작

### 설정

필수 환경 변수:

```bash
export CUBRID_HOST=localhost
export CUBRID_PORT=33000        # 선택, 기본값: 33000
export CUBRID_USER=readonly_user   # SELECT 권한만 가진 CUBRID 사용자 (보안 참고)
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
| `CUBRID_MCP_QUERY_TIMEOUT` | `30` | 문장별 소켓 읽기 타임아웃 (초). 서버가 이 시간 내에 데이터를 보내지 않으면 쿼리가 중단되고 연결이 재설정됩니다. 서버 측 문장 타임아웃이 아닙니다. |
| `CUBRID_MCP_AUDIT_LOG` | `0` | 옵트인 감사 로그. 활성화 시 실행된 문장마다 재던션-safe JSON 기록을 **stderr**에 출력 (연결별 적용: `CUBRID_<NAME>_MCP_AUDIT_LOG`) |
| `CUBRID_MCP_WRITE` | `0` | 옵트인 쓰기 모드. `1`로 설정하면 단일 DML용 `execute_write` 도구가 등록됩니다 (연결별 적용: `CUBRID_<NAME>_MCP_WRITE`). 기본은 꺼짐 |

### 다중 연결

기본적으로 `CUBRID_*` 변수만으로 `default`라는 이름의 단일 연결이 구성됩니다. `CUBRID_CONNECTIONS`(쉼표 구분)에 추가 연결 이름을 나열하고 각각 `CUBRID_<NAME>_*` 변수를 제공하면 하나의 프로세스에서 여러 CUBRID 데이터베이스를 서빙할 수 있습니다. 모든 도구는 선택적 `connection` 인자를 받으며, 생략하면 `default` 연결을 사용하므로 기존 설정은 그대로 유지됩니다.

```bash
# 기본 연결 (기존과 동일)
export CUBRID_HOST=localhost
export CUBRID_USER=readonly_user
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb

# 추가 이름 있는 연결들
export CUBRID_CONNECTIONS=reporting,analytics

export CUBRID_REPORTING_HOST=reporting-db
export CUBRID_REPORTING_USER=readonly_user
export CUBRID_REPORTING_PASSWORD=secret
export CUBRID_REPORTING_DATABASE=reports
export CUBRID_REPORTING_MCP_MAX_ROWS=500   # 연결별 선택 튜닝
```

참고: 연결 이름은 `[A-Za-z0-9_]+` 형식이며 대소문자를 구분하지 않습니다. `default`는 예약된 이름입니다. 이름 있는 연결은 기본 변수를 상속하지 않으므로 모든 필드를 지정해야 합니다. 연결별로 읽기 전용 강제가 독립적으로 적용됩니다.

### 실행

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

## MCP 클라이언트 연동

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

## 보안

서버는 기본적으로 **읽기 전용**입니다. 코드 수준의 SQL 화이트리스트는 `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, `WITH` 문만 허용하며, 다중 문장 쿼리는 거부됩니다.

> **SQL 화이트리스트는 심층 방어이지 보안 경계가 아닙니다.** 명백한 실수를 막는 파서 기반 가드레일일 뿐, 실제 강제 계층은 데이터베이스 자체입니다. 모델이 읽을 수 있는 테이블에 **SELECT 권한만 가진 CUBRID 사용자**로 서버를 실행하세요. 자세한 내용은 [`SECURITY.md`](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md)를 참고하세요.

### 쓰기 모드 (옵트인)

쓰기 접근은 **기본적으로 비활성화**됩니다. `CUBRID_MCP_WRITE=1`을 설정하면 단일 `INSERT`/`UPDATE`/`DELETE` 문을 명시적 트랜잭션(성공 시 커밋, 오류 시 롤백)으로 실행하는 `execute_write` 도구가 등록됩니다. 쓰기 모드가 꺼져 있으면 도구 자체가 등록되지 않아 MCP 기능 탐색에 쓰기 경로가 노출되지 않습니다.

제약 사항:

- **단일 DML 문만 허용.** 독립 실행형 읽기, DDL(`CREATE`/`ALTER`/`DROP`/`TRUNCATE`), 트랜잭션 제어, 다중 문장 입력은 거부됩니다. (단일 DML 안의 서브쿼리는 합법적으로 허용됩니다.)
- **DDL은 의도적으로 미지원.** CUBRID는 DDL을 자동 커밋하므로 롤백 보장이 무의미해집니다.
- **쓰기 모드는 연결 단위.** 읽기 도구와 동일한 `connection` 인자를 받으며, 대상 연결의 설정으로 강제됩니다.
- `execute_query`는 쓰기 모드 플래그와 무관하게 **항상 읽기 전용**입니다.

## 로깅

서버는 MCP **stdio 전송**을 사용하며 `stdout`은 JSON-RPC 프로토콜 스트림으로 예약됩니다. **모든 로그는 `stderr`로 출력**되며, 로그 레벨 기본값은 `INFO`입니다. LLM 클라이언트에 반환되는 오류는 **재던션 처리**됩니다 — 예외 카테고리(예: `query failed: OperationalError`)만 반환되고 전체 세부 정보는 운영자를 위해 stderr에 기록됩니다. 스키마 세부 사항, 호스트명, SQL 조각, 설정 값이 클라이언트에 노출되지 않습니다.

### 감사 로깅 (옵트인)

`CUBRID_MCP_AUDIT_LOG=1`을 설정하면 실행된 모든 문장(`execute_query`, `explain_query`, `execute_write`)에 대해 **stderr**에 구조화된 JSON 한 줄이 기록됩니다. 기본은 꺼짐이며 연결별로 적용됩니다.

| 필드 | 설명 |
|-------|------|
| `tool` | 문장을 실행한 MCP 도구 |
| `status` | `ok` 또는 `error` |
| `category` | 선행 SQL 키워드만 (예: `SELECT`, `WITH`) — 전체 문장은 절대 기록 안 함 |
| `identifiers` | `FROM`/`JOIN` 뒤에서 식별자 정규식으로 추출한 테이블 이름. 식별자가 아닌 것(값, 리터럴, 표현식)은 버려짐 |
| `sql_length` | 제출된 SQL의 글자 수 |
| `row_count`, `truncated` | 결과 크기 및 잘림 여부 (성공 시만) |
| `duration_ms` | 호출 소요 시간 (정수 밀리초) |
| `error_type` | 실패 시 예외 클래스 이름만 |

**원본 SQL 텍스트, 바인드 파라미터, 리터럴 값은 절대 기록되지 않습니다.**

## 개발

```bash
git clone https://github.com/cubrid-lab/cubrid-mcp-server.git
cd cubrid-mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 린트 및 타입 검사
ruff check .
mypy cubrid_mcp_server

# 단위 테스트
pytest -m "not integration"

# 통합 테스트 (실행 중인 CUBRID 필요)
export CUBRID_HOST=localhost CUBRID_USER=dba CUBRID_PASSWORD="" CUBRID_DATABASE=demodb
pytest -m integration
```

## 고지

> 이 프로젝트는 CUBRID 개발자 도구를 위한 독립 오픈소스 이니셔티브인 [CUBRID Lab](https://github.com/cubrid-lab)의 일부이며, CUBRID Corporation 또는 공식 CUBRID 프로젝트와 제휴, 후원, 보증 관계가 없습니다.

## 라이선스

MIT ([`LICENSE`](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/LICENSE) 참고).
