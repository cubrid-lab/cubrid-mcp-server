const fs=require('fs'),path=require('path');
// Install outside this Python repo: npm install --prefix /tmp/release-please-check --ignore-scripts release-please@17.6.0
// Run: node scripts/check_release_please.cjs /tmp/release-please-check/node_modules/release-please
// This uses upstream strategy/updaters with a read-only local SCM fixture, no GitHub mutations.
const upstream=path.join(process.argv[2], 'build/src');
if (JSON.parse(fs.readFileSync(path.join(process.argv[2], 'package.json'))).version !== '17.6.0') throw new Error('Use bundled action v5.0.0 core 17.6.0');
require(upstream+'/index.js');
const {parseConventionalCommits}=require(upstream+'/commit.js');
const {TagName}=require(upstream+'/util/tag-name.js');
const {Version}=require(upstream+'/version.js');
const root=path.resolve(__dirname,'..');
const config=JSON.parse(fs.readFileSync(path.join(root,'release-please-config.json')));
const {Manifest}=require(upstream+'/manifest.js');
const github={repository:{owner:'cubrid-lab',repo:'cubrid-mcp-server'},getFileJson:async p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8')),findFilesByFilenameAndRef:async()=>[],getFileContentsOnBranch:async p=>({parsedContent:fs.readFileSync(path.join(root,p),'utf8')})};
(async()=>{
 const manifest=await Manifest.fromManifest(github,'main');
 // The manifest must agree with the single-sourced __version__ (both move together in a release PR).
 const released=/^__version__ = "([^"]+)"$/m.exec(fs.readFileSync(path.join(root,'cubrid_mcp_server/__init__.py'),'utf8'))[1];
 if(manifest.releasedVersions['.'].toString()!==released || manifest.repositoryConfig['.'].releaseType!=='python') throw new Error('Invalid manifest/config mapping');
 // [message, expected version from the fixed 0.4.0 boundary, expected ### heading (AGENTS.md GitHub Release Policy)]
 const scenarios=[['fix: correct failure','0.4.1','Fixed'],['feat: new optional API','0.5.0','Added'],['feat!: remove old API\n\nBREAKING CHANGE: remove old API','0.5.0','Added'],['fix!: drop legacy flag','0.5.0','Fixed'],['fix: explicit major\n\nRelease-As: 1.0.0','1.0.0','Fixed'],['docs: improve instructions','0.4.1','Documentation'],['perf: faster fetch','0.4.1','Performance'],['chore: housekeeping',null],['ci: pin action',null],['test: add case',null],['refactor: tidy',null],['fix: explicit override\n\nRelease-As: 0.5.0','0.5.0','Fixed']];
 const allowed=new Set(['Upgrade notes','Added','Changed','Deprecated','Removed','Fixed','Security','Performance','Documentation','CI','Tests','⚠ BREAKING CHANGES']);
 for(const [message,expected,heading] of scenarios){
 // Built through the upstream factory, as Manifest does, so versioning options (bump-minor-pre-major) apply.
 const strategy=await require(upstream+'/factory.js').buildStrategy({...manifest.repositoryConfig['.'],github,path:'.',targetBranch:'main'});
 const commits=parseConventionalCommits([{sha:'a'.repeat(40),message,files:['cubrid_mcp_server/__init__.py']}]);
 const candidate=await strategy.buildReleasePullRequest(commits,{tag:new TagName(Version.parse('0.4.0')),sha:'b6305f1888753ee57e0878bf381d58ce10bb5ff4',notes:''});
 const actual=candidate?candidate.version.toString():null;
 if(actual!==expected)throw new Error(`${message}: expected ${expected} got ${actual}`);
 const headings=candidate?[...candidate.body.toString().matchAll(/^### (.+)$/gm)].map(m=>m[1]):[];
 if(candidate&&(!headings.includes(heading)||headings.some(h=>!allowed.has(h))))throw new Error(`${message}: expected ### ${heading}, got ${headings}`);
 console.log(JSON.stringify({message,version:actual,headings}));
 if(candidate&&message.startsWith('feat:')){
 const out=process.env.RELEASE_PLEASE_CANDIDATE || '/tmp/cubrid-mcp-server-release-please-candidate';fs.mkdirSync(out,{recursive:true});
 // Same-path updates (the two .mcpb/server.json extra-files) are combined as upstream github.js does.
 for(const update of require(upstream+'/updaters/composite.js').mergeUpdates(candidate.updates)){
 const file=path.join(root,update.path); if(!fs.existsSync(file)&&!update.createIfMissing) continue;
 const content=update.updater.updateContent(fs.existsSync(file)?fs.readFileSync(file,'utf8'):undefined);
 fs.mkdirSync(path.dirname(path.join(out,update.path)),{recursive:true}); fs.writeFileSync(path.join(out,update.path),content);
 console.log('updated '+update.path);
 }
 // The MCP Registry metadata must move with __version__ (make release-check enforces it).
 const server=JSON.parse(fs.readFileSync(path.join(out,'.mcpb/server.json'),'utf8'));
 if(server.version!==actual||server.packages.some(p=>p.version!==actual)) throw new Error('.mcpb/server.json versions were not bumped to '+actual);
 }
 }
})().catch(err=>{console.error(err);process.exit(1)});
