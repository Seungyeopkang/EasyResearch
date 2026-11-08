'use strict';
// Checks the project-independent library and reader behaviors by running the
// real functions from apps/web/app.js against small stubs of the DOM and API.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const TOP=/\n(?=(?:async )?function |const |let |\$\(|\$\$|document\.|window\.|import\(|\(async)/g;
function grab(name){
  const decl=source.search(new RegExp(`\\n(?:async )?function ${name}\\(|\\nconst ${name} `));
  assert.ok(decl>=0,`${name} must exist in app.js`);
  TOP.lastIndex=decl+1;
  const next=TOP.exec(source);
  return source.slice(decl+1,next?next.index+1:source.length);
}
const NAMES=['readProgress','matchedText','paperCardHtml','refreshLibrary','refreshCategories','findPaper','reloadLibraryPaper','updateCachedPaper',
  'patchPaper','scheduleProgressSave','translateSelectionNow','switchReaderTab','refreshTranslationStatus','wirePaperInfo','renderPaperInfo',
  'renderPaperCategories','renderPaperProjects','renderTopics','refreshPaperInfo','isCurrentReader','showSearch','sourceLabel','statusLabel',
  'paperTitle','paperAuthors','setActiveNav'];
const code=NAMES.map(grab).join('\n');

function makeNode(){
  return {value:'',disabled:false,hidden:false,innerHTML:'',textContent:'',dataset:{},classList:{toggle(){},add(){},remove(){}},
    setAttribute(){},style:{},isConnected:true,insertAdjacentHTML(){},addEventListener(){}};
}
function harness({api,projects=[],translation=null,selection='',paper=null,libraryPapers=[]}={}){
  const nodes={};
  const $=sel=>{const id=sel.slice(1);return nodes[id]||(nodes[id]=makeNode())};
  const calls=[],notices=[],errors=[];
  const state={view:'library',projectId:'',projects,papers:[],paper,page:1,zooms:{},libraryPapers,categories:[],readerGeneration:1,selectionText:selection,progressTimer:null,pageText:null,results:[]};
  const ctx=vm.createContext({
    state,console,setTimeout,clearTimeout,Date,Math,URLSearchParams,JSON,window:{},
    $,$$:()=>[],esc:v=>String(v??''),
    api:async(url,options={})=>{calls.push({url,method:options.method||'GET',body:options.body?JSON.parse(options.body):undefined});return api?api(url,options):{}},
    post:async(url,data)=>{calls.push({url,method:'POST',body:data});return api?api(url,{method:'POST',body:JSON.stringify(data)}):{}},
    notify:(message,kind)=>notices.push({message,kind}),error:e=>errors.push(e.message),
    translation,heading:t=>t,empty:(t,d)=>`${t} ${d}`,loadSearchHistory:async()=>{},
    TRANSLATE_LABELS:{available:'바로',downloadable:'내려받기',downloading:'내려받는 중',unavailable:'불가',unsupported:'Chrome 138 이상 또는 지원되는 Edge에서 열어 주세요.'},
    names:{library:'내 서재',search:'논문 찾기'},
    needProject:()=>false,
    confirm:()=>true,
  });
  vm.runInContext(code+'\nthis.__exports={'+NAMES.join(',')+'};',ctx);
  return {ctx,state,calls,notices,errors,nodes,fns:ctx.__exports,$};
}

