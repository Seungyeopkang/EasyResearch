'use strict';
// Manual paper entry no longer depends on a project: it posts to /api/papers,
// refreshes the library, and opens the new paper. These checks keep the old
// coverage for payload shape, failure retention, pending lock and stale views.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const dialog=source.slice(source.indexOf('function manualPaperDialog()'),source.indexOf('\nfunction uploadDialog('));
assert.ok(dialog.includes("post('/api/papers',payload)"),'manual entry posts without a project');
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function harness(post,{refreshThrows=false}={}){
  const names=['modal','close','manual-paper-form','manual-title','manual-authors','manual-year','manual-doi'];
  const nodes=Object.fromEntries(names.map(x=>[x,{value:'',disabled:false,innerHTML:'',isConnected:true}]));
  const button={disabled:false};
  const errors=[],notifications=[];
  let closed=0,refreshed=0;const opened=[];
  nodes.modal.close=()=>{closed++};
  const state={view:'library',projectId:'project with space',papers:[],paper:null,page:1,zooms:{}};
  const ctx=vm.createContext({state,post,
    $:selector=>selector==='button[type=submit]'?button:nodes[selector.slice(1)],
    $$:()=>['manual-title','manual-authors','manual-year','manual-doi'].map(name=>nodes[name]),
    esc:String,
    modal:html=>{nodes.modal.innerHTML=html},
    notify:message=>notifications.push(message),
    error:err=>errors.push(err.message),
    refreshLibrary:async()=>{refreshed++;if(refreshThrows)throw Error('refresh failed')},
    openPaper:async id=>{opened.push(id);state.paper={id}},
    console});
  vm.runInContext(dialog+'\nthis.manualPaperDialog=manualPaperDialog;',ctx);
  return {
    nodes,state,errors,notifications,button,
    open:()=>ctx.manualPaperDialog(),
    get closed(){return closed},get refreshed(){return refreshed},get opened(){return opened},
  };
}
function values(ui){ui.nodes['manual-title'].value='  Test title  ';ui.nodes['manual-authors'].value=' First Author \n\n Second Author  \n';ui.nodes['manual-year'].value='2025';ui.nodes['manual-doi'].value=' 10.1234/test ';}
const event={preventDefault(){}};

async function main(){
  const calls=[];
  const ui=harness(async(path,body)=>{calls.push({path,body:JSON.parse(JSON.stringify(body))});return {id:'created-paper'}});
  ui.open();assert.match(ui.nodes.modal.innerHTML,/PDF 없이/);
  values(ui);await ui.nodes['manual-paper-form'].onsubmit(event);
  assert.equal(calls[0].path,'/api/papers');
  assert.deepEqual(calls[0].body,{title:'Test title',authors:['First Author','Second Author'],year:2025,doi:'10.1234/test'});
  assert.equal(ui.closed,1);assert.equal(ui.refreshed,1);assert.deepEqual(ui.opened,['created-paper']);
  assert.equal(ui.state.paper.id,'created-paper');

  const failure=harness(async()=>{throw Error('저장 실패')});failure.open();values(failure);
  await failure.nodes['manual-paper-form'].onsubmit(event);
  assert.equal(failure.closed,0);assert.equal(failure.nodes['manual-title'].value,'  Test title  ');
  assert.equal(failure.nodes['manual-authors'].value,' First Author \n\n Second Author  \n');
  assert.equal(failure.nodes['manual-year'].value,'2025');assert.equal(failure.nodes['manual-doi'].value,' 10.1234/test ');
  assert.equal(failure.button.disabled,false);assert.deepEqual(failure.errors,['저장 실패']);

  // While saving, inputs and close are locked. A view change before the response means no library refresh or open.
  const pending=deferred(),paths=[],switched=harness(path=>{paths.push(path);return pending.promise});
  switched.open();values(switched);
  const saving=switched.nodes['manual-paper-form'].onsubmit(event);assert.equal(switched.button.disabled,true);
  assert.equal(switched.nodes['manual-title'].disabled,true);assert.equal(switched.nodes['manual-authors'].disabled,true);
  switched.nodes.close.onclick();assert.equal(switched.closed,0);
  let prevented=false;switched.nodes.modal.oncancel({preventDefault(){prevented=true}});assert.equal(prevented,true);
  switched.state.view='search';pending.resolve({id:'created-paper'});await saving;
  assert.equal(paths[0],'/api/papers');assert.equal(switched.refreshed,0);
  assert.equal(switched.state.paper,null);assert.equal(switched.nodes['manual-title'].disabled,false);

  const refreshFailure=harness(async()=>({id:'created-paper'}),{refreshThrows:true});refreshFailure.open();values(refreshFailure);
  await refreshFailure.nodes['manual-paper-form'].onsubmit(event);
  assert.equal(refreshFailure.closed,1);assert.equal(refreshFailure.errors.length,0);
  assert.ok(refreshFailure.notifications.some(message=>message.includes('논문은 저장됐지만')));
  console.log('manual_paper_ui: all checks passed');
}
main().catch(error=>{console.error(error);process.exitCode=1});
