'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const trash=source.slice(source.indexOf('async function showTrash(){'),source.indexOf('async function runOcr('));
assert.ok(trash.includes('function renderPurgePanel(')&&trash.includes('async function purgePreview('));

function harness(scenario){
  const ids=['trash-list','purge-panel','purge-form','purge-confirm-text','purge-submit','purge-cancel','purge-files'];
  const nodes=Object.fromEntries(ids.map(id=>[id,{value:'',checked:false,disabled:false,innerHTML:'',isConnected:true}]));
  // Rendering a fresh panel replaces its controls, so their values reset like a real DOM.
  const panel=nodes['purge-panel'];let html='';
  Object.defineProperty(panel,'innerHTML',{get(){return html},set(value){html=value;nodes['purge-confirm-text'].value='';nodes['purge-files'].checked=false;nodes['purge-submit'].disabled=true;nodes['purge-confirm-text'].disabled=false;nodes['purge-cancel'].disabled=false}});
  const calls=[],notifications=[],errors=[],counts={projects:0,papers:0};
  const state={view:'library',paper:null,projectId:'project-a'};
  const route=async(requestPath,method)=>{
    if(requestPath==='/api/trash')return {projects:[],papers:[{id:'p1',title:'Paper A',project_count:1,evidence_count:2,deleted_at:'2026-11-01'}],links:[],evidence:[]};
    if(method==='GET'&&requestPath.endsWith('/purge-preview')){return scenario.previews.length>1?scenario.previews.shift():scenario.previews[0]}
    if(method==='POST'&&requestPath.endsWith('/purge')){if(scenario.purgeError)throw scenario.purgeError;return {status:'purged',deleted:{papers:1},deleted_files:0,files_not_removed:[]}}
    throw new Error(`unexpected request ${method} ${requestPath}`);
  };
  const api=async(requestPath,options={})=>{const method=(options.method||'GET').toUpperCase(),body=options.body?JSON.parse(options.body):undefined;calls.push({path:requestPath,method,body});return route(requestPath,method)};
  const post=(url,data)=>api(url,{method:'POST',body:JSON.stringify(data)});
  const ctx=vm.createContext({state,api,post,$:selector=>nodes[selector.slice(1)],$$:()=>[],esc:String,
    modal:()=>{},notify:message=>notifications.push(message),error:err=>errors.push(err.message),
    refreshProjects:async()=>{counts.projects++},refreshPapers:async()=>{counts.papers++},
    loadEvidence:async()=>{},showLibrary:()=>{},console});
  vm.runInContext(trash+'\nthis.showTrash=showTrash;',ctx);
  return {ctx,nodes,calls,notifications,errors,counts,scenario};
}
function preview(over={}){
  return {kind:'papers',id:'p1',title:'Paper A',counts:{papers:1,evidence:2,project_papers:0},blocked_by:[],deletable_files:[],retained_files_reason:null,confirm_token:'tok-1',notice:'영구 삭제한 기록은 복구할 수 없습니다.',...over};
}
const flush=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setTimeout(resolve,0))};
async function openPurge(h){
  await h.ctx.showTrash();
  h.nodes['trash-list'].onclick({target:{closest:selector=>selector==='[data-purge-kind]'?{dataset:{purgeKind:'papers',purgeId:'p1'}}:null}});
  await flush();
}
function type(h,value){h.nodes['purge-confirm-text'].value=value;h.nodes['purge-confirm-text'].oninput()}
async function submit(h){await h.nodes['purge-form'].onsubmit({preventDefault(){}});await flush()}
const posts=h=>h.calls.filter(c=>c.method==='POST');

