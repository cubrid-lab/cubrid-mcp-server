# Third-Party Software Licenses

This file lists the third-party open-source software used by **cubrid-mcp-server** (runtime dependency tree, generated with `pip-licenses`).

All listed dependencies are distributed under permissive licenses (MIT, BSD-2/3-Clause, Apache-2.0, ISC, PSF, MPL-2.0, Unlicense). No dependency is copyleft/GPL, and none conflicts with this project's MIT license. The single MPL-2.0 package (`certifi`) is a file-level-licensed data bundle distributed unmodified.

Direct runtime dependencies: `fastmcp>=3.0,<4` (Apache-2.0), `pycubrid>=1.4,<2` (MIT), `sqlparse>=0.5,<1` (BSD). Everything else below is pulled in transitively by `fastmcp`.

## Runtime dependencies

| Name                      | Version   | License                              | URL                                                                                |
|---------------------------|-----------|--------------------------------------|------------------------------------------------------------------------------------|
| aiofile                   | 3.9.0     | Apache Software License              | http://github.com/mosquito/aiofile                                                 |
| jsonschema-path           | 0.5.0     | Apache Software License              | https://github.com/p1c2u/jsonschema-path                                           |
| pathable                  | 0.6.0     | Apache Software License              | https://github.com/p1c2u/pathable                                                  |
| caio                      | 0.9.25    | Apache-2.0                           | UNKNOWN                                                                            |
| cyclopts                  | 4.25.2    | Apache-2.0                           | https://github.com/BrianPugh/cyclopts                                              |
| fastmcp                   | 3.4.7     | Apache-2.0                           | https://gofastmcp.com                                                              |
| fastmcp-slim              | 3.4.7     | Apache-2.0                           | https://gofastmcp.com                                                              |
| importlib_metadata        | 9.0.1     | Apache-2.0                           | https://github.com/python/importlib_metadata                                       |
| opentelemetry-api         | 1.44.0    | Apache-2.0                           | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| py-key-value-aio          | 0.4.5     | Apache-2.0                           | UNKNOWN                                                                            |
| python-multipart          | 0.0.32    | Apache-2.0                           | https://github.com/Kludex/python-multipart                                         |
| packaging                 | 26.3      | Apache-2.0 OR BSD-2-Clause           | https://github.com/pypa/packaging                                                  |
| cryptography              | 50.0.1    | Apache-2.0 OR BSD-3-Clause           | https://github.com/pyca/cryptography                                               |
| Authlib                   | 1.8.0     | BSD License                          | https://github.com/authlib/authlib                                                 |
| httpx                     | 0.28.1    | BSD License                          | https://github.com/encode/httpx                                                    |
| joserfc                   | 1.7.5     | BSD License                          | https://github.com/authlib/joserfc                                                 |
| pyperclip                 | 1.11.0    | BSD License                          | https://github.com/asweigart/pyperclip                                                        |
| sqlparse                  | 0.6.0     | BSD License                          | https://github.com/andialbrecht/sqlparse                                           |
| Pygments                  | 2.21.0    | BSD-2-Clause                         | https://pygments.org                                                               |
| SecretStorage             | 3.5.0     | BSD-3-Clause                         | https://github.com/mitya57/secretstorage                                           |
| click                     | 8.5.0     | BSD-3-Clause                         | https://github.com/pallets/click/                                                  |
| httpcore                  | 1.6.0     | BSD-3-Clause                         | https://www.encode.io/httpcore/                                                    |
| idna                      | 3.19      | BSD-3-Clause                         | https://github.com/kjd/idna                                                        |
| pycparser                 | 3.0       | BSD-3-Clause                         | https://github.com/eliben/pycparser                                                |
| python-dotenv             | 1.2.3     | BSD-3-Clause                         | https://github.com/theskumar/python-dotenv                                         |
| sse-starlette             | 3.4.11    | BSD-3-Clause                         | https://github.com/sysid/sse-starlette                                             |
| starlette                 | 1.6.0     | BSD-3-Clause                         | https://github.com/Kludex/starlette                                                |
| uvicorn                   | 0.52.4    | BSD-3-Clause                         | https://uvicorn.dev/                                                               |
| websockets                | 16.1.1    | BSD-3-Clause                         | https://github.com/python-websockets/websockets                                    |
| griffelib                 | 2.3.0     | ISC                                  | UNKNOWN                                                                            |
| dnspython                 | 2.8.0     | ISC License (ISCL)                   | https://www.dnspython.org                                                          |
| PyJWT                     | 2.13.0    | MIT                                  | https://github.com/jpadilla/pyjwt                                                  |
| annotated-types           | 0.8.0     | MIT                                  | https://github.com/annotated-types/annotated-types                                 |
| anyio                     | 4.15.1    | MIT                                  | https://anyio.readthedocs.io/en/stable/versionhistory.html                         |
| attrs                     | 26.1.0    | MIT                                  | https://www.attrs.org/en/stable/changelog.html                                     |
| cachetools                | 7.1.8     | MIT                                  | https://github.com/tkem/cachetools/                                                |
| httpx-sse                 | 0.4.3     | MIT                                  | https://github.com/florimondmanca/httpx-sse                                        |
| jaraco.context            | 6.1.2     | MIT                                  | https://github.com/jaraco/jaraco.context                                           |
| jaraco.functools          | 4.6.0     | MIT                                  | https://github.com/jaraco/jaraco.functools                                         |
| jeepney                   | 0.9.0     | MIT                                  | https://gitlab.com/takluyver/jeepney                                              |
| jsonref                   | 1.1.0     | MIT                                  | https://github.com/gazpachoking/jsonref                                            |
| jsonschema                | 4.26.0    | MIT                                  | https://github.com/python-jsonschema/jsonschema                                    |
| jsonschema-specifications | 2025.9.1  | MIT                                  | https://github.com/python-jsonschema/jsonschema-specifications                     |
| keyring                   | 25.7.0    | MIT                                  | https://github.com/jaraco/keyring                                                  |
| more-itertools            | 11.1.0    | MIT                                  | https://github.com/more-itertools/more-itertools                                   |
| pycubrid                  | 1.7.0     | MIT                                  | https://github.com/cubrid-lab/pycubrid                                             |
| pydantic                  | 2.13.5    | MIT                                  | https://github.com/pydantic/pydantic                                               |
| pydantic-settings         | 2.15.0    | MIT                                  | https://github.com/pydantic/pydantic-settings                                      |
| pydantic_core             | 2.46.5    | MIT                                  | https://github.com/pydantic/pydantic                                               |
| referencing               | 0.37.0    | MIT                                  | https://github.com/python-jsonschema/referencing                                   |
| rich-rst                  | 2.1.0     | MIT                                  | https://wasi-master.github.io/rich-rst                                             |
| rpds-py                   | 0.30.0    | MIT                                  | https://github.com/crate-py/rpds                                                   |
| typing-inspection         | 0.4.4     | MIT                                  | https://github.com/pydantic/typing-inspection                                      |
| zipp                      | 4.1.0     | MIT                                  | https://github.com/jaraco/zipp                                                     |
| PyYAML                    | 6.0.3     | MIT License                          | https://pyyaml.org/                                                                |
| backports.tarfile         | 1.2.0     | MIT License                          | https://github.com/jaraco/backports.tarfile                                        |
| beartype                  | 0.22.9    | MIT License                          | UNKNOWN                                                                            |
| docstring_parser          | 0.18.0    | MIT License                          | https://github.com/rr-/docstring_parser                                            |
| exceptiongroup            | 1.3.1     | MIT License                          | https://github.com/agronholm/exceptiongroup/blob/main/CHANGES.rst                  |
| h11                       | 0.16.0    | MIT License                          | https://github.com/python-hyper/h11                                                |
| jaraco.classes            | 3.4.0     | MIT License                          | https://github.com/jaraco/jaraco.classes                                           |
| markdown-it-py            | 4.2.0     | MIT License                          | https://github.com/executablebooks/markdown-it-py                                  |
| mcp                       | 1.30.0    | MIT License                          | https://modelcontextprotocol.io                                                    |
| mdurl                     | 0.1.2     | MIT License                          | https://github.com/executablebooks/mdurl                                           |
| openapi-pydantic          | 0.5.1     | MIT License                          | https://github.com/mike-oakley/openapi-pydantic                                    |
| rich                      | 15.0.0    | MIT License                          | https://github.com/Textualize/rich                                                 |
| uncalled-for              | 0.4.0     | MIT License                          | https://github.com/chrisguidry/uncalled-for                                        |
| watchfiles                | 1.2.0     | MIT License                          | https://github.com/samuelcolvin/watchfiles                                         |
| cffi                      | 2.1.1     | MIT-0                                | https://cffi.readthedocs.io/en/latest/whatsnew.html                                |
| certifi                   | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi                                          |
| typing_extensions         | 4.16.0    | PSF-2.0                              | https://github.com/python/typing_extensions                                        |
| email-validator           | 2.3.0     | The Unlicense (Unlicense)            | https://github.com/JoshData/python-email-validator                                 |

(The `cubrid-mcp-server` row emitted by pip-licenses is omitted — it is this project.)

## Development / test-only dependencies

Not distributed with the package: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `pre-commit`, `tox` (all MIT/Apache-2.0).
