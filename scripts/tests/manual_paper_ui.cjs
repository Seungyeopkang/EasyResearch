'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const library=source.slice(source.indexOf('function showLibrary(){'),source.indexOf('\nfunction uploadDialog('));
const reader=source.slice(source.indexOf('async function openPaper('),source.indexOf('\n// Each loaded document'));
assert.ok(library.includes('function manualPaperDialog()')&&reader.includes('async function renderReader('));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function harness(post,refreshThrows=false){
  const names=['content','manual-paper','upload-open','export-project','library-filter','library-status','library-sort','library-count','paper-list',
    'local-search-form','local-search-input','local-search-results','manual-paper-form','manual-title','manual-authors','manual-year','manual-doi',
    'modal','close','back-library','attach-pdf'];
  const nodes=Object.fromEntries(names.map(x=>[x,{value:'',disabled:false,innerHTML:'',isConnected:true,insertAdjacentHTML(){}}]));
  let closed=0,refreshed=0,uploaded=null;const errors=[],notifications=[],button={disabled:false};
  nodes.modal.close=()=>{closed++};
  const state={projectId:'project with space',papers:[],paper:null,page:1,zooms:{}};
  const ctx=vm.createContext({state,post,$:selector=>selector==='button[type=submit]'?button:nodes[selector.slice(1)],
    $$:()=>['manual-title','manual-authors','manual-year','manual-doi'].map(name=>nodes[name]),
    heading:(title,subtitle,actions)=>`${title} ${subtitle} ${actions}`,esc:String,empty:(title,detail)=>`${title} ${detail}`,
    needProject:()=>false,paperTitle:p=>p.title,paperAuthors:p=>(p.authors||[]).join(','),paperRow:()=>'',
    modal:html=>{nodes.modal.innerHTML=html},notify:message=>notifications.push(message),error:err=>errors.push(err.message),
    refreshPapers:async()=>{refreshed++;if(refreshThrows)throw Error('refresh failed');state.papers=[{id:'created-paper',title:'Test title',authors:['First Author','Second Author'],file_id:null}]},
    setupPaperActions:async()=>{},uploadDialog:id=>{uploaded=id},console});
  vm.runInContext(library+'\n'+reader+'\nthis.show=showLibrary;',ctx);
  return {nodes,state,errors,notifications,button,show:()=>ctx.show(),get closed(){return closed},get refreshed(){return refreshed},get uploaded(){return uploaded}};
}
function values(ui){ui.nodes['manual-title'].value='  Test title  ';ui.nodes['manual-authors'].value=' First Author \n\n Second Author  \n';ui.nodes['manual-year'].value='2025';ui.nodes['manual-doi'].value=' 10.1234/test ';}
const event={preventDefault(){}};

async function main(){
  const calls=[],ui=harness(async(path,body)=>{calls.push({path,body:JSON.parse(JSON.stringify(body))});return {id:'created-paper'}});
  ui.show();assert.match(ui.nodes.content.innerHTML,/id="manual-paper"/);
  ui.nodes['manual-paper'].onclick();assert.match(ui.nodes.modal.innerHTML,/PDF 없이/);
  values(ui);await ui.nodes['manual-paper-form'].onsubmit(event);
  assert.equal(calls[0].path,'/api/projects/project%20with%20space/papers');
  assert.deepEqual(calls[0].body,{title:'Test title',authors:['First Author','Second Author'],year:2025,doi:'10.1234/test'});
  assert.equal(ui.closed,1);assert.equal(ui.refreshed,1);assert.equal(ui.state.paper.id,'created-paper');
  assert.match(ui.nodes.content.innerHTML,/연결된 PDF가 없습니다/);
  ui.nodes['attach-pdf'].onclick();assert.equal(ui.uploaded,'created-paper');

  const failure=harness(async()=>{throw Error('저장 실패')});failure.show();failure.nodes['manual-paper'].onclick();values(failure);
  await failure.nodes['manual-paper-form'].onsubmit(event);
  assert.equal(failure.closed,0);assert.equal(failure.nodes['manual-title'].value,'  Test title  ');
  assert.equal(failure.nodes['manual-authors'].value,' First Author \n\n Second Author  \n');
  assert.equal(failure.nodes['manual-year'].value,'2025');assert.equal(failure.nodes['manual-doi'].value,' 10.1234/test ');
  assert.equal(failure.button.disabled,false);assert.deepEqual(failure.errors,['저장 실패']);

  const pending=deferred(),paths=[],switched=harness((path)=>{paths.push(path);return pending.promise});
  switched.show();switched.nodes['manual-paper'].onclick();values(switched);
  const saving=switched.nodes['manual-paper-form'].onsubmit(event);assert.equal(switched.button.disabled,true);
  assert.equal(switched.nodes['manual-title'].disabled,true);assert.equal(switched.nodes['manual-authors'].disabled,true);
  switched.nodes.close.onclick();assert.equal(switched.closed,0);
  let prevented=false;switched.nodes.modal.oncancel({preventDefault(){prevented=true}});assert.equal(prevented,true);
  switched.state.projectId='other-project';pending.resolve({id:'created-paper'});await saving;
  assert.equal(paths[0],'/api/projects/project%20with%20space/papers');assert.equal(switched.refreshed,0);
  assert.equal(switched.state.paper,null);assert.equal(switched.nodes['manual-title'].disabled,false);

  const refreshFailure=harness(async()=>({id:'created-paper'}),true);refreshFailure.show();refreshFailure.nodes['manual-paper'].onclick();values(refreshFailure);
  await refreshFailure.nodes['manual-paper-form'].onsubmit(event);
  assert.equal(refreshFailure.closed,1);assert.equal(refreshFailure.errors.length,0);
  assert.ok(refreshFailure.notifications.some(message=>message.includes('논문은 저장됐지만')));
}
main().catch(error=>{console.error(error);process.exitCode=1});