async function main(){
  // Confirm stays disabled until the exact word 삭제 is typed.
  let h=harness({previews:[preview()]});
  await openPurge(h);
  const panel=()=>h.nodes['purge-panel'].innerHTML;
  assert.match(panel(),/영구 삭제 확인/);assert.match(panel(),/근거 2개/);assert.match(panel(),/논문 1개/);
  assert.doesNotMatch(panel(),/프로젝트 연결/);
  assert.equal(h.calls[1].path,'/api/trash/papers/p1/purge-preview');
  assert.equal(h.nodes['purge-submit'].disabled,true);
  type(h,'삭');assert.equal(h.nodes['purge-submit'].disabled,true);
  type(h,'삭제');assert.equal(h.nodes['purge-submit'].disabled,false);
  type(h,'');assert.equal(h.nodes['purge-submit'].disabled,true);
  type(h,'삭제');
  h.nodes['purge-cancel'].onclick();assert.equal(panel(),'');

  // Blocked previews never enable the confirm button, even with the word typed.
  h=harness({previews:[preview({blocked_by:[{reason:'idea_linked_evidence',ids:['e1']}]})]});
  await openPurge(h);
  assert.match(panel(),/아이디어가 연결된 근거가 있어 삭제할 수 없습니다\. 아이디어에서 연결을 먼저 해제하세요\./);
  type(h,'삭제');assert.equal(h.nodes['purge-submit'].disabled,true);
  await submit(h);assert.equal(posts(h).length,0);

  h=harness({previews:[preview({blocked_by:[{reason:'ocr_job_shared',ids:['j1']}]})]});
  await openPurge(h);assert.match(panel(),/다른 기록이 이 OCR 결과를 사용합니다\./);
  type(h,'삭제');assert.equal(h.nodes['purge-submit'].disabled,true);

  // delete_files is sent as true only when the PDF checkbox is checked.
  const withFiles=()=>preview({deletable_files:[{file_id:'f1',sha256:'abc',size:3}],retained_files_reason:'백업 ZIP은 삭제하지 않습니다.'});
  h=harness({previews:[withFiles()]});
  await openPurge(h);
  assert.match(panel(),/원본 PDF 파일 1개도 삭제 \(되돌릴 수 없음\)/);assert.match(panel(),/백업 ZIP은 삭제하지 않습니다\./);
  assert.equal(h.nodes['purge-files'].checked,false);
  type(h,'삭제');await submit(h);
  assert.equal(posts(h).length,1);
  assert.deepEqual(posts(h)[0],{path:'/api/trash/papers/p1/purge',method:'POST',body:{confirm_token:'tok-1',delete_files:false}});
  assert.ok(h.notifications.includes('기록을 영구 삭제했습니다.'));
  assert.equal(h.calls.at(-1).path,'/api/trash');
  assert.equal(h.counts.projects,1);assert.equal(h.counts.papers,1);
  assert.equal(panel(),'');

  h=harness({previews:[withFiles()]});
  await openPurge(h);
  h.nodes['purge-files'].checked=true;type(h,'삭제');await submit(h);
  assert.deepEqual(posts(h)[0].body,{confirm_token:'tok-1',delete_files:true});

  // A stale token (409) reloads the preview, notifies, and the retry uses the new token.
  const stale=Object.assign(new Error('stale'),{status:409});
  h=harness({previews:[preview(),preview({confirm_token:'tok-2'})],purgeError:stale});
  await openPurge(h);
  type(h,'삭제');await submit(h);
  assert.equal(h.calls.filter(c=>c.path.endsWith('/purge-preview')).length,2);
  assert.ok(h.notifications.some(message=>message.includes('미리보기를 다시 불러옵니다')));
  assert.equal(h.counts.projects,0);
  assert.equal(h.nodes['purge-submit'].disabled,true);
  assert.equal(h.nodes['purge-confirm-text'].value,'');
  h.scenario.purgeError=null;
  type(h,'삭제');await submit(h);
  assert.equal(posts(h).at(-1).body.confirm_token,'tok-2');
  assert.equal(h.counts.papers,1);

  // Non-409 failures keep the panel and re-enable the inputs for a retry.
  h=harness({previews:[preview()],purgeError:Object.assign(new Error('disk'),{status:500})});
  await openPurge(h);
  type(h,'삭제');await submit(h);
  assert.deepEqual(h.errors,['disk']);assert.equal(h.nodes['purge-confirm-text'].disabled,false);
  assert.equal(h.nodes['purge-submit'].disabled,false);
  assert.equal(h.counts.projects,0);
}
main().catch(error=>{console.error(error);process.exitCode=1});
