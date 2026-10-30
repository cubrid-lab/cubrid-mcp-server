# 문제 해결 (한국어)

> 🌐 [TROUBLESHOOTING.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/TROUBLESHOOTING.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 경고 수준의 동기화 규칙을 따릅니다.
>
> English: [Troubleshooting](../TROUBLESHOOTING.md)

증상 → 원인 → 해결 순으로 정리했습니다.

## 오류 메시지로 찾기

도구 결과에는 데이터베이스 세부 정보가 모델에 전달되지 않도록 오류의 종류만 표시됩니다. 원인은 서버의 오류 출력(stderr)에 있습니다. 보이는 메시지 그대로 찾으세요.

| 메시지 | 나타나는 곳 | 섹션 |
|---|---|---|
| `configuration error: missing required environment variable: CUBRID_HOST`(또는 다른 `CUBRID_*` 이름) | 시작 시 서버의 오류 출력. 클라이언트는 서버를 실패로 표시 | [클라이언트가 서버에 연결되지 않음](#클라이언트가-서버에-연결되지-않음) |
| `failed to connect to CUBRID` | 모든 도구 호출 결과 | [CUBRID 연결 거부](#cubrid-연결-거부) |
| `health_check` → `{"ok":false,"error":"DatabaseError"}` | `health_check` 결과 | [CUBRID 연결 거부](#cubrid-연결-거부) |
| `query failed: ProgrammingError` | `execute_query` 결과 | [쿼리 권한 거부](#쿼리-권한-거부) |
| `query failed: OperationalError` | `execute_query` 결과 | [CUBRID 연결 거부](#cubrid-연결-거부) |
| `query exceeded timeout of 30s (CUBRID_MCP_QUERY_TIMEOUT)` | `execute_query` 결과 | [쿼리 타임아웃 의미](#쿼리-타임아웃-의미) |
| `DELETE is not permitted in read-only mode; allowed statements: ...`(또는 다른 키워드) | `execute_query` 결과 | [읽기 전용 거부](#읽기-전용-거부) |
| 메시지 없음: 서버는 연결됨으로 표시되지만 모든 도구가 실패함 | MCP 클라이언트 | [서버는 연결됨으로 표시되지만 모든 도구가 실패함](#서버는-연결됨으로-표시되지만-모든-도구가-실패함) |

[빠른 시작의 실패 표](quickstart.md#문제가-생기면)에도 같은 메시지와 서버 오류 출력에 나오는 원인이 정리되어 있습니다.

## 클라이언트가 서버에 연결되지 않음

**증상:** MCP 클라이언트가 서버를 실패 또는 사용 불가로 표시함.

- **`uvx` 없음.** 클라이언트는 `uvx cubrid-mcp-server`를 실행합니다 — [uv](https://docs.astral.sh/uv/)를 설치해 클라이언트의 `PATH`에 두거나, 클라이언트 설정에 절대 경로를 사용하세요(`"command": "/home/you/.local/bin/uvx"`).
- **환경 변수 누락.** `CUBRID_HOST`, `CUBRID_USER`, `CUBRID_PASSWORD`, `CUBRID_DATABASE`는 클라이언트의 `env` 블록에 있어야 합니다 — 터미널의 `export`는 Claude Desktop 같은 GUI 앱에 보이지 않습니다.
- **설정 파일 위치.** Claude Desktop은 `~/Library/Application Support/Claude/claude_desktop_config.json`, Claude Code는 프로젝트 루트의 `.mcp.json`, Cursor는 `.cursor/mcp.json`을 읽습니다. 수정 후에는 클라이언트를 재시작하세요.

## 서버는 연결됨으로 표시되지만 모든 도구가 실패함

**증상:** MCP 클라이언트에 서버와 도구가 표시되지만 모든 도구 호출이 실패함(예: `failed to connect to CUBRID`).

서버는 데이터베이스에 접속하지 않고 시작하며, CUBRID 연결은 첫 도구 호출 때 엽니다. 따라서 서버가 실행 중이라는 것은 설정을 읽었다는 뜻일 뿐, CUBRID에 접속할 수 있거나 자격 증명이 유효하다는 뜻은 아닙니다. `health_check`를 호출하고 서버의 오류 출력을 확인한 뒤 [CUBRID 연결 거부](#cubrid-연결-거부)를 차례로 점검하세요.

## CUBRID 연결 거부

**증상:** 도구가 연결 또는 운영 오류로 실패함.

- **포트.** 서버는 CUBRID **브로커**의 33000 포트(`CUBRID_PORT`)에 연결합니다 — 매니저 포트 1523이 아닙니다.
- **데이터베이스가 없음.** 먼저 생성하세요(`cubrid createdb`) 또는 `CUBRID_DATABASE`를 기존 데이터베이스로 지정하세요.
- **CUBRID 기동 중.** 새 CUBRID 컨테이너는 접속 수락까지 시간이 걸립니다 — 브로커가 TCP를 열고 엔진이 준비되는 사이에 틈이 있습니다. 쿼리 전에 준비를 기다리세요(docker-compose 헬스체크 등). `health_check`가 요청 시점에 연결을 확인해 줍니다.
- **자격 증명.** 서버 전용 읽기 전용 계정의 `CUBRID_USER`/`CUBRID_PASSWORD`가 유효해야 합니다. 로컬 docker 실습 환경에서 빈 비밀번호의 `dba`는 이미지의 관리자 계정입니다. 그 계정을 만들 때만 사용하고(빠른 시작 [3단계](quickstart.md#3단계-예제-테이블과-읽기-전용-계정-준비)), 서버의 `CUBRID_USER`로는 절대 사용하지 마세요.
- **느리거나 먼 브로커.** 연결 시도는 `CUBRID_MCP_CONNECT_TIMEOUT`초(기본 10) 후 포기합니다. 느린 링크로 접속하는 브로커라면 늘리세요(연결별: `CUBRID_<NAME>_MCP_CONNECT_TIMEOUT`).

## 쿼리 권한 거부

**증상:** `SELECT` 문에서 권한 오류.

CUBRID 사용자에게 권한이 없습니다. CUBRID는 **테이블 단위**로 권한을 부여합니다 — 스키마 전체 `db.*` 부여는 없습니다. 사용자를 만들고 모델이 읽을 각 테이블에 `SELECT`를 부여하세요. [보안 모델](SECURITY_MODEL.md#계층-1--데이터베이스-권한-필수) 참고.

## 읽기 전용 거부

**증상:** `execute_query`가 문장을 거부함.

설계된 동작입니다. `dba` 사용, 권한 추가 부여, `CUBRID_MCP_READONLY=0` 설정으로 거부를 해결하지 마세요. 화이트리스트는 `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `WITH`만 허용하며 다중 문장은 항상 거부됩니다. CUBRID에는 `EXPLAIN` 문이 없으므로 실행 계획은 `explain_query` 도구를 사용하세요. 쓰기는 화이트리스트를 끄는 대신 [옵트인 쓰기 모드](SECURITY_MODEL.md#계층-2b--옵트인-쓰기-모드-cubrid_mcp_write)를 사용하세요. `CUBRID_MCP_READONLY=0`은 [보안 모델](SECURITY_MODEL.md#계층-2--읽기-전용-sql-화이트리스트)이 설명하는 좁은 경우에만 사용합니다. 데이터베이스 사용자가 이미 읽기 전용이고 파서가 오판하는 결과 집합 문장이 필요할 때입니다.

## 출력이 잘린 것처럼 보임

**증상:** `execute_query` 결과가 갑자기 끝나거나 잘림 표시가 있음.

행·글자 상한은 모델의 컨텍스트 창을 보호합니다. 더 필요하면 `CUBRID_MCP_MAX_ROWS`(기본 1000) 또는 `CUBRID_MCP_MAX_CHARS`(기본 4000)를 올리거나, 쿼리를 좁히세요.

## 쿼리 타임아웃 의미

**증상:** 오래 걸리는 쿼리가 약 30초에 중단됨.

`CUBRID_MCP_QUERY_TIMEOUT`(기본 30)은 **소켓 읽기 타임아웃**이지 서버 측 문장 타임아웃이 아닙니다: 서버가 이 시간 안에 데이터를 보내지 않으면 쿼리가 중단되고 연결이 재설정됩니다. 워크로드에 맞게 조정하세요(연결별 `CUBRID_<NAME>_MCP_QUERY_TIMEOUT`도 가능).

## 로그가 안 보임 / 서버 출력이 JSON 깨진 것처럼 보임

서버는 MCP stdio를 사용합니다: `stdout`은 프로토콜 스트림이고 **모든 로그는 stderr**로 갑니다. 클라이언트의 MCP 로그 창을 보거나(직접 실행 시 `2>server.log` 리다이렉트) 확인하세요. 커스터마이즈에서 `print()`를 stdout에 절대 추가하지 마세요 — 프로토콜 스트림이 오염되어 연결이 깨집니다.

## 감사 로그가 안 남음

`CUBRID_MCP_AUDIT_LOG=1`을 설정하세요(옵트인, 기본 꺼짐). 멀티커넥션에서는 연결별로 `CUBRID_<NAME>_MCP_AUDIT_LOG`로 켭니다. 기록은 **stderr**의 JSON 라인입니다 — stdout에는 절대 나오지 않습니다. [보안 모델](SECURITY_MODEL.md#계층-4--감사-로그-옵트인) 참고.
