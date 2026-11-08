'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const hashHelpers=source.slice(source.indexOf('function setPaperHash('),source.indexOf('// Each loaded document'));
const deepLinks=source.slice(source.indexOf('function parsePaperHash('),source.indexOf('(async()=>{try{const health'));
assert.ok(hashHelpers.includes('function clearPaperHash()')&&deepLinks.includes('async function openDeepLink('));

function harness({hash='',projectId='',papers={},dialogOpen=false,paper=null,refreshed=null}={}){
  const calls={modal:[],notify:[],errors:[],opened:[],replaced:[],renders:0,syncs:0,refreshes:0,storage:{}};
  const listeners={},windowListeners={};
  const location={hash,pathname:'/app/index.html',search:'?x=1'};
  const history={replaceState(_state,_title,url){calls.replaced.push(url);location.hash=url.includes('#')?url.slice(url.indexOf('#')):''}};
  const nodes={'prev-page':{disabled:false,click(){calls.prev=(calls.prev||0)+1}},'next-page':{disabled:false,click(){calls.next=(calls.next||0)+1}}};
  const document={addEventListener(type,fn){listeners[type]=fn},querySelector:selector=>dialogOpen&&selector==='dialog[open]'?{}:null};
  const window={addEventListener(type,fn){windowListeners[type]=fn}};
  const state={view:'library',projectId,projects:[{id:'proj-a',name:'A'},{id:'proj-b',name:'B'}],papers:[],paper,page:1};
  const ctx=vm.createContext({
    state,location,history,document,window,URLSearchParams,console,
    localStorage:{getItem:key=>calls.storage[key]??null,setItem:(key,value)=>{calls.storage[key]=String(value)}},
    $:selector=>nodes[selector.slice(1)]??null,
    modal:html=>calls.modal.push(html),
    notify:(message,kind)=>calls.notify.push({message,kind}),
    error:err=>calls.errors.push(err.message),
    syncProjects:()=>{calls.syncs++},
    refreshProjects:async()=>{calls.refreshes++;if(refreshed)state.projects=refreshed.map(p=>({...p}))},
    render:async()=>{calls.renders++;if(!state.paper)ctx.clearPaperHash();state.papers=papers[state.projectId]||[]},
    openPaper:async(id,page)=>{calls.opened.push({id,page});state.paper={id};state.page=page??1;ctx.setPaperHash(id,state.projectId,state.page)},
  });
  vm.runInContext(hashHelpers+'\n'+deepLinks+'\nthis.openDeepLink=openDeepLink;this.clearPaperHash=clearPaperHash;this.setPaperHash=setPaperHash;this.readerKeyHandler=readerKeyHandler;',ctx);
  return {ctx,state,calls,location,listeners,windowListeners,nodes};
}
const flush=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setTimeout(resolve,0))};
const papers={'proj-a':[{id:'paper-2'}],'proj-b':[{id:'paper-1'}]};

