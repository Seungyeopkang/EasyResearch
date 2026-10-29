'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const histStart=source.indexOf('async function loadOcrHistory('),histEnd=source.indexOf('\nfunction extractionWarning(',histStart);
const blockStart=source.indexOf('try{const data=await api(`/api/papers/',source.indexOf("$('#ocr-language').value=state.ocrLanguage"));
const blockEnd=source.indexOf('}catch(err){if(state.readerGeneration===readerGeneration',blockStart);
assert.ok(histStart>=0&&histEnd>histStart&&blockStart>=0&&blockEnd>blockStart);
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {resolve,reject,promise}}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function main(){
  const target={isConnected:true,innerHTML:'',textContent:''},state={paper:{id:'paper id'},page:2},selected=[],calls=[];
  let response=Promise.resolve({results:[{job_id:'old-en',language:'en',created_at:'2025'},
    {job_id:'new-ko',language:'ko',created_at:'2026'}],truncated:false});
  const history=vm.createContext({state,$:()=>target,esc:String,api:url=>{calls.push(url);return response},renderReader:id=>selected.push(id)});
  vm.runInContext(source.slice(histStart,histEnd)+'\nthis.load=loadOcrHistory;',history);
  await history.load('paper id',1);
  assert.equal(calls[0],'/api/papers/paper%20id/pages/1/ocr-results');
  assert.match(target.innerHTML,/en · 2025 결과 보기/);assert.match(target.innerHTML,/ko · 2026 결과 보기/);
  for(const id of ['old-en','new-ko'])target.onclick({target:{closest:()=>({dataset:{historyOcr:id}})}});
  assert.deepEqual(selected,['old-en','new-ko']);
  const late=deferred();response=late.promise;target.innerHTML='previous page';
  const loading=history.load('paper id',1);state.page=3;
  late.resolve({results:[{job_id:'late',language:'en'}]});await loading;
  assert.equal(target.innerHTML,'previous page','previous page history response must be ignored');
  target.onclick({target:{closest:()=>({dataset:{historyOcr:'old-en'}})}});
  assert.deepEqual(selected,['old-en','new-ko'],'old page controls must not select a result after navigation');

  const nodes={'page-text':{innerHTML:'',insertAdjacentHTML(){}},'evidence-form':{dataset:{}}};
  const renderState={paper:{id:'paper'},page:2,readerGeneration:0};
  const pending={old:deferred(),new:deferred()};
  const render=vm.createContext({state:renderState,$:id=>nodes[id.slice(1)],esc:String,
    api:async url=>url.startsWith('/api/ocr-results/')?pending[url.split('/').pop()].promise:{status:'extracted',text:'page'}});
  vm.runInContext(`async function display(p,n,preferredOcrJobId){const readerGeneration=state.readerGeneration=(state.readerGeneration||0)+1;${source.slice(blockStart,blockEnd)}}catch(err){throw err}};this.display=display;`,render);
  const older=render.display({id:'paper'},2,'old');const newer=render.display({id:'paper'},2,'new');await tick();
  pending.new.resolve({paper_id:'paper',page_index:1,job_id:'new',language:'ko',text:'new result'});await newer;
  pending.old.resolve({paper_id:'paper',page_index:1,job_id:'old',language:'en',text:'old result'});await older;
  assert.equal(nodes['evidence-form'].dataset.ocrJobId,'new');assert.match(nodes['page-text'].innerHTML,/new result/);
  assert.doesNotMatch(nodes['page-text'].innerHTML,/old result/);
  const pageLate=deferred();pending.old=pageLate;const pageLoading=render.display({id:'paper'},2,'old');await tick();
  renderState.page=3;pageLate.resolve({paper_id:'paper',page_index:1,job_id:'old',language:'en',text:'late old page'});await pageLoading;
  assert.equal(nodes['evidence-form'].dataset.ocrJobId,'new');assert.doesNotMatch(nodes['page-text'].innerHTML,/late old page/);
}
main().catch(error=>{console.error(error);process.exitCode=1});
