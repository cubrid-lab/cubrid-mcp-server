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

#### `list_indexes(table_name, connection=None)`

테이블에 정의된 인덱스와 인덱스된 키 컬럼·플래그(유니크, 리버스).

#### `list_class_hierarchy(connection=None, ...)`

CUBRID `CLASS` 상속 관계 — 어느 테이블이 어느 테이블을 상속하는지.

### 쿼리

#### `execute_query(sql, connection=None)`

**읽기 전용** SQL(`SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `EXPLAIN`, `WITH`)을 실행합니다. 출력은 모델의 컨텍스트 창을 보호하도록 자동 잘림됩니다:

- 최대 `CUBRID_MCP_MAX_ROWS`행 (기본 1000)
- 렌더링된 출력은 `CUBRID_MCP_MAX_CHARS`자로 제한 (기본 4000)
- 문장 길이는 `CUBRID_MCP_MAX_SQL_LENGTH`로 제한 (기본 65536)
- 문장별 소켓 읽기 타임아웃 `CUBRID_MCP_QUERY_TIMEOUT`초 (기본 30)

다중 문장 입력은 거부됩니다. 바이너리 값은 작으면 base64로 인코딩되고 크면 요약됩니다(`<binary N bytes>`).

#### `explain_query(sql, connection=None)`

CUBRID `SHOW TRACE`를 통해 `SELECT`/`WITH` 문의 실행 계획/트레이스를 반환합니다. `CUBRID_MCP_READONLY` 플래그와 무관하게 항상 읽기 전용입니다.

#### `table_row_counts(connection=None, ...)`

한 테이블 또는 여러 테이블의 `COUNT(*)` — 크기를 추정하려고 행을 샘플링하는 것보다 저렴합니다.

### CUBRID 특화

#### `list_serials(connection=None)`

CUBRID `SERIAL` 시퀀스와 현재값·최솟값·최댓값·증분. (`db_serial` 카탈로그의 컬럼명은 CUBRID 11.4에서 `att_name`→`attr_name`으로 개명되어, 서버 버전에 따라 자동으로 해석합니다.)

#### `health_check(connection=None)`

데이터베이스 연결 상태를 요청 시점에 확인하고 연결별 상태를 보고합니다. 환경 변경 후나 긴 유휴 후에 유용합니다.

### 옵트인 쓰기

#### `execute_write(sql, connection=None)`

**단일** `INSERT`/`UPDATE`/`DELETE` 문을 명시적 트랜잭션(성공 시 커밋, 실패 시 롤백)으로 실행합니다. **쓰기 모드가 활성화된 경우에만 등록**됩니다(`CUBRID_MCP_WRITE=1` 또는 특정 연결의 `CUBRID_<NAME>_MCP_WRITE=1`) — 쓰기 모드가 꺼져 있으면 MCP 기능 탐색에 이 도구가 아예 존재하지 않습니다.

제약: DDL(`CREATE`/`ALTER`/`DROP`/`TRUNCATE`), 독립 실행형 읽기, 트랜잭션 제어, 다중 문장 입력은 거부됩니다. [보안 모델](SECURITY_MODEL.ko.md) 참고.

## 리소스

스키마 메타데이터는 읽기 전용 [MCP 리소스](https://modelcontextprotocol.io/docs/concepts/resources)로도 노출되어, 클라이언트가 도구 호출 없이 스키마 맥락을 발견할 수 있습니다. 리소스는 도구와 동일한 읽기 전용 카탈로그 쿼리를 재사용합니다 — 데이터 접근 범위는 늘어나지 않습니다.

| 리소스 URI | 설명 |
|--------------|------|
| `cubrid://schema` | 전체 스키마 인덱스: 모든 사용자 테이블과 테이블별 리소스 URI |
| `cubrid://schema/{table}` | 테이블별 메타데이터(컬럼, 기본 키, 인덱스) — `describe_table`과 동일 |

둘 다 `application/json`을 반환합니다. `{table}`의 테이블 이름은 URI 템플릿 매칭으로 퍼센트 디코딩되며, 알 수 없거나 시스템 테이블이면 리소스 읽기 오류가 발생합니다(`describe_table` 도구와 동일한 동작).

## 프롬프트

서버는 MCP **프롬프트 템플릿**을 노출합니다 — 흔한 조회 작업의 안내 전용 시작점입니다. 각 프롬프트는 클라이언트에게 어느 읽기 전용 도구를 어떤 순서로 호출할지 알려주는 텍스트를 반환합니다. 프롬프트는 데이터베이스에 접근하거나 SQL을 실행하지 않으며, 데이터 접근 범위를 늘리지 않고, 인자는 신뢰할 수 없는 데이터로 취급됩니다.

| 프롬프트 | 인자 | 설명 |
|--------|-----------|------|
| `summarize_table` | `table` | 테이블을 설명한 뒤 제한된 읽기 전용 쿼리로 샘플 조회 |
| `explain_query` | `sql` | `SELECT`/`WITH`의 실행 계획을 얻고 해석 |
| `inspect_schema` | (없음) | 읽기 전용 도구들로 전체 스키마 개요 작성 |
| `find_index_candidates` | `table` | 테이블의 인덱스 커버리지 검토 |
