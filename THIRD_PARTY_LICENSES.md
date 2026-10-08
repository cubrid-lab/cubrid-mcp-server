# Third-Party Software Licenses

This file records the third-party open-source software that **cubrid-mcp-server**
depends on at runtime and in development, and what cubrid-mcp-server itself
distributes. It is an engineering inventory, not legal advice.

## Direct runtime dependencies

The allowed ranges are the package contract declared in `pyproject.toml`, which
is authoritative. The versions in the tables below are a snapshot observed when
this inventory was generated, not the allowed range.

| Dependency | Allowed range (`pyproject.toml`) | License | Observed in snapshot |
|---|---|---|---|
| `fastmcp` | `>=3.0,<5` | Apache-2.0 | 4.0.11 |
| `pycubrid` | `>=1.4,<2` | MIT | 1.9.0 |
| `sqlparse` | `>=0.5,<1` | BSD License | 0.6.0 |

Every other runtime package is pulled in transitively; the **Required by**
column names the installed packages whose requirements pull each one in.

> **CUBRID server license, for the record.** The CUBRID server engine is
> distributed under Apache License 2.0 and the official APIs/connectors under
> BSD (upstream `COPYING`, http://www.cubrid.org/cubrid) — the frequently cited
> GPL v2+ no longer applies. This project is an independent wire-protocol client
> that neither includes nor links any CUBRID server code; the `cubrid/cubrid`
> Docker image is used for CI verification only.

## What cubrid-mcp-server distributes

- **Wheel**: only the `cubrid_mcp_server` package and its metadata, plus
  `LICENSE` and `NOTICE`. No third-party source code or asset is vendored, and
  no source file carries a third-party copyright notice.
- **Source distribution**: the same files, project metadata (`README.md`,
  `pyproject.toml`, `setup.cfg`) and the test suite.
- **Dependencies** are installed by users from PyPI. cubrid-mcp-server declares
  them; it does not bundle or redistribute them.

## License categories

- **Permissive**: MIT, MIT-0, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, the
  Unlicense and the Python Software Foundation License, as declared by each
  package. The generator also accepts 0BSD, Public Domain and a generic "BSD
  License" declaration as permissive. **Every runtime package falls here.**
- **Weak (file-level) copyleft: MPL**: `certifi` and `pathspec`, both MPL-2.0
  and both in the development toolchain only (`certifi` through `twine` →
  `requests`, `pathspec` through `mypy`). MPL-2.0 is not a permissive license.
  Its obligations attach to the MPL-covered files themselves: anyone
  distributing those files, modified or not, must make their source available
  under MPL-2.0 and keep their notices. Because MPL-2.0 is file-level, it never
  extends to this project's own files (MPL §3.3, "Larger Work"). Separately,
  cubrid-mcp-server does not distribute these packages, so their distribution
  obligations do not arise for this project.
- **Needs review**: any package whose metadata mentions a GPL-family license, or
  a license the generator cannot fully classify. Multiple license classifiers do
  not say whether they combine as "or" or "and", so these are never treated as
  permissive automatically. Each one is resolved below.

### Reviewed entries

- **docutils** (0.23, development only, pulled in by `twine` through
  `readme_renderer`). Its metadata carries Public Domain, BSD and GPL
  classifiers. Its `COPYING.rst` places most files in the public domain, with
  BSD-2-Clause exceptions including `docutils/utils/math/latex2mathml.py`,
  `docutils/__main__.py` and `docutils/utils/math/math2html.py` (relicensed from
  GPL-3.0+ to BSD-2-Clause for Docutils). `docutils/utils/smartquotes.py` also
  carries the original SmartyPants BSD-3-Clause notice, and
  `docutils/utils/_roman_numerals.py` is public domain or 0BSD (per its file
  header). The one GPL-3.0+ file it lists, `tools/editors/emacs/rst.el`, is not
  part of the installed package. As installed, docutils is therefore public
  domain plus permissive BSD terms (BSD-2-Clause, BSD-3-Clause and 0BSD).

## How the inventories were generated

- Dependency declarations: commit `ca7075dc14276bb62404a8499c5a2a32255b60b5`
- Environment: CPython 3.12.13 on Linux x86_64 (glibc 2.35), uv 0.11.7,
  generated 2026-10-09
- Commands (one fresh environment per scope; `--exclude cubrid-mcp-server` drops
  the project itself):

```bash
uv venv -p 3.12 /tmp/tpl-runtime
uv pip install -p /tmp/tpl-runtime/bin/python .
/tmp/tpl-runtime/bin/python scripts/generate_third_party_licenses.py \
    --exclude cubrid-mcp-server --required-by

uv venv -p 3.12 /tmp/tpl-dev
uv pip install -p /tmp/tpl-dev/bin/python ".[dev]"
/tmp/tpl-dev/bin/python scripts/generate_third_party_licenses.py \
    --exclude cubrid-mcp-server --required-by
```

The development table lists only the packages that the `.[dev]` environment
adds to the runtime tree.

`scripts/generate_third_party_licenses.py` uses only the standard library and is
shared with pycubrid and sqlalchemy-cubrid. It reads the PEP 639
`License-Expression` field, then `License ::` classifiers, then a short
`License` field, and never guesses a license. `tests/test_third_party_licenses.py`
fails when a dependency declared in `pyproject.toml` is missing from its table,
when a recorded version falls outside a declared version range, when the direct
dependency table above disagrees with `pyproject.toml`, when a row's category
disagrees with what the generator would assign to its license, or when a
reviewed entry loses its review. Exact `==` pins are checked for presence only:
they are authoritative in `pyproject.toml`, so a routine pin bump does not
require regenerating this snapshot. Transitive rows are kept accurate by
regenerating the tables, not by the test.

## Runtime dependencies (70 packages)

| Name | Version | License | Category | URL | Required by |
|---|---|---|---|---|---|
| aiofile | 3.12.3 | Apache-2.0 | Permissive | https://github.com/mosquito/aiofile | py-key-value-aio |
| annotated-types | 0.8.0 | MIT | Permissive | https://github.com/annotated-types/annotated-types | pydantic |
| anyio | 4.15.1 | MIT | Permissive | https://github.com/agronholm/anyio | httpx2, mcp, sse-starlette, starlette, watchfiles |
| attrs | 26.1.0 | MIT | Permissive | - | cyclopts, jsonschema, jsonschema-path, referencing |
| Authlib | 1.8.0 | BSD License | Permissive | https://github.com/authlib/authlib | fastmcp-slim |
| beartype | 0.22.9 | MIT License | Permissive | - | py-key-value-aio |
| cachetools | 7.2.1 | MIT | Permissive | https://github.com/tkem/cachetools/ | py-key-value-aio |
| caio | 0.12.9 | Apache-2.0 | Permissive | https://github.com/mosquito/caio/ | aiofile |
| cffi | 2.1.1 | MIT-0 | Permissive | https://github.com/python-cffi/cffi | cryptography |
| click | 8.5.0 | BSD-3-Clause | Permissive | https://github.com/pallets/click/ | uvicorn |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Permissive | https://github.com/pyca/cryptography | Authlib, joserfc, SecretStorage |
| cyclopts | 5.2.0 | Apache-2.0 | Permissive | https://github.com/BrianPugh/cyclopts | fastmcp-slim |
| dnspython | 2.8.0 | ISC License (ISCL) | Permissive | https://www.dnspython.org | email-validator |
| docstring_parser | 0.18.0 | MIT License | Permissive | https://github.com/rr-/docstring_parser | cyclopts |
| email-validator | 2.3.0 | The Unlicense (Unlicense) | Permissive | https://github.com/JoshData/python-email-validator | pydantic |
| exceptiongroup | 1.3.1 | MIT License | Permissive | https://github.com/agronholm/exceptiongroup | anyio |
| fastmcp | 4.0.11 | Apache-2.0 | Permissive | https://gofastmcp.com | cubrid-mcp-server |
| fastmcp-slim | 4.0.11 | Apache-2.0 | Permissive | https://gofastmcp.com | fastmcp |
| griffelib | 2.3.2 | ISC | Permissive | - | fastmcp-slim |
| h11 | 0.16.0 | MIT License | Permissive | https://github.com/python-hyper/h11 | httpcore2, uvicorn |
| httpcore2 | 2.13.1 | BSD-3-Clause | Permissive | https://github.com/pydantic/httpx2 | httpx2 |
| httpx2 | 2.13.1 | BSD-3-Clause | Permissive | https://github.com/pydantic/httpx2 | mcp |
| idna | 3.20 | BSD-3-Clause | Permissive | https://github.com/kjd/idna | anyio, email-validator, httpx2 |
| jaraco.classes | 3.4.0 | MIT License | Permissive | https://github.com/jaraco/jaraco.classes | keyring |
| jaraco.context | 6.1.2 | MIT | Permissive | https://github.com/jaraco/jaraco.context | keyring |
| jaraco.functools | 4.6.0 | MIT | Permissive | https://github.com/jaraco/jaraco.functools | keyring |
| jeepney | 0.9.0 | MIT | Permissive | https://gitlab.com/takluyver/jeepney | keyring, SecretStorage |
| joserfc | 1.7.5 | BSD License | Permissive | https://github.com/authlib/joserfc | Authlib |
| jsonref | 1.1.0 | MIT | Permissive | https://github.com/gazpachoking/jsonref | fastmcp-slim |
| jsonschema | 4.26.0 | MIT | Permissive | https://github.com/python-jsonschema/jsonschema | mcp |
| jsonschema-path | 0.5.0 | Apache Software License | Permissive | https://github.com/p1c2u/jsonschema-path | fastmcp-slim |
| jsonschema-specifications | 2025.9.1 | MIT | Permissive | https://github.com/python-jsonschema/jsonschema-specifications | jsonschema |
| keyring | 25.7.0 | MIT | Permissive | https://github.com/jaraco/keyring | py-key-value-aio |
| markdown-it-py | 4.2.0 | MIT License | Permissive | https://github.com/executablebooks/markdown-it-py | rich |
| mcp | 2.3.0 | MIT License | Permissive | https://modelcontextprotocol.io | fastmcp-slim |
| mcp-types | 2.3.0 | MIT License | Permissive | https://modelcontextprotocol.io | fastmcp-slim, mcp |
| mdurl | 0.1.2 | MIT License | Permissive | https://github.com/executablebooks/mdurl | markdown-it-py |
| more-itertools | 11.1.0 | MIT | Permissive | https://github.com/more-itertools/more-itertools | jaraco.classes, jaraco.functools |
| openapi-pydantic | 0.6.0 | MIT License | Permissive | https://github.com/mike-oakley/openapi-pydantic | fastmcp-slim |
| opentelemetry-api | 1.45.1 | Apache-2.0 | Permissive | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api | mcp |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Permissive | https://github.com/pypa/packaging | fastmcp-slim |
| pathable | 0.6.0 | Apache Software License | Permissive | https://github.com/p1c2u/pathable | jsonschema-path |
| platformdirs | 4.12.4 | MIT | Permissive | https://github.com/tox-dev/platformdirs | fastmcp-slim |
| py-key-value-aio | 0.4.6 | Apache-2.0 | Permissive | - | fastmcp-slim |
| pycparser | 3.1 | BSD-3-Clause | Permissive | https://github.com/eliben/pycparser | cffi |
| pycubrid | 1.9.0 | MIT | Permissive | https://github.com/cubrid-lab/pycubrid | cubrid-mcp-server |
| pydantic | 2.14.0 | MIT | Permissive | https://github.com/pydantic/pydantic | fastmcp-slim, mcp, mcp-types, openapi-pydantic, pydantic-settings |
| pydantic_core | 2.50.0 | MIT | Permissive | https://github.com/pydantic | pydantic |
| pydantic-settings | 2.15.0 | MIT | Permissive | https://github.com/pydantic/pydantic-settings | fastmcp-slim |
| Pygments | 2.21.0 | BSD-2-Clause | Permissive | https://pygments.org | rich, rich-rst |
| PyJWT | 2.15.1 | MIT | Permissive | https://github.com/jpadilla/pyjwt | mcp |
| pyperclip | 1.11.0 | BSD License | Permissive | https://github.com/asweigart/pyperclip | fastmcp-slim |
| python-dotenv | 1.2.4 | BSD-3-Clause | Permissive | https://github.com/theskumar/python-dotenv | fastmcp-slim, pydantic-settings |
| python-multipart | 0.0.32 | Apache-2.0 | Permissive | https://github.com/Kludex/python-multipart | mcp |
| PyYAML | 6.0.3 | MIT License | Permissive | https://github.com/yaml/pyyaml | jsonschema-path |
| referencing | 0.37.0 | MIT | Permissive | https://github.com/python-jsonschema/referencing | jsonschema, jsonschema-path, jsonschema-specifications |
| rich | 15.0.0 | MIT License | Permissive | https://github.com/Textualize/rich | cyclopts, fastmcp-slim, rich-rst |
| rich-rst | 2.2.0 | MIT | Permissive | https://github.com/wasi-master/rich-rst | cyclopts |
| rpds-py | 2026.9.1 | MIT | Permissive | https://github.com/crate-py/rpds | jsonschema, referencing |
| SecretStorage | 3.5.0 | BSD-3-Clause | Permissive | https://github.com/mitya57/secretstorage | keyring |
| sqlparse | 0.6.0 | BSD License | Permissive | https://github.com/andialbrecht/sqlparse | cubrid-mcp-server |
| sse-starlette | 3.5.0 | BSD-3-Clause | Permissive | https://github.com/sysid/sse-starlette | mcp |
| starlette | 1.7.0 | BSD-3-Clause | Permissive | https://github.com/Kludex/starlette | mcp, sse-starlette |
| truststore | 0.10.4 | MIT | Permissive | https://github.com/sethmlarson/truststore | httpcore2, httpx2 |
| typing_extensions | 4.16.0 | PSF-2.0 | Permissive | https://github.com/python/typing_extensions | anyio, cryptography, exceptiongroup, fastmcp-slim, httpx2, mcp, mcp-types, opentelemetry-api, py-key-value-aio, pydantic, pydantic_core, PyJWT, referencing, starlette, typing-inspection, uvicorn |
| typing-inspection | 0.4.4 | MIT | Permissive | https://github.com/pydantic/typing-inspection | mcp, pydantic, pydantic-settings |
| uncalled-for | 0.4.0 | MIT License | Permissive | https://github.com/chrisguidry/uncalled-for | fastmcp-slim |
| uvicorn | 0.54.0 | BSD-3-Clause | Permissive | https://uvicorn.dev/ | mcp |
| watchfiles | 1.3.0 | MIT License | Permissive | https://github.com/samuelcolvin/watchfiles | fastmcp-slim, uvicorn |
| websockets | 17.2 | BSD-3-Clause | Permissive | https://github.com/python-websockets/websockets | fastmcp-slim, uvicorn |

## Development / test dependencies: `.[dev]` additions (37 packages, not distributed)

| Name | Version | License | Category | URL | Required by |
|---|---|---|---|---|---|
| ast_serialize | 0.12.1 | MIT | Permissive | https://github.com/mypyc/ast_serialize | mypy |
| build | 1.6.1 | MIT | Permissive | https://build.pypa.io | cubrid-mcp-server, id, pycubrid, sqlparse |
| cfgv | 3.5.0 | MIT | Permissive | https://github.com/asottile/cfgv | pre_commit |
| charset-normalizer | 3.5.2 | MIT | Permissive | - | requests |
| colorama | 0.4.6 | BSD License | Permissive | https://github.com/tartley/colorama | build, pytest, tox |
| coverage | 7.16.2 | Apache-2.0 | Permissive | https://github.com/coveragepy/coveragepy | pytest-cov |
| distlib | 0.4.3 | Python Software Foundation License | Permissive | https://github.com/pypa/distlib | virtualenv |
| filelock | 4.0.12 | MIT | Permissive | https://github.com/tox-dev/py-filelock | python-discovery, tox, virtualenv |
| id | 1.6.1 | Apache Software License | Permissive | https://pypi.org/project/id/ | twine |
| identify | 2.6.20 | MIT | Permissive | https://github.com/pre-commit/identify | pre_commit |
| iniconfig | 2.3.1 | MIT | Permissive | https://github.com/pytest-dev/iniconfig | pytest |
| librt | 0.16.0 | MIT | Permissive | https://github.com/mypyc/librt | mypy |
| mypy | 2.4.0 | MIT | Permissive | https://www.mypy-lang.org/ | beartype, cubrid-mcp-server, dnspython, id, idna, pycubrid, rich-rst |
| mypy_extensions | 1.1.0 | MIT | Permissive | https://github.com/python/mypy_extensions | mypy |
| nh3 | 0.3.7 | MIT | Permissive | https://github.com/messense/nh3 | readme_renderer |
| nodeenv | 1.11.0 | BSD License | Permissive | https://github.com/ekalinin/nodeenv | pre_commit |
| pluggy | 1.6.0 | MIT License | Permissive | - | pytest, pytest-cov, tox |
| pre_commit | 4.6.2 | MIT | Permissive | https://github.com/pre-commit/pre-commit | cubrid-mcp-server, cyclopts, docstring_parser, pluggy, pycubrid, rich-rst |
| pyproject-api | 1.11.4 | MIT | Permissive | https://pyproject-api.readthedocs.io | tox |
| pyproject_hooks | 1.3.3 | MIT | Permissive | https://github.com/pypa/pyproject-hooks | build |
| pytest | 9.1.1 | MIT | Permissive | https://docs.pytest.org/en/latest/ | pytest-asyncio, pytest-cov |
| pytest-asyncio | 1.4.0 | Apache-2.0 | Permissive | https://github.com/pytest-dev/pytest-asyncio | cubrid-mcp-server, jeepney, pycubrid |
| pytest-cov | 7.1.0 | MIT | Permissive | - | caio, cubrid-mcp-server, cyclopts, dnspython, id, jaraco.classes, jaraco.context, jaraco.functools, keyring, markdown-it-py, pycubrid, rich-rst |
| python-discovery | 1.6.1 | MIT License | Permissive | https://github.com/tox-dev/python-discovery | tox, virtualenv |
| readme_renderer | 46.0 | Apache-2.0 | Permissive | https://github.com/pypa/readme_renderer | twine |
| requests | 2.34.2 | Apache Software License | Permissive | https://github.com/psf/requests | requests-toolbelt, twine |
| requests-toolbelt | 1.0.0 | Apache Software License | Permissive | https://github.com/requests/toolbelt | twine |
| rfc3986 | 2.0.0 | Apache Software License | Permissive | http://rfc3986.readthedocs.io | twine |
| ruff | 0.16.10 | MIT | Permissive | https://github.com/astral-sh/ruff | cubrid-mcp-server, id, idna, pycubrid, rich-rst |
| tomli_w | 1.2.0 | MIT License | Permissive | https://github.com/hukkin/tomli-w | tox |
| tox | 4.64.10 | MIT | Permissive | https://tox.wiki | beartype, cubrid-mcp-server, pluggy, pycubrid |
| twine | 7.0.0 | Apache-2.0 | Permissive | https://twine.readthedocs.io/ | cubrid-mcp-server, dnspython, pycubrid |
| urllib3 | 2.8.0 | MIT | Permissive | - | id, requests, twine |
| virtualenv | 21.14.6 | MIT | Permissive | https://github.com/pypa/virtualenv | pre_commit, tox |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (MPL) | https://github.com/certifi/python-certifi | requests |
| pathspec | 1.1.1 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (MPL) | https://github.com/cpburnz/python-pathspec | mypy |
| docutils | 0.23 | BSD License / GNU General Public License (GPL) / Public Domain | Needs review | https://docutils.sourceforge.io | readme_renderer |
