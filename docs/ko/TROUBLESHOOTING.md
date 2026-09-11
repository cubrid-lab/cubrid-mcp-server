# 문제 해결 (한국어)

> 🌐 [TROUBLESHOOTING.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/TROUBLESHOOTING.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 경고 수준의 동기화 규칙을 따릅니다.

증상 → 원인 → 해결 순으로 정리했습니다.

## 클라이언트가 서버에 연결되지 않음

**증상:** MCP 클라이언트가 서버를 실패 또는 사용 불가로 표시함.

- **`uvx` 없음.** 클라이언트는 `uvx cubrid-mcp-server`를 실행합니다 — [uv](https://docs.astral.sh/uv/)를 설치해 클라이언트의 `PATH`에 두거나, 클라이언트 설정에 절대 경로를 사용하세요(`"command": "/home/you/.local/bin/uvx"`).
- **환경 변수 누락.** `CUBRID_HOST`, `CUBRID_USER`, `CUBRID_PASSWORD`, `CUBRID_DATABASE`는 클라이언트의 `env` 블록에 있어야 합니다 — 터미널의 `export`는 Claude Desktop 같은 GUI 앱에 보이지 않습니다.
- **설정 파일 위치.** Claude Desktop은 `~/Library/Application Support/Claude/claude_desktop_config.json`, Claude Code는 프로젝트 루트의 `.mcp.json`, Cursor는 `.cursor/mcp.json`을 읽습니다. 수정 후에는 클라이언트를 재시작하세요.

## CUBRID 연결 거부

**증상:** 도구가 연결 또는 운영 오류로 실패함.

- **포트.** 서버는 CUBRID **브로커**의 33000 포트(`CUBRID_PORT`)에 연결합니다 — 매니저 포트 1523이 아닙니다.
- **데이터베이스가 없음.** 먼저 생성하세요(`cubrid createdb`) 또는 `CUBRID_DATABASE`를 기존 데이터베이스로 지정하세요.
- **CUBRID 기동 중.** 새 CUBRID 컨테이너는 접속 수락까지 시간이 걸립니다 — 브로커가 TCP를 열고 엔진이 준비되는 사이에 틈이 있습니다. 쿼리 전에 준비를 기다리세요(docker-compose 헬스체크 등). `health_check`가 요청 시점에 연결을 확인해 줍니다.
- **자격 증명.** `CUBRID_USER`/`CUBRID_PASSWORD`가 유효해야 합니다. 로컬 docker에서는 빈 비밀번호의 `dba`가 흔합니다.

## 쿼리 권한 거부

**증상:** `SELECT` 문에서 권한 오류.

CUBRID 사용자에게 권한이 없습니다. CUBRID는 **테이블 단위**로 권한을 부여합니다 — 스키마 전체 `db.*` 부여는 없습니다. 사용자를 만들고 모델이 읽을 각 테이블에 `SELECT`를 부여하세요. [보안 모델](SECURITY_MODEL.ko.md#계층-1--데이터베이스-권한-필수) 참고.

## 읽기 전용 거부

**증상:** `execute_query`가 문장을 거부함.

설계된 동작입니다. 화이트리스트는 `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, `WITH`만 허용하며 다중 문장은 항상 거부됩니다. 정말 다른 문장이 필요하면 먼저 읽기 전용 DB 사용자를 배치한 뒤 `CUBRID_MCP_READONLY=0`을 고려하세요 — 쓰기는 화이트리스트를 끄는 대신 옵트인 쓰기 모드를 사용하세요.

## 출력이 잘린 것처럼 보임

**증상:** `execute_query` 결과가 갑자기 끝나거나 잘림 표시가 있음.

행·글자 상한은 모델의 컨텍스트 창을 보호합니다. 더 필요하면 `CUBRID_MCP_MAX_ROWS`(기본 1000) 또는 `CUBRID_MCP_MAX_CHARS`(기본 4000)를 올리거나, 쿼리를 좁히세요.

## 쿼리 타임아웃 의미

**증상:** 오래 걸리는 쿼리가 약 30초에 중단됨.

`CUBRID_MCP_QUERY_TIMEOUT`(기본 30)은 **소켓 읽기 타임아웃**이지 서버 측 문장 타임아웃이 아닙니다: 서버가 이 시간 안에 데이터를 보내지 않으면 쿼리가 중단되고 연결이 재설정됩니다. 워크로드에 맞게 조정하세요(연결별 `CUBRID_<NAME>_MCP_QUERY_TIMEOUT`도 가능).

## 로그가 안 보임 / 서버 출력이 JSON 깨진 것처럼 보임

서버는 MCP stdio를 사용합니다: `stdout`은 프로토콜 스트림이고 **모든 로그는 stderr**로 갑니다. 클라이언트의 MCP 로그 창을 보거나(직접 실행 시 `2>server.log` 리다이렉트) 확인하세요. 커스터마이즈에서 `print()`를 stdout에 절대 추가하지 마세요 — 프로토콜 스트림이 오염되어 연결이 깨집니다.

## 감사 로그가 안 남음

`CUBRID_MCP_AUDIT_LOG=1`을 설정하세요(옵트인, 기본 꺼짐). 멀티커넥션에서는 연결별로 `CUBRID_<NAME>_MCP_AUDIT_LOG`로 켭니다. 기록은 **stderr**의 JSON 라인입니다 — stdout에는 절대 나오지 않습니다. [보안 모델](SECURITY_MODEL.ko.md#계층-4--감사-로그-옵트인) 참고.
