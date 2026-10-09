# 도구 참조 (한국어)

> 🌐 [TOOLS.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/TOOLS.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 경고 수준의 동기화 규칙을 따릅니다.

`cubrid-mcp-server`는 MCP **도구**·**리소스**·**프롬프트**로 기능을 노출합니다. 모든 도구는 선택적 `connection` 인자를 받으며( [멀티커넥션](MULTI_CONNECTION.ko.md) 참고), 생략하면 `default` 연결을 대상으로 합니다.

## 도구

### 스키마 조회

#### `all_table_names(connection=None)`

데이터베이스의 모든 사용자 테이블을 나열합니다. 시스템·카탈로그 테이블은 제외됩니다.

#### `filter_table_names(substring, connection=None)`

테이블 이름에 대한 대소문자 구분 없는 부분 문자열 검색. 스키마가 클 때 `all_table_names` 대신 사용하세요.

#### `schema_definitions(table_name, connection=None)`

한 테이블의 컬럼 수준 메타데이터: 컬럼 이름·타입·NULL 허용 여부·기본값·기본 키 포함 여부.

#### `describe_table(table_name, connection=None)`

한 테이블의 전체 메타데이터를 한 번의 호출로 — 컬럼, 기본 키, 인덱스. `cubrid://schema/{table}` 리소스와 동일합니다.

`primary_key`는 키 컬럼을 **선언된 기본 키 순서**(`PRIMARY KEY (...)`에 적은 순서, 즉 CUBRID `db_index_key.key_order`)로 나열하며, `indexes`의 기본 키 항목과 일치합니다. `columns`는 테이블 정의 순서를 유지하고 컬럼별 불리언 `primary_key` 플래그를 가집니다. 기본 키가 없는 테이블은 `"primary_key": []`를 반환합니다.

#### `list_indexes(table_name, connection=None)`

테이블에 정의된 인덱스와 인덱스된 키 컬럼·플래그(유니크, 리버스).

#### `list_class_hierarchy(table_name=None, connection=None)`

CUBRID `CLASS` 상속 관계 — 어느 테이블이 어느 테이블을 상속하는지. `table_name`을 생략하면 모든 클래스를, 전달하면 해당 테이블의 직접 상위 클래스만 반환합니다. `table_name`은 다른 스키마 도구와 같은 방식으로 해석됩니다. 사용자 테이블과 대소문자 구분 없이 매칭하며, 알 수 없는 테이블(시스템 클래스와 뷰 포함)은 빈 리스트 대신 `unknown table` 오류를 발생시킵니다.

### 쿼리

#### `execute_query(sql, connection=None)`

**읽기 전용** SQL(`SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `WITH`) 중 결과 집합을 반환하는 문장만 실행합니다. 쿼리 계획은 `explain_query`를 사용하세요. 출력은 모델의 컨텍스트 창을 보호하도록 자동 잘림됩니다:

- 최대 `CUBRID_MCP_MAX_ROWS`행 (기본 1000)
- 렌더링된 출력은 `CUBRID_MCP_MAX_CHARS`자로 제한 (기본 4000)
- 문장 길이는 `CUBRID_MCP_MAX_SQL_LENGTH`로 제한 (기본 65536)
- 문장별 소켓 읽기 타임아웃 `CUBRID_MCP_QUERY_TIMEOUT`초 (기본 30)

다중 문장 입력과 빈 입력(주석만 있거나 `;`만 있는 입력)은 `CUBRID_MCP_READONLY=0`에서도 거부됩니다. 바이너리 값은 작으면 base64로 인코딩되고 크면 요약됩니다(`<binary N bytes>`).

모든 읽기는 자체 트랜잭션을 종료합니다. 서버는 행을 수집한 뒤(잘림 여부와 무관하게) 롤백하므로 도구 호출 사이에 잠금이나 스냅샷이 유지되지 않으며, 다음 호출은 다른 세션이 커밋한 행을 봅니다. `execute_query`는 절대 커밋하지 않으며, 화이트리스트만 완화하는 `CUBRID_MCP_READONLY=0`에서도 읽기 전용입니다. 쓰기·DDL·트랜잭션 제어 키워드(`INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `SET`, `PREPARE`, `EXECUTE`, `DEALLOCATE`, `DO`)로 시작하는 문장은 데이터베이스에 도달하기 전에 거부되며, 오류 메시지가 `execute_write`를 안내합니다. 선두 키워드의 첫 단어를 비교하므로 `CREATE OR REPLACE …`도 `CREATE`와 같이 거부됩니다. 이 키워드 검사는 보안 경계가 아니라 가드레일이며, 보안 경계는 여전히 읽기 전용 데이터베이스 계정입니다. 그래도 결과 집합을 반환하지 않는 문장은 롤백되고 `statement produced no result set; execute_query is read-only, use execute_write …` 오류로 실패하며, 연결은 유지됩니다. 쓰기에는 `execute_write`를 사용하세요.

> **마이그레이션:** `CUBRID_MCP_READONLY=0`으로 `execute_query`를 통해 `INSERT`/`UPDATE`/`DELETE`를 보내던 클라이언트는 대신 `execute_write`(`CUBRID_MCP_WRITE=1`)를 사용해야 합니다.

#### `explain_query(sql, connection=None)`

CUBRID `SHOW TRACE`를 통해 `SELECT`/`WITH` 문의 실행 계획/트레이스를 반환합니다. 문장은 `SET TRACE ON` 아래에서 **실제로 실행**됩니다(실제 데이터베이스 자원을 사용하며 쿼리 자체만큼 오래 걸릴 수 있음). 트레이스를 읽은 뒤 트레이스를 끄고 트랜잭션을 롤백합니다(최선 노력 방식의 정리). `CUBRID_MCP_READONLY` 플래그와 무관하게 읽기 전용 검사를 적용하며, 데이터베이스 계정의 권한도 그대로 적용됩니다. CUBRID에는 `EXPLAIN` 문이 없으므로 실행 계획에는 이 도구를 사용하세요.

#### `table_row_counts(table_names=None, connection=None)`

한 테이블 또는 여러 테이블의 `COUNT(*)` — 크기를 추정하려고 행을 샘플링하는 것보다 저렴합니다. `{"tables": [{"table", "row_count"}, …], "truncated": bool, "total_tables": int}`를 반환하며, `total_tables`는 데이터베이스의 사용자 테이블 수입니다. 알 수 없거나 카운트에 실패한 테이블은 `"row_count": null`과 `error`를 가집니다.

- 생략하거나 `None`: 이름 순으로 처음 50개 사용자 테이블을 카운트합니다. 테이블이 더 있으면 `truncated`가 `true`이며, 나머지 이름(`all_table_names`로 확인)을 최대 50개씩 나누어 전달하세요.
- 명시적 리스트: 해당 테이블을 카운트하며, 50개를 넘으면 `too many tables requested (N); limit is 50 per call` 오류가 발생합니다.
- 빈 리스트(`[]`): 아무것도 카운트하지 않고 `"tables": []`를 반환합니다.

### CUBRID 특화

#### `list_serials(connection=None)`

CUBRID `SERIAL` 시퀀스와 현재값·최솟값·최댓값·증분. (`db_serial` 카탈로그의 컬럼명은 CUBRID 11.4에서 `att_name`→`attr_name`으로 개명되어, 서버 버전에 따라 자동으로 해석합니다.)

#### `health_check(connection=None)`

데이터베이스 연결 상태를 요청 시점에 확인하고 연결별 상태를 보고합니다. 환경 변경 후나 긴 유휴 후에 유용합니다.

### 옵트인 쓰기

#### `execute_write(sql, connection=None)`

**단일** `INSERT`/`UPDATE`/`DELETE` 문을 명시적 트랜잭션(성공 시 커밋, 실패 시 롤백)으로 실행합니다. **쓰기 모드가 활성화된 경우에만 등록**됩니다(`CUBRID_MCP_WRITE=1` 또는 특정 연결의 `CUBRID_<NAME>_MCP_WRITE=1`) — 쓰기 모드가 꺼져 있으면 MCP 기능 탐색에 이 도구가 아예 존재하지 않습니다.

제약: DDL(`CREATE`/`ALTER`/`DROP`/`TRUNCATE`), 독립 실행형 읽기, 트랜잭션 제어, 다중 문장 입력은 거부됩니다. DDL이 제외되는 이유는 DDL 자동 커밋이 아니라, `execute_write`가 DML 도구이고 `execute_query`가 읽기 전용이기 때문입니다. [보안 모델](SECURITY_MODEL.ko.md) 참고.

## 리소스

스키마 메타데이터는 읽기 전용 [MCP 리소스](https://modelcontextprotocol.io/docs/concepts/resources)로도 노출되어, 클라이언트가 도구 호출 없이 스키마 맥락을 발견할 수 있습니다. 리소스는 도구와 동일한 읽기 전용 카탈로그 쿼리를 재사용합니다 — 데이터 접근 범위는 늘어나지 않습니다.

| 리소스 URI | MIME 타입 | 설명 |
|--------------|-----------|------|
| `cubrid://agent-guide` | `text/markdown` | CUBRID 에이전트 종합 가이드: SQL 방언, 타입, 안전, 성능, 도구 선택 |
| `cubrid://guide/sql-dialect` | `text/markdown` | MySQL/PostgreSQL과 다른 CUBRID 구문 |
| `cubrid://guide/types` | `text/markdown` | 데이터 타입 가이드: 컬렉션, ENUM, JSON, Python 매핑 |
| `cubrid://guide/performance` | `text/markdown` | 성능 최적화: SHOW TRACE, 인덱스, 안티패턴 |
| `cubrid://guide/collections` | `text/markdown` | SET, MULTISET, SEQUENCE 타입 심층 설명 |
| `cubrid://schema` | `application/json` | 전체 스키마 인덱스: 모든 사용자 테이블과 테이블별 리소스 URI |
| `cubrid://schema/{table}` | `application/json` | 테이블별 메타데이터(컬럼, 기본 키, 인덱스) — `describe_table`과 동일 |

`cubrid://guide/*`와 에이전트 가이드는 정적 Markdown입니다. 스키마 리소스는 항상 `default` 연결을 읽으며 `connection` 인자를 받지 않습니다([멀티커넥션](MULTI_CONNECTION.ko.md) 참고). `{table}`의 테이블 이름은 URI 템플릿 매칭으로 퍼센트 디코딩되며, 알 수 없거나 시스템 테이블이면 리소스 읽기 오류가 발생합니다(`describe_table` 도구와 동일한 동작).

## 프롬프트

서버는 MCP **프롬프트 템플릿**을 노출합니다 — 흔한 조회 작업의 안내 전용 시작점입니다. 각 프롬프트는 클라이언트에게 어느 읽기 전용 도구를 어떤 순서로 호출할지 알려주는 텍스트를 반환합니다. 프롬프트는 데이터베이스에 접근하거나 SQL을 실행하지 않으며, 데이터 접근 범위를 늘리지 않고, 인자는 신뢰할 수 없는 데이터로 취급됩니다.

| 프롬프트 | 인자 | 설명 |
|--------|-----------|------|
| `summarize_table` | `table` | 테이블을 설명한 뒤 제한된 읽기 전용 쿼리로 샘플 조회 |
| `explain_query` | `sql` | `SELECT`/`WITH`의 실행 계획을 얻고 해석 |
| `inspect_schema` | (없음) | 읽기 전용 도구들로 전체 스키마 개요 작성 |
| `find_index_candidates` | `table` | 테이블의 인덱스 커버리지 검토 |
| `optimize_query` | `sql` | 실행 계획을 분석하고 CUBRID에 맞는 최적화 제안 |
| `migrate_from_mysql` | `sql` | MySQL 쿼리 구문을 유효한 CUBRID SQL로 변환 |
| `explore_unknown_db` | (없음) | 낯선 데이터베이스를 체계적으로 탐색 |
| `safe_data_analysis` | `question` | 읽기 전용 쿼리로 데이터 질문에 답변 |
| `write_cubrid_sql` | `natural_language` | 자연어로 유효한 CUBRID SQL 생성 |
