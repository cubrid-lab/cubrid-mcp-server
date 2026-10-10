# Changelog

## [0.5.0](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.4.0...v0.5.0) (2026-10-10)


### Added

* add MCP Registry server.json ([f04c32e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f04c32e58ead79e633bbc3425b25b94e8ebe2a50))
* add MCP Registry server.json for official listing ([c45bfd5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c45bfd5217824d9178d5036aa2b1f7d440e3e49e))
* CUBRID Skills — domain knowledge resources + expert prompts + tool hints + server instructions ([#162](https://github.com/cubrid-lab/cubrid-mcp-server/issues/162)) ([#163](https://github.com/cubrid-lab/cubrid-mcp-server/issues/163)) ([79927e5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/79927e5b376afb05eb424e15163d29930e3ff62c))
* VHS terminal demo script — MCP server programmatic interaction ([#165](https://github.com/cubrid-lab/cubrid-mcp-server/issues/165)) ([685a437](https://github.com/cubrid-lab/cubrid-mcp-server/commit/685a4379659ac1d67a4e84f92d16c1c252fce4a7))


### Fixed

* accept leading comments in explain_query ([#203](https://github.com/cubrid-lab/cubrid-mcp-server/issues/203)) ([7e10f29](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7e10f29c55eae08ca48780405f78ffbb0e6307bf))
* **database:** end the read transaction after every fetch ([#246](https://github.com/cubrid-lab/cubrid-mcp-server/issues/246)) ([1c838f2](https://github.com/cubrid-lab/cubrid-mcp-server/commit/1c838f24fb6d5f9f6afcd9b78731487d78159d6b))
* **database:** route cursor-creation failures through recovery and re-probe serial column after reconnect ([#200](https://github.com/cubrid-lab/cubrid-mcp-server/issues/200)) ([a4f3492](https://github.com/cubrid-lab/cubrid-mcp-server/commit/a4f34922cc17a784be810bc44d91f0d592dc1364))
* **database:** stop returning host and database names in connect and health_check errors ([#248](https://github.com/cubrid-lab/cubrid-mcp-server/issues/248)) ([aa2f547](https://github.com/cubrid-lab/cubrid-mcp-server/commit/aa2f5479e5518665ccda3af81a22ef677b6be3c4))
* distinguish empty table_names from omitted in table_row_counts ([#183](https://github.com/cubrid-lab/cubrid-mcp-server/issues/183)) ([e6748f0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e6748f04cbeb0d8df35313226f03061791254f0b))
* preserve composite PK order and make the FastMCP canary reach pytest ([#198](https://github.com/cubrid-lab/cubrid-mcp-server/issues/198)) ([3f9b97e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/3f9b97ede33e62a27187693dc50333d09016b91b))
* regenerate demo GIF — 8fps, 800x450, 10s ([#167](https://github.com/cubrid-lab/cubrid-mcp-server/issues/167)) ([16fba7e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/16fba7e15a35b7866826f5b8afae4d67aecc0916))
* reject blank required connection values ([#194](https://github.com/cubrid-lab/cubrid-mcp-server/issues/194)) ([12e6a0d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/12e6a0d3a0d3d617c73cd1933c2370446eab1fcd))
* reject non-finite query timeouts ([#184](https://github.com/cubrid-lab/cubrid-mcp-server/issues/184)) ([4310a90](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4310a901af89f24b02939dd46dcf4c3cb80cc9ee))
* remove the duplicate environment field from the bug report form ([#190](https://github.com/cubrid-lab/cubrid-mcp-server/issues/190)) ([825d736](https://github.com/cubrid-lab/cubrid-mcp-server/commit/825d7368aa74234dce578647cb0b687ee6e28df5))
* **server:** keep execute_query read-only when CUBRID_MCP_READONLY=0 ([#249](https://github.com/cubrid-lab/cubrid-mcp-server/issues/249)) ([f59308c](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f59308cc07cbdb830910d8cbd350862c645ee978))
* **tools:** fence prompt args, cap table_row_counts, resolve class hierarchy names, drop EXPLAIN ([#252](https://github.com/cubrid-lab/cubrid-mcp-server/issues/252)) ([55e6a23](https://github.com/cubrid-lab/cubrid-mcp-server/commit/55e6a238c46d6dbaca430e9df230af5ac6b0a886))
* validate CUBRID port range ([#193](https://github.com/cubrid-lab/cubrid-mcp-server/issues/193)) ([d679122](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d679122b61810cbaf845f1e0537291e027ae6522))


### Documentation

* add issue templates, SUPPORT.md, Code of Conduct, docs badge ([#157](https://github.com/cubrid-lab/cubrid-mcp-server/issues/157)) ([ff1d408](https://github.com/cubrid-lab/cubrid-mcp-server/commit/ff1d40809684aa6768e9597843079627dc184cfe))
* add PyPI version badge to README ([#168](https://github.com/cubrid-lab/cubrid-mcp-server/issues/168)) ([0bc0ca9](https://github.com/cubrid-lab/cubrid-mcp-server/commit/0bc0ca9adbceadeac6270310af47393edf5a960c))
* add Related Projects section linking the cubrid-lab Python stack ([#155](https://github.com/cubrid-lab/cubrid-mcp-server/issues/155)) ([33b9892](https://github.com/cubrid-lab/cubrid-mcp-server/commit/33b9892f3f0631d53c94261f005e3e35110a266d))
* **agents:** add issue size-label convention to AGENTS.md ([#172](https://github.com/cubrid-lab/cubrid-mcp-server/issues/172)) ([33303e5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/33303e50e71a0888cb3130abaec3a6ef38009c53))
* **agents:** align ownership, contributor and review guardrails ([#225](https://github.com/cubrid-lab/cubrid-mcp-server/issues/225)) ([724de18](https://github.com/cubrid-lab/cubrid-mcp-server/commit/724de18fc8f0c84f4dde9142aafdeb1e73ad8adb)), closes [#222](https://github.com/cubrid-lab/cubrid-mcp-server/issues/222)
* **agents:** require priority and size labels when filing issues ([#187](https://github.com/cubrid-lab/cubrid-mcp-server/issues/187)) ([d177ab2](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d177ab27ce4a564256356fd360fc888b5472a2db))
* align security model, docs and changelog with the server ([#253](https://github.com/cubrid-lab/cubrid-mcp-server/issues/253)) ([0649c53](https://github.com/cubrid-lab/cubrid-mcp-server/commit/0649c53d59688b5aa805b4eb83826f16c2ce620a))
* embed demo GIF in README ([#166](https://github.com/cubrid-lab/cubrid-mcp-server/issues/166)) ([179b91d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/179b91d1265e0a3b85a45e8f0762b067df4794b9))
* Korean site pages — docs/ko/ (5 pages) ([#161](https://github.com/cubrid-lab/cubrid-mcp-server/issues/161)) ([2db0059](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2db00590f59ac4d31a4bd46030733d33d6b93396))
* **licenses:** reproducible inventory and the real FastMCP range ([#233](https://github.com/cubrid-lab/cubrid-mcp-server/issues/233)) ([7828861](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7828861e21f94fb07fc21f08a092ad55f6a67f67))
* pin cookbook smoke-test fallback to the exact release ([#196](https://github.com/cubrid-lab/cubrid-mcp-server/issues/196)) ([959b6b7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/959b6b7481438f5e23079bf4c3f22f5c83299593))
* **site:** unified six-tab IA, translations group, ecosystem links ([#158](https://github.com/cubrid-lab/cubrid-mcp-server/issues/158)) ([c086826](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c086826fb30b2800b9fb969ee74de34fad479026))
* translation sync markers + translation-sync CI check ([#159](https://github.com/cubrid-lab/cubrid-mcp-server/issues/159)) ([eb66e09](https://github.com/cubrid-lab/cubrid-mcp-server/commit/eb66e0961dcb4b7b894cbc4794e32ce675db9a8d))
