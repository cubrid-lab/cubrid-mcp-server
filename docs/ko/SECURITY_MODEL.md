# 보안 모델 (한국어)

> 🌐 [SECURITY_MODEL.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/SECURITY_MODEL.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 경고 수준의 동기화 규칙을 따릅니다.

`cubrid-mcp-server`는 CUBRID 데이터베이스와 MCP를 사용하는 LLM 클라이언트를 잇는 다리입니다. 모델이 보내는 모든 쿼리를 신뢰할 수 없는 입력으로 취급하세요: LLM은 파괴적 SQL을 환각할 수 있고, 악의적인 프롬프트는 서버가 노출할 의도가 없던 데이터를 빼내려 할 수 있습니다. **심층 방어**가 설계 의도입니다.

## 계층 1 — 데이터베이스 권한 (필수)

모델이 사용하길 원하는 권한**만** 가진 전용 CUBRID 사용자로 서버를 실행하세요. 코드 수준의 안전 검사기는 이것을 대신할 수 없습니다.

```sql
-- 1. 사용자 생성
CREATE USER mcp_reader PASSWORD 'replace-me';

-- 2. 노출할 테이블에만 SELECT 권한 부여.
--    CUBRID는 테이블 단위 권한 부여입니다 (스키마 전체 db.* 부여는 없음).
GRANT SELECT ON customers TO mcp_reader;
GRANT SELECT ON orders TO mcp_reader;
-- ...모델이 읽을 수 있는 각 테이블마다 반복.

-- 3. CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, GRANT, DBA 역할은 부여 금지.
```

추가 강화: 시크릿 매니저의 긴 무작위 비밀번호 사용, 정기적 로테이션, 스키마 전체가 아닌 테이블 단위 부여, MCP 서버 호스트만 접근 가능한 네트워크에 CUBRID 두기. 전체 정책은 [`SECURITY.md`](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/SECURITY.md)를 참고하세요.

## 계층 2 — 읽기 전용 SQL 화이트리스트

서버는 **기본적으로 읽기 전용**입니다. `CUBRID_MCP_READONLY=1`(기본값)이면 모든 문장이 `sqlparse`로 파싱되어 `SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, `WITH`(CTE)가 아니면 거부됩니다. 다중 문장 입력은 즉시 거부되므로 `; DROP TABLE …`이 뒤에 붙는 것도 막힙니다.

> 이 화이트리스트는 심층 방어이지 보안 경계가 아닙니다. 명백한 실수를 막는 파서 기반 가드레일일 뿐이며, 실제 강제 계층은 데이터베이스 자신입니다(계층 1).

`CUBRID_MCP_READONLY=0`은 이 계층을 끕니다 — 데이터베이스 사용자가 이미 읽기 전용이고 파서가 오판하는 문장이 필요할 때만 사용하세요. `explain_query`는 이 플래그와 무관하게 **항상** 읽기 전용입니다. `execute_query`만 이 설정을 따릅니다.

## 계층 2b — 옵트인 쓰기 모드 (`CUBRID_MCP_WRITE`)

쓰기 접근은 **기본적으로 꺼져 있습니다**. `CUBRID_MCP_WRITE=1`을 설정하면 별도의 `execute_write` 도구가 등록되며 다음으로 제한됩니다:

- **DML 전용.** 전용 화이트리스트(`ensure_write_allowed`)가 **단일** `INSERT`/`UPDATE`/`DELETE`만 허용하고, 독립 실행형 읽기·DDL·트랜잭션 제어·다중 문장 입력을 거부합니다. (단일 DML 안의 서브쿼리, 예컨대 `INSERT ... SELECT`는 합법적으로 허용됩니다.)
- **원자적 트랜잭션.** 문장은 명시적 트랜잭션에서 실행됩니다 — 성공 시 커밋, 어떤 실패든 롤백.
- **DDL은 의도적으로 미지원.** CUBRID는 DDL을 자동 커밋해서 롤백 보장이 무의미해지므로, `CREATE`/`ALTER`/`DROP`/`TRUNCATE`는 절대 허용되지 않습니다.
- **비활성 시 미등록.** 쓰기 모드가 꺼져 있으면 `execute_write`는 MCP 기능 탐색에 나타나지 않습니다 — 지켜지는 경로가 아니라 아예 닿을 수 없는 경로입니다.
- **연결별 게이팅.** 멀티커넥션에서 어떤 연결이 쓰기를 켜면 도구가 등록되지만, 매 쓰기는 **대상** 연결의 설정으로 강제됩니다 — 쓰기가 꺼진 연결은 다른 연결이 켜져 있어도 거부합니다.
- `execute_query`는 쓰기 플래그와 무관하게 **항상 읽기 전용**입니다.

## 계층 3 — 출력 제한

`execute_query`는 행을 `CUBRID_MCP_MAX_ROWS`(기본 1000)로, 렌더링된 출력을 `CUBRID_MCP_MAX_CHARS`(기본 4000)로 제한합니다. 이는 모델의 컨텍스트 창을 보호하고 한 번의 탐색 쿼리가 빼낼 수 있는 데이터량을 제한합니다. 바이너리 값은 작으면 base64로, 크면 요약됩니다(`<binary N bytes>`).

## 계층 4 — 감사 로그 (옵트인)

`CUBRID_MCP_AUDIT_LOG=1`을 설정하면 실행된 문장(`execute_query`, `explain_query`, `execute_write`)마다 **stderr**에 구조화된 JSON 기록 한 줄이 남습니다. 기본은 꺼짐이며 연결별로 적용됩니다(`CUBRID_<NAME>_MCP_AUDIT_LOG`).

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

**원본 SQL 텍스트, 바인드 파라미터, 리터럴 값은 절대 기록되지 않습니다** — 쿼리에 박힌 비밀이 감사 스트림으로 새지 않습니다.

## 로깅 규율

서버는 MCP stdio를 사용합니다: `stdout`은 JSON-RPC 프로토콜 스트림으로 예약되어 있어 **모든 로그는 `stderr`로** 출력됩니다(기본 레벨 `INFO`). LLM 클라이언트에 반환되는 오류는 **재던션 처리**됩니다 — 예외 카테고리(예: `query failed: OperationalError`)만 반환되고 전체 세부 정보는 운영자를 위해 stderr에 기록됩니다. 스키마 세부 사항, 호스트명, SQL 조각, 설정 값이 클라이언트에 노출되지 않습니다.
