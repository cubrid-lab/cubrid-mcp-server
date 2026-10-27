# Changelog

## [0.7.0](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.6.0...v0.7.0) (2026-10-27)


### Added

* **config:** make the connect timeout and server output limits configurable ([#454](https://github.com/cubrid-lab/cubrid-mcp-server/issues/454)) ([f65e548](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f65e548348100494510838ec731ed474a889a159))


### Documentation

* adopt type-only issue titles and shared triage guidance ([31cc0b0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/31cc0b0fa536cce00845d6192e77ffd6823fea8e))
* **readme:** repin the brand icon to the 2026-10-25 brand revision ([#457](https://github.com/cubrid-lab/cubrid-mcp-server/issues/457)) ([d35e4a5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d35e4a51bffa97bd4e51cba9f891d1578a8bf520))
* **readme:** repin the brand icon to the emblem-aligned keyline ([#470](https://github.com/cubrid-lab/cubrid-mcp-server/issues/470)) ([c80a8c0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c80a8c0b5a10a6f0fada88b857890d15c087109c))
* **readme:** repin the brand icon to the shared white marks ([#473](https://github.com/cubrid-lab/cubrid-mcp-server/issues/473)) ([6eaba76](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6eaba766ffdb0e1f42c7e5e8dfade1d81d281f68))

## [0.6.0](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.6...v0.6.0) (2026-10-25)


### Added

* **make:** run the live integration lane in make verify ([#447](https://github.com/cubrid-lab/cubrid-mcp-server/issues/447)) ([e694f56](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e694f569cbbe62034a275a846b90bd8ed7e827f1))
* **make:** write an aggregate verification summary under test-results/verify ([#450](https://github.com/cubrid-lab/cubrid-mcp-server/issues/450)) ([3260e38](https://github.com/cubrid-lab/cubrid-mcp-server/commit/3260e3810ec8ed1a285f3f84731ac96271ca9892)), closes [#449](https://github.com/cubrid-lab/cubrid-mcp-server/issues/449)

## [0.5.6](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.5...v0.5.6) (2026-10-25)


### Fixed

* **config:** name the variable when a boolean setting is invalid ([#443](https://github.com/cubrid-lab/cubrid-mcp-server/issues/443)) ([8fc77db](https://github.com/cubrid-lab/cubrid-mcp-server/commit/8fc77db9e5379706dae95b1e85894be677f92df7)), closes [#435](https://github.com/cubrid-lab/cubrid-mcp-server/issues/435)


### Documentation

* **agents:** align independent MCP safety review and local title rules ([7592c53](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7592c534b089882077f2b5da8345659aeb041d5c))
* **agents:** clarify MCP safety review and local PR policy ([#442](https://github.com/cubrid-lab/cubrid-mcp-server/issues/442)) ([7592c53](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7592c534b089882077f2b5da8345659aeb041d5c))

## [0.5.5](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.4...v0.5.5) (2026-10-25)


### Fixed

* **context:** log suppressed connection close failures ([#439](https://github.com/cubrid-lab/cubrid-mcp-server/issues/439)) ([9924e2c](https://github.com/cubrid-lab/cubrid-mcp-server/commit/9924e2c94454eb0abda19776e23135d12acca381))
* **context:** raise RuntimeError for unset audit loggers instead of asserting ([#438](https://github.com/cubrid-lab/cubrid-mcp-server/issues/438)) ([b6d8bb0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/b6d8bb0e79022dc7a0df7282c87fae8784fdcf69))
* **reporting:** redact credentials embedded in environment command metadata ([#433](https://github.com/cubrid-lab/cubrid-mcp-server/issues/433)) ([702aac6](https://github.com/cubrid-lab/cubrid-mcp-server/commit/702aac6f4b4c43a5b2abdaa36a4adfe645c0830a))


### Documentation

* **server:** document the table-resolution and schema helper functions ([#440](https://github.com/cubrid-lab/cubrid-mcp-server/issues/440)) ([c645e6c](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c645e6c6b272a8dadfa1f1113c07b9f7571422c5)), closes [#432](https://github.com/cubrid-lab/cubrid-mcp-server/issues/432)

## [0.5.4](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.3...v0.5.4) (2026-10-24)


### CI

* **release:** verify against the current cookbook and restart after the abandoned 0.5.3 ([#424](https://github.com/cubrid-lab/cubrid-mcp-server/issues/424)) ([1d1e5a1](https://github.com/cubrid-lab/cubrid-mcp-server/commit/1d1e5a18f1496a9b4a5c6f5794bd488edbf020cd)), closes [#388](https://github.com/cubrid-lab/cubrid-mcp-server/issues/388)

## [0.5.3](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.2...v0.5.3) (2026-10-24)


### Fixed

* **test:** never let a failed service-log save skip make integration cleanup ([#416](https://github.com/cubrid-lab/cubrid-mcp-server/issues/416)) ([dec3942](https://github.com/cubrid-lab/cubrid-mcp-server/commit/dec39420852edc175e36f5d9afa5953685c7c937))


### Changed

* remove the App-owned agent-review publisher ([#397](https://github.com/cubrid-lab/cubrid-mcp-server/issues/397)) ([e5bf28e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e5bf28e006f8c005c7d9334ed87ee3531bf61eb2))


### Documentation

* **agents:** require repository-local issue authoring checks ([#383](https://github.com/cubrid-lab/cubrid-mcp-server/issues/383)) ([4f04af7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4f04af7b503cae0e2fcc97b79326a629d9e68aea))
* enforce repository-local issue drafting ([4f04af7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4f04af7b503cae0e2fcc97b79326a629d9e68aea))
* **ko:** replace the mistranslated redaction term in the Korean docs ([#389](https://github.com/cubrid-lab/cubrid-mcp-server/issues/389)) ([2621d8b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2621d8b415a1dcf7ea8a34fab758126bb6b5f216)), closes [#290](https://github.com/cubrid-lab/cubrid-mcp-server/issues/290)
* **triage:** clarify PR overlap and execution precedence ([440166a](https://github.com/cubrid-lab/cubrid-mcp-server/commit/440166adcf3b8a1e51cda51353a2c4f762adec40)), closes [#410](https://github.com/cubrid-lab/cubrid-mcp-server/issues/410)

## [0.5.2](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.1...v0.5.2) (2026-10-20)


### Fixed

* **agent-review:** do not count empty reply-only Copilot records as review rounds ([#349](https://github.com/cubrid-lab/cubrid-mcp-server/issues/349)) ([6d75295](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6d75295e4a724302099c3789213f14cb922e9253))
* **agent-review:** fail closed when a review thread lacks author or resolver identity ([#347](https://github.com/cubrid-lab/cubrid-mcp-server/issues/347)) ([09d746e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/09d746ec158d165b2d9700f346ee3c49eb127b1d)), closes [#346](https://github.com/cubrid-lab/cubrid-mcp-server/issues/346)
* **database:** preserve serial-probe failures and fence the cache to its connection ([#357](https://github.com/cubrid-lab/cubrid-mcp-server/issues/357)) ([0832251](https://github.com/cubrid-lab/cubrid-mcp-server/commit/08322518dd85efeb3e0fe743ebc827deee93788d))


### Documentation

* **agents:** accept an independent reviewer agent in the standalone-agent review route ([#342](https://github.com/cubrid-lab/cubrid-mcp-server/issues/342)) ([bbfe3a4](https://github.com/cubrid-lab/cubrid-mcp-server/commit/bbfe3a476fee5c8a63c3f35b823ba305c627eb66))
* **agents:** require a Copilot or maintainer review in the standalone-agent route ([#344](https://github.com/cubrid-lab/cubrid-mcp-server/issues/344)) ([3b18cdf](https://github.com/cubrid-lab/cubrid-mcp-server/commit/3b18cdfbd46a83a70268a2642a18fd5e540cad46)), closes [#317](https://github.com/cubrid-lab/cubrid-mcp-server/issues/317)
* **contributing:** clarify good-first-issue access for human contributors ([#322](https://github.com/cubrid-lab/cubrid-mcp-server/issues/322)) ([b319f9f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/b319f9fe33c7576f412d17c9ca1397a6f89ba246))
* fix Korean documentation typos and links ([#320](https://github.com/cubrid-lab/cubrid-mcp-server/issues/320)) ([6f49f05](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6f49f059ae8e6cf7e9f12d2ed6d31b5641d54680))
* **ko:** fix a typo and broken cross-page links ([#319](https://github.com/cubrid-lab/cubrid-mcp-server/issues/319)) ([6f49f05](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6f49f059ae8e6cf7e9f12d2ed6d31b5641d54680))
* **onboarding:** provide a safe single-client walkthrough with a prepared read-only lab ([#356](https://github.com/cubrid-lab/cubrid-mcp-server/issues/356)) ([e3e0185](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e3e0185f21e25ffe08f5a866a30c2557505b519a)), closes [#352](https://github.com/cubrid-lab/cubrid-mcp-server/issues/352)
* **release:** add a release review checklist to the runbook ([#360](https://github.com/cubrid-lab/cubrid-mcp-server/issues/360)) ([f196135](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f196135b82298e6af701469925e57424f345dab0)), closes [#355](https://github.com/cubrid-lab/cubrid-mcp-server/issues/355)
* **site:** label the site as main-branch documentation with its build commit ([#359](https://github.com/cubrid-lab/cubrid-mcp-server/issues/359)) ([08550e7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/08550e7655260de42c78e879bb5eb1580106d67d)), closes [#355](https://github.com/cubrid-lab/cubrid-mcp-server/issues/355)
* **structure:** group the site by reader and make Korean pages peers ([#358](https://github.com/cubrid-lab/cubrid-mcp-server/issues/358)) ([c0f900b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c0f900b76fe72523e51e5ae4e84fe197324284f8)), closes [#354](https://github.com/cubrid-lab/cubrid-mcp-server/issues/354)

## [0.5.1](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.5.0...v0.5.1) (2026-10-14)


### Fixed

* **audit:** determine SQL category after stripping leading comments ([#283](https://github.com/cubrid-lab/cubrid-mcp-server/issues/283)) ([2c64d0f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2c64d0f74d4a3bb6fa9cc0619e4e5b05a559f492))
* **safety:** reject CALL and KILL in execute_query when read-only mode is off ([#304](https://github.com/cubrid-lab/cubrid-mcp-server/issues/304)) ([49bb56f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/49bb56f3d196ce3f73de45e809da2e78a38bb4ca))
* **safety:** reject INCR and serial advances in execute_query with the whitelist off ([#305](https://github.com/cubrid-lab/cubrid-mcp-server/issues/305)) ([56c97eb](https://github.com/cubrid-lab/cubrid-mcp-server/commit/56c97eb99052f231d8103d7dbb6002153ddc03e3)), closes [#301](https://github.com/cubrid-lab/cubrid-mcp-server/issues/301) [#303](https://github.com/cubrid-lab/cubrid-mcp-server/issues/303)
* **safety:** reject INCR, DECR and serial advances in read-only queries ([#302](https://github.com/cubrid-lab/cubrid-mcp-server/issues/302)) ([d17bf58](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d17bf584d9987f39752357398e5f0d05ee23f23a))
* **server:** report the package version in MCP serverInfo ([#288](https://github.com/cubrid-lab/cubrid-mcp-server/issues/288)) ([55fea91](https://github.com/cubrid-lab/cubrid-mcp-server/commit/55fea91d9428fe7b421f25564dcef0864de85b6b))
* **tools:** cap the first result row at the configured character limit ([#306](https://github.com/cubrid-lab/cubrid-mcp-server/issues/306)) ([094b3c6](https://github.com/cubrid-lab/cubrid-mcp-server/commit/094b3c6fbe74892e629284c48fe87a8e735e6578))
* **tools:** parse, keep connections and cap output in explain_query like execute_query ([#308](https://github.com/cubrid-lab/cubrid-mcp-server/issues/308)) ([75dd0cc](https://github.com/cubrid-lab/cubrid-mcp-server/commit/75dd0cc4de2dcb9d16fa40811edd154e96142c69))
* **tools:** qualify table metadata by owner on CUBRID 11.2 and later ([#307](https://github.com/cubrid-lab/cubrid-mcp-server/issues/307)) ([6f8a60f](https://github.com/cubrid-lab/cubrid-mcp-server/commit/6f8a60f602f657b42ed27836fe025836ffc13f28))


### Documentation

* add per-tool JSON response examples to TOOLS.md ([#285](https://github.com/cubrid-lab/cubrid-mcp-server/issues/285)) ([d88b998](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d88b99820ed1afa6392bb574762d6917dbdc7aad))
* add Related Projects to the Korean README and test the empty password ([#293](https://github.com/cubrid-lab/cubrid-mcp-server/issues/293)) ([908f834](https://github.com/cubrid-lab/cubrid-mcp-server/commit/908f8348650b298db257c65c1639869e07b3709e))
* **agents:** refresh the module list and tool surface in AGENTS.md ([#289](https://github.com/cubrid-lab/cubrid-mcp-server/issues/289)) ([d10f0bc](https://github.com/cubrid-lab/cubrid-mcp-server/commit/d10f0bc46cbcbef3a3a94393a1317f3a61c6c64d))
* **brand:** show the centered repository icon in the README and docs site ([#316](https://github.com/cubrid-lab/cubrid-mcp-server/issues/316)) ([666174d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/666174d30abeab16b561551bd938bed0bd7b7669)), closes [#310](https://github.com/cubrid-lab/cubrid-mcp-server/issues/310)
* record the README demo GIF from a real MCP session ([#287](https://github.com/cubrid-lab/cubrid-mcp-server/issues/287)) ([f46426b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f46426b30a9637537f93102a9d62c8e5087acb7f))
* **release:** set last-release-sha when an abandoned release has no tag ([#323](https://github.com/cubrid-lab/cubrid-mcp-server/issues/323)) ([a4ffb9b](https://github.com/cubrid-lab/cubrid-mcp-server/commit/a4ffb9ba3dac79c7afb4c94f5bc9b189298b9f65))

## [0.5.0](https://github.com/cubrid-lab/cubrid-mcp-server/compare/v0.4.0...v0.5.0) (2026-10-12)


### Added

* add MCP Registry server.json ([f04c32e](https://github.com/cubrid-lab/cubrid-mcp-server/commit/f04c32e58ead79e633bbc3425b25b94e8ebe2a50))
* add MCP Registry server.json for official listing ([c45bfd5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c45bfd5217824d9178d5036aa2b1f7d440e3e49e))
* CUBRID Skills — domain knowledge resources + expert prompts + tool hints + server instructions ([#162](https://github.com/cubrid-lab/cubrid-mcp-server/issues/162)) ([#163](https://github.com/cubrid-lab/cubrid-mcp-server/issues/163)) ([79927e5](https://github.com/cubrid-lab/cubrid-mcp-server/commit/79927e5b376afb05eb424e15163d29930e3ff62c))
* VHS terminal demo script — MCP server programmatic interaction ([#165](https://github.com/cubrid-lab/cubrid-mcp-server/issues/165)) ([685a437](https://github.com/cubrid-lab/cubrid-mcp-server/commit/685a4379659ac1d67a4e84f92d16c1c252fce4a7))


### Fixed

* accept leading comments in explain_query ([#203](https://github.com/cubrid-lab/cubrid-mcp-server/issues/203)) ([7e10f29](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7e10f29c55eae08ca48780405f78ffbb0e6307bf))
* **database:** discard the shared connection when trace cleanup fails ([#269](https://github.com/cubrid-lab/cubrid-mcp-server/issues/269)) ([739dca0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/739dca082a0026ee9ab8210d546b7f2520741460)), closes [#264](https://github.com/cubrid-lab/cubrid-mcp-server/issues/264)
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
* align the closing-guard wording with sqlalchemy-cubrid ([#277](https://github.com/cubrid-lab/cubrid-mcp-server/issues/277)) ([e7eece8](https://github.com/cubrid-lab/cubrid-mcp-server/commit/e7eece86adc913496d86c3c6915a90c48814fd44))
* correct the older closing-guard CHANGELOG notes ([#278](https://github.com/cubrid-lab/cubrid-mcp-server/issues/278)) ([c917df4](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c917df4e920dd68e906439a83a7ea226906e1881))
* embed demo GIF in README ([#166](https://github.com/cubrid-lab/cubrid-mcp-server/issues/166)) ([179b91d](https://github.com/cubrid-lab/cubrid-mcp-server/commit/179b91d1265e0a3b85a45e8f0762b067df4794b9))
* Korean site pages — docs/ko/ (5 pages) ([#161](https://github.com/cubrid-lab/cubrid-mcp-server/issues/161)) ([2db0059](https://github.com/cubrid-lab/cubrid-mcp-server/commit/2db00590f59ac4d31a4bd46030733d33d6b93396))
* **licenses:** reproducible inventory and the real FastMCP range ([#233](https://github.com/cubrid-lab/cubrid-mcp-server/issues/233)) ([7828861](https://github.com/cubrid-lab/cubrid-mcp-server/commit/7828861e21f94fb07fc21f08a092ad55f6a67f67))
* pin cookbook smoke-test fallback to the exact release ([#196](https://github.com/cubrid-lab/cubrid-mcp-server/issues/196)) ([959b6b7](https://github.com/cubrid-lab/cubrid-mcp-server/commit/959b6b7481438f5e23079bf4c3f22f5c83299593))
* **repo:** document the main branch protection baseline ([#266](https://github.com/cubrid-lab/cubrid-mcp-server/issues/266)) ([bf288a0](https://github.com/cubrid-lab/cubrid-mcp-server/commit/bf288a061fac9ae0f18ad0d209ed70df744bc7f5))
* **review:** separate Oracle and GitHub review requirements ([#265](https://github.com/cubrid-lab/cubrid-mcp-server/issues/265)) ([4763bfc](https://github.com/cubrid-lab/cubrid-mcp-server/commit/4763bfc1f268c20d0ae6d342220ab1deeb1e478a))
* **site:** unified six-tab IA, translations group, ecosystem links ([#158](https://github.com/cubrid-lab/cubrid-mcp-server/issues/158)) ([c086826](https://github.com/cubrid-lab/cubrid-mcp-server/commit/c086826fb30b2800b9fb969ee74de34fad479026))
* translation sync markers + translation-sync CI check ([#159](https://github.com/cubrid-lab/cubrid-mcp-server/issues/159)) ([eb66e09](https://github.com/cubrid-lab/cubrid-mcp-server/commit/eb66e0961dcb4b7b894cbc4794e32ce675db9a8d))