async function main(){
  // A deep link selects its project, opens the page, and writes the hash back once.
  let h=harness({hash:'#/paper/paper-1?project=proj-b&page=3',projectId:'proj-a',papers});
  await h.ctx.openDeepLink(h.location.hash);
  assert.equal(h.state.projectId,'proj-b');assert.equal(h.calls.storage['easyresearch-project'],'proj-b');
  assert.equal(h.calls.syncs,1);assert.equal(h.state.view,'library');
  assert.deepEqual(h.calls.opened,[{id:'paper-1',page:3}]);
  assert.equal(h.location.hash,'#/paper/paper-1?project=proj-b&page=3');
  assert.equal(h.calls.notify.length,0);
  await flush();assert.equal(h.calls.opened.length,1);

  // Without a page, the reader uses its default page.
  h=harness({hash:'#/paper/paper-1?project=proj-b',projectId:'proj-a',papers});
  await h.ctx.openDeepLink(h.location.hash);
  assert.deepEqual(h.calls.opened,[{id:'paper-1',page:null}]);

  // Invalid page numbers are rejected before any state changes.
  for(const bad of ['page=0','page=abc','page=1.5','page=-1','page=','page=01x','page=9999999999999999999']){
    h=harness({hash:`#/paper/paper-1?project=proj-b&${bad}`,projectId:'proj-a',papers});
    await h.ctx.openDeepLink(h.location.hash);
    assert.deepEqual(h.calls.opened,[],bad);assert.equal(h.state.projectId,'proj-a',bad);
    assert.match(h.calls.notify[h.calls.notify.length-1].message,/페이지 번호는 1 이상의 정수/,bad);
  }

  // A project missing from the cached list is found after one refresh and its paper opens.
  h=harness({hash:'#/paper/paper-3?project=proj-c&page=2',projectId:'proj-a',papers:{...papers,'proj-c':[{id:'paper-3'}]},refreshed:[{id:'proj-a',name:'A'},{id:'proj-b',name:'B'},{id:'proj-c',name:'C'}]});
  await h.ctx.openDeepLink(h.location.hash);
  assert.equal(h.calls.refreshes,1);assert.equal(h.state.projectId,'proj-c');
  assert.deepEqual(h.calls.opened,[{id:'paper-3',page:2}]);assert.equal(h.calls.notify.length,0);

  // A project still missing after the refresh shows a Korean error and opens nothing.
  h=harness({hash:'#/paper/paper-1?project=nope',projectId:'proj-a',papers});
  await h.ctx.openDeepLink(h.location.hash);
  assert.equal(h.calls.refreshes,1);
  assert.match(h.calls.notify[0].message,/프로젝트를 찾을 수 없습니다/);
  assert.deepEqual(h.calls.opened,[]);assert.equal(h.state.projectId,'proj-a');

  h=harness({hash:'#/paper/paper-9?project=proj-b',projectId:'proj-a',papers});
  await h.ctx.openDeepLink(h.location.hash);
  assert.equal(h.state.projectId,'proj-b');assert.match(h.calls.notify[0].message,/해당 논문/);
  assert.deepEqual(h.calls.opened,[]);

  h=harness({hash:'#/paper/paper-1',projectId:'proj-a',papers});
  await h.ctx.openDeepLink(h.location.hash);
  assert.match(h.calls.notify[0].message,/프로젝트와 논문 정보/);assert.deepEqual(h.calls.opened,[]);

  // Other hashes are ignored entirely.
  h=harness({hash:'#/search',projectId:'proj-a',papers});
  await h.ctx.openDeepLink(h.location.hash);
  assert.equal(h.calls.notify.length,0);assert.equal(h.calls.renders,0);assert.equal(h.state.projectId,'proj-a');

  // hashchange opens a new link; leaving the reader clears the hash.
  h=harness({hash:'#/paper/paper-1?project=proj-b&page=3',projectId:'proj-a',papers});
  h.location.hash='#/paper/paper-2?project=proj-a&page=2';
  h.windowListeners.hashchange();await flush();
  assert.equal(h.state.projectId,'proj-a');
  assert.deepEqual(h.calls.opened,[{id:'paper-2',page:2}]);
  h.state.paper=null;h.ctx.clearPaperHash();assert.equal(h.location.hash,'');
  h.calls.replaced.length=0;h.location.hash='#section';h.ctx.clearPaperHash();assert.equal(h.calls.replaced.length,0);

  // Arrow keys move pages only in the reader, outside text fields, dialogs and with modifiers.
  const key=(extra={})=>({key:'ArrowRight',target:{tagName:'BUTTON'},preventDefault(){this.prevented=true},...extra});
  h=harness({projectId:'proj-b',papers,paper:{id:'paper-1'}});
  let event=key();h.listeners.keydown(event);assert.equal(h.calls.next,1);assert.equal(event.prevented,true);
  event=key({key:'ArrowLeft'});h.listeners.keydown(event);assert.equal(h.calls.prev,1);
  h.listeners.keydown(key({target:{tagName:'INPUT'}}));
  h.listeners.keydown(key({target:{tagName:'TEXTAREA'}}));
  h.listeners.keydown(key({target:{tagName:'SELECT'}}));
  h.listeners.keydown(key({target:{tagName:'DIV',isContentEditable:true}}));
  h.listeners.keydown(key({ctrlKey:true}));h.listeners.keydown(key({metaKey:true}));h.listeners.keydown(key({altKey:true}));
  assert.equal(h.calls.next,1);assert.equal(h.calls.prev,1);
  h.nodes['next-page'].disabled=true;h.listeners.keydown(key());assert.equal(h.calls.next,1);
  h.nodes['next-page'].disabled=false;

  // "?" opens the shortcut dialog outside inputs only.
  h.listeners.keydown({key:'?',target:{tagName:'BODY'},preventDefault(){this.prevented=true}});
  assert.equal(h.calls.modal.length,1);assert.match(h.calls.modal[0],/키보드 단축키/);
  h.listeners.keydown({key:'?',target:{tagName:'INPUT'},preventDefault(){}});assert.equal(h.calls.modal.length,1);

  const dialog=harness({projectId:'proj-b',papers,paper:{id:'paper-1'},dialogOpen:true});
  dialog.listeners.keydown(key());dialog.listeners.keydown({key:'?',target:{tagName:'BODY'},preventDefault(){}});
  assert.equal(dialog.calls.next,undefined);assert.equal(dialog.calls.modal.length,0);

  const libraryOnly=harness({projectId:'proj-b',papers,paper:null});
  libraryOnly.listeners.keydown(key());assert.equal(libraryOnly.calls.next,undefined);
}
main().catch(error=>{console.error(error);process.exitCode=1});
