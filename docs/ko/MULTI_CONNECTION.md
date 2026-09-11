# 멀티커넥션 (한국어)

> 🌐 [MULTI_CONNECTION.md](https://github.com/cubrid-lab/cubrid-mcp-server/blob/main/docs/MULTI_CONNECTION.md)의 번역입니다. 영어 원문이 표준이며, 페이지 번역은 경고 수준의 동기화 규칙을 따릅니다.

하나의 서버 프로세스로 여러 CUBRID 데이터베이스를 서빙할 수 있습니다. 모든 도구는 대상을 선택하는 선택적 `connection` 인자를 받으며, 단일 데이터베이스 구성은 그대로 작동합니다.

## 기본 연결

`CUBRID_*` 변수만으로 `default`라는 이름의 단일 연결이 구성됩니다:

```bash
export CUBRID_HOST=localhost
export CUBRID_USER=readonly_user
export CUBRID_PASSWORD=secret
export CUBRID_DATABASE=mydb
```

## 이름 있는 연결

`CUBRID_CONNECTIONS`(쉼표 구분)에 추가 연결 이름을 나열하고, 각각에 `CUBRID_<NAME>_*` 변수를 제공합니다:

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

export CUBRID_ANALYTICS_HOST=analytics-db
export CUBRID_ANALYTICS_USER=readonly_user
export CUBRID_ANALYTICS_PASSWORD=secret
export CUBRID_ANALYTICS_DATABASE=analytics
```

이제 클라이언트 대화에서 *"analytics 데이터베이스에서 … 조회해줘"*라고 하면 모델이 도구에 `connection="analytics"`를 전달합니다.

## 규칙

- 연결 이름은 `[A-Za-z0-9_]+` 형식이며 대소문자를 구분하지 않습니다.
- `default`는 예약된 이름입니다(항상 `CUBRID_*` 기본 변수에서 옴) — `CUBRID_CONNECTIONS`에 넣을 수 없습니다.
- 이름 있는 연결 `<NAME>`의 연결 필드는 `CUBRID_<NAME>_HOST` 등에, 선택 튜닝은 `CUBRID_<NAME>_MCP_*`(전역 것과 같은 접미사)에 둡니다.
- 이름 있는 연결은 기본 변수를 **상속하지 않습니다** — 모든 필드를 각각 지정해야 합니다.
- 알 수 없는 연결을 선택하면 사용 가능한 이름을 안내하는 명확한 오류가 반환됩니다.

## 연결별 격리

각 연결은 독립적으로 구성되고 강제됩니다:

| 설정 | 연결별 변수 | 효과 |
|---------|------------------------|------|
| 읽기 전용 | `CUBRID_<NAME>_MCP_READONLY` | 이 연결에만 화이트리스트 강제 |
| 쓰기 모드 | `CUBRID_<NAME>_MCP_WRITE` | 이 연결에만 `execute_write` 옵트인 |
| 감사 로그 | `CUBRID_<NAME>_MCP_AUDIT_LOG` | 이 연결에만 감사 스트림 |
| 출력 제한 | `CUBRID_<NAME>_MCP_MAX_ROWS` / `_MAX_CHARS` / `_MAX_SQL_LENGTH` / `_QUERY_TIMEOUT` | 이 연결에만 튜닝 |

각 연결은 자체 잠금·연결 수명 주기·끊어진 연결 복구를 가지므로, 한 데이터베이스에서 쿼리가 멈춰도 다른 연결을 막지 않습니다.

쓰기 모드 등록의 미묘한 점: 어떤 연결이든 쓰기를 켜면 `execute_write`가 MCP 기능 탐색에 등장하지만, 매 호출은 **대상** 연결의 설정으로 강제됩니다 — 쓰기가 꺼진 연결은 다른 연결이 켜져 있어도 쓰기를 거부합니다. [보안 모델](SECURITY_MODEL.ko.md#계층-2b--옵트인-쓰기-모드-cubrid_mcp_write) 참고.
