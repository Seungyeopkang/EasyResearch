'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const start=source.indexOf('async function showVersions('),end=source.indexOf('\nfunction ',start);
assert.ok(start>=0&&end>start);
const code=source.slice(start,end)+'\nthis.show=showVersions;';
function harness(){
  const nodes=Object.fromEntries(['modal','version-list','version-form','version-file','version-label','version-result'].map(x=>[x,{value:'',disabled:false,textContent:'',innerHTML:'',isConnected:true}]));
  const button={disabled:false},calls=[],notices=[],errors=[],confirmations=[];
  let current={primary:{size:100},versions:[{id:'version +1',label:'초판',revision:'revision-1',size:30}],trashed_versions:[]},conflict=false,failGet=false,promptValue=' 새 이름 ';
  class FormDataStub{constructor(){this.parts=[]}append(k,v){this.parts.push([k,v])}}
  async function api(path,options){
    calls.push({path,options});
    if(!options){if(failGet){failGet=false;throw Error('목록 연결 오류')}return JSON.parse(JSON.stringify(current))}
    if(path.endsWith('/versions'))return {trashed:true,duplicate:true};
    if(conflict){conflict=false;const e=new Error('conflict');e.status=409;throw e}
    const item=(current.versions[0]||current.trashed_versions[0]);
    if(options.method==='PATCH'){item.label=JSON.parse(options.body).label;item.revision='revision-2'}
    else if(options.method==='DELETE'){item.revision='revision-3';current.versions=[];current.trashed_versions=[item]}
    else if(path.endsWith('/restore')){item.revision='revision-4';current.trashed_versions=[];current.versions=[item]}
    return item;
  }
  const ctx=vm.createContext({api,FormData:FormDataStub,$:s=>s==='button'?button:nodes[s.slice(1)],
    modal:html=>{nodes.modal.innerHTML=html},esc:String,formatBytes:n=>`${n}B`,prompt:()=>promptValue,
    confirm:message=>{confirmations.push(message);return true},notify:(...args)=>notices.push(args),error:err=>errors.push(err.message)});
  vm.runInContext(code,ctx);
  return {nodes,calls,notices,errors,confirmations,button,show:()=>ctx.show({id:'paper space'}),
    action:(action,id='version +1')=>{const b={dataset:{versionAction:action,versionId:id},disabled:false};return nodes['version-list'].onclick({target:{closest:()=>b}})},
    conflict:()=>{conflict=true},failNextGet:()=>{failGet=true},setPrompt:x=>{promptValue=x}};
}
async function main(){
  const ui=harness();await ui.show();
  assert.match(ui.nodes.modal.innerHTML,/기존 PDF와 저장된 근거는 그대로 유지됩니다/);
  assert.match(ui.nodes.modal.innerHTML,/발췌와 읽기 기록은 기존 PDF에 연결됩니다/);
  assert.match(ui.nodes['version-list'].innerHTML,/기본 원본/);
  assert.match(ui.nodes['version-list'].innerHTML,/초판/);
  await ui.action('rename');
  let op=ui.calls.find(x=>x.options?.method==='PATCH');
  assert.equal(op.path,'/api/papers/paper%20space/versions/version%20%2B1');
  assert.deepEqual(JSON.parse(op.options.body),{expected_revision:'revision-1',label:'새 이름'});
  assert.equal(op.options.headers['Content-Type'],'application/json');
  assert.match(ui.nodes['version-list'].innerHTML,/새 이름/);
  await ui.action('trash');
  op=ui.calls.find(x=>x.options?.method==='DELETE');
  assert.equal(op.path,'/api/papers/paper%20space/versions/version%20%2B1');
  assert.deepEqual(JSON.parse(op.options.body),{expected_revision:'revision-2'});
  assert.match(ui.confirmations[0],/기본 원본, 근거는 보존/);
  assert.match(ui.nodes['version-list'].innerHTML,/버전 휴지통/);
  await ui.action('restore');
  op=ui.calls.find(x=>x.options?.method==='POST'&&x.path.endsWith('/restore'));
  assert.equal(op.path,'/api/papers/paper%20space/versions/version%20%2B1/restore');
  assert.deepEqual(JSON.parse(op.options.body),{expected_revision:'revision-3'});
  assert.doesNotMatch(ui.nodes['version-list'].innerHTML,/버전 휴지통/);

  const loads=ui.calls.filter(x=>!x.options).length;ui.conflict();await ui.action('rename');
  assert.equal(ui.calls.filter(x=>!x.options).length,loads+1,'409 must reload latest version list');
  assert.ok(ui.notices.some(([message])=>message.includes('다른 창에서 버전이 변경')));
  ui.nodes['version-file'].files=['synthetic PDF'];ui.nodes['version-label'].value=' 버전명 ';
  await ui.nodes['version-form'].onsubmit({preventDefault(){}});
  op=ui.calls.find(x=>x.options?.method==='POST'&&x.path.endsWith('/versions'));
  assert.equal(op.path,'/api/papers/paper%20space/versions');
  assert.deepEqual(op.options.body.parts,[['file','synthetic PDF'],['label','버전명']]);
  assert.match(ui.nodes['version-result'].textContent,/휴지통에 있습니다.*복구/);
  assert.equal(ui.nodes['version-label'].disabled,false);assert.equal(ui.nodes['version-file'].disabled,false);
  assert.deepEqual(ui.errors,[]);

  const changed=harness();await changed.show();changed.failNextGet();await changed.action('rename');
  assert.match(changed.nodes['version-list'].textContent,/변경은 저장됐지만 목록을 불러오지 못했습니다/);
  assert.ok(changed.notices.some(([message])=>message.includes('변경은 저장됐지만 목록을 갱신하지 못했습니다')));
  assert.deepEqual(changed.errors,[],'a saved rename is not reported as a failed action');

  const conflictFailure=harness();await conflictFailure.show();conflictFailure.conflict();conflictFailure.failNextGet();
  await conflictFailure.action('rename');
  assert.ok(conflictFailure.notices.some(([message])=>message.includes('다른 창에서 버전이 변경')));
  assert.match(conflictFailure.nodes['version-list'].textContent,/최신 목록을 불러오지 못했습니다/);
  assert.deepEqual(conflictFailure.errors,[]);

  const uploadFailure=harness();await uploadFailure.show();uploadFailure.failNextGet();
  uploadFailure.nodes['version-file'].files=['synthetic PDF'];uploadFailure.nodes['version-label'].value='버전';
  await uploadFailure.nodes['version-form'].onsubmit({preventDefault(){}});
  assert.match(uploadFailure.nodes['version-result'].textContent,/휴지통에 있습니다.*복구.*목록은 갱신하지 못했습니다/);
  assert.match(uploadFailure.nodes['version-list'].textContent,/목록을 불러오지 못했습니다/);
  assert.doesNotMatch(uploadFailure.nodes['version-result'].textContent,/등록하지 못했습니다/);
  assert.equal(uploadFailure.nodes['version-label'].disabled,false);assert.equal(uploadFailure.nodes['version-file'].disabled,false);
}
main().catch(error=>{console.error(error);process.exitCode=1});