async function main(){
  // 1. Library cards show suggested vs confirmed categories and progress without any project.
  const card=(()=>{const h=harness({});return h.fns})();
  const html=card.paperCardHtml({id:'p1',title:'Pruning',authors:['A'],year:2024,reading_status:'reading',last_page:4,page_count:10,last_opened_at:'x',
    categories:[{id:'c1',name:'경량화',status:'suggested',matched:['pruning']},{id:'c2',name:'최적화',status:'confirmed'},{id:'c3',name:'제외',status:'rejected'}],projects:[]});
  assert.match(html,/chip suggested[^>]*>경량화/);assert.match(html,/chip confirmed[^>]*>최적화/);assert.doesNotMatch(html,/제외</);
  assert.match(html,/aria-valuenow="50"/);assert.match(html,/읽는 중/);
  assert.equal(card.readProgress({page_count:10,last_page:4,last_opened_at:'x'}),50);
  assert.equal(card.readProgress({page_count:10,last_page:0}),0,'unopened papers show no progress');

  // 2. Reader progress is saved globally: PATCH /api/papers/{id} with last_page only, never project_id.
  const reader=harness({api:async()=>({})});
  const paper={id:'p1',last_page:0,projects:[{id:'proj-a',name:'A'}]};
  reader.state.libraryPapers=[paper];reader.state.paper=paper;
  reader.fns.scheduleProgressSave(paper,5);
  await new Promise(r=>setTimeout(r,700));
  const patch=reader.calls.find(c=>c.method==='PATCH');
  assert.ok(patch,'progress is patched');assert.equal(patch.url,'/api/papers/p1');
  assert.deepEqual(patch.body,{last_page:4});assert.equal('project_id' in patch.body,false);
  assert.equal(paper.last_page,4);

  // 3. Reading status changes are global too.
  const status=harness({api:async()=>({reading_status:'read'})});
  const statusPaper={id:'p2',reading_status:'to_read',projects:[],categories:[]};
  status.state.paper=statusPaper;status.state.libraryPapers=[statusPaper];
  status.fns.wirePaperInfo(statusPaper,'',false);
  await status.nodes['reading-status'].onchange({target:{value:'read'}});
  assert.deepEqual(status.calls.find(c=>c.method==='PATCH').body,{reading_status:'read'});

  // 4. Translation runs synchronously inside the click path (no await before translateText) and reports unsupported browsers in Korean.
  const seen=[];
  const translating=harness({selection:'Hello world.',translation:{translateText:(text)=>{seen.push(text);return Promise.resolve('안녕')}}});
  translating.fns.translateSelectionNow();
  assert.deepEqual(seen,['Hello world.'],'translateText is called before the click handler returns');
  const missing=harness({selection:'Hi.',translation:null});
  missing.fns.translateSelectionNow();
  assert.match(missing.nodes['translate-selection-result'].innerHTML,/Chrome 138 이상 또는 지원되는 Edge/);

  // 5. Categories: confirm and reject call the PUT endpoint with the status; rejected rows disappear from cards.
  const cats=harness({api:async()=>({})});
  const catPaper={id:'p3',projects:[],categories:[{id:'c9',name:'분석',status:'suggested',matched:[]}]};
  cats.state.paper=catPaper;cats.state.libraryPapers=[catPaper];
  cats.fns.wirePaperInfo(catPaper,'',false);
  const clicks=[];
  for(const status of ['confirmed','rejected']){
    await cats.nodes['paper-categories'].onclick({target:{closest:sel=>sel==='[data-cat-status]'?{disabled:false,dataset:{catStatus:status,catId:'c9'}}:null}});
  }
  const put=cats.calls.filter(c=>c.method==='PUT');
  assert.deepEqual(put.map(c=>c.url),['/api/papers/p3/categories/c9','/api/papers/p3/categories/c9']);
  assert.deepEqual(put.map(c=>c.body),[{status:'confirmed'},{status:'rejected'}]);

  // 6. Linking a paper to a project uses the link endpoint.
  const link=harness({api:async()=>({}),projects:[{id:'proj-b',name:'B'}]});
  const linkPaper={id:'p4',projects:[],categories:[]};
  link.state.paper=linkPaper;link.state.libraryPapers=[linkPaper];link.state.projects=[{id:'proj-b',name:'B'}];
  link.fns.wirePaperInfo(linkPaper,'',false);
  link.nodes['add-project-select'].value='proj-b';
  await link.nodes['add-project-link'].onclick();
  assert.ok(link.calls.some(c=>c.method==='POST'&&c.url==='/api/projects/proj-b/papers/p4/link'),'link endpoint is called');

  // 7. Search works without a selected project and does not show the project gate.
  const search=harness({projects:[]});
  search.fns.showSearch();
  assert.match(search.nodes.content.innerHTML,/논문 찾기/);
  assert.doesNotMatch(search.nodes.content.innerHTML,/프로젝트가 필요합니다/);
  assert.match(search.nodes.content.innerHTML,/search-form/);
  console.log('library_reader_ui: all checks passed');
}
main().catch(error=>{console.error(error);process.exitCode=1});
