'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','..','apps','web','app.js'),'utf8');
const begin=source.indexOf("$('#ocr-language').value=state.ocrLanguage"),end=source.indexOf(';try{const data=await api',begin);
const runBegin=source.indexOf('async function runOcr('),runEnd=source.indexOf('\nasync function patchPaper(',runBegin);
const labelBegin=source.indexOf('function ocrErrorLabel('),labelEnd=source.indexOf('\nfunction extractionWarning(',labelBegin);
assert.ok(begin>=0&&end>begin&&runBegin>=0&&runEnd>runBegin&&labelBegin>=0&&labelEnd>labelBegin);
const code=`function attach(p,n){${source.slice(begin,end)}}\n${source.slice(labelBegin,labelEnd)}\n${source.slice(runBegin,runEnd)}\nthis.attach=attach;`;
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{resolve,reject,promise}}
function harness(){
  let nodes={},postResult,job={status:'completed'};const requests=[],notifications=[],errors=[],renderedJobIds=[];
  const state={view:'library',paper:{id:'paper space'},page:3,ocrLanguage:null};
  const ctx=vm.createContext({state,$:name=>nodes[name.slice(1)],
    post:(path,payload)=>{requests.push({path,payload:JSON.parse(JSON.stringify(payload))});return postResult.promise},
    api:async()=>job,notify:(...x)=>notifications.push(x),error:e=>errors.push(e.message),
    setTimeout:fn=>{fn()},renderReader:async jobId=>{renderedJobIds.push(jobId);render()}});
  vm.runInContext(code,ctx);
  function render(){
    for(const node of Object.values(nodes))node.isConnected=false;
    nodes={'ocr-language':{value:'',disabled:false,isConnected:true},'page-ocr':{disabled:false,isConnected:true},'ocr-history':{isConnected:true},
      'page-text':{innerHTML:'기존 OCR 텍스트',isConnected:true},'evidence-form':{dataset:{ocrJobId:'previous-job'},isConnected:true}};
    ctx.attach(state.paper,state.page);
  }
  render();
  return {state,requests,notifications,errors,renderedJobIds,get nodes(){return nodes},render,setJob(value){job=value},
    choose(value){nodes['ocr-language'].value=value;nodes['ocr-language'].onchange({target:nodes['ocr-language']})},
    request(){postResult=deferred();const run=nodes['page-ocr'].onclick();return{...postResult,run}}};
}
async function main(){
  for(const code of ['ko','en','ja','zh-Hans','zh-Hant'])assert.ok(source.includes(`<option value="${code}">`));
  const ui=harness();assert.equal(ui.nodes['ocr-language'].value,'ko');ui.choose('en');
  const failure=ui.request();assert.equal(ui.nodes['page-ocr'].disabled,true);assert.equal(ui.nodes['ocr-language'].disabled,true);
  assert.equal(ui.requests[0].path,'/api/papers/paper%20space/pages/2/ocr');assert.deepEqual(ui.requests[0].payload,{language:'en'});
  ui.render();assert.equal(ui.nodes['page-ocr'].disabled,true,'same page stays blocked after rerender');
  assert.equal(ui.nodes['ocr-language'].disabled,true);await ui.nodes['page-ocr'].onclick();
  assert.equal(ui.requests.length,1,'pending page ignores duplicate OCR request');
  failure.reject(Error('OCR 요청 실패'));await failure.run;
  assert.equal(ui.nodes['page-ocr'].disabled,false);assert.equal(ui.nodes['ocr-language'].disabled,false);
  assert.equal(ui.nodes['ocr-language'].value,'en');assert.deepEqual(ui.errors,['OCR 요청 실패']);
  ui.render();assert.equal(ui.nodes['ocr-language'].value,'en','selected language survives a reader rerender');
  ui.choose('ja');const success=ui.request();success.resolve({job_id:'job'});await success.run;
  assert.equal(ui.nodes['ocr-language'].value,'ja','completion rerender retains chosen language');
  assert.deepEqual(ui.renderedJobIds,['job'],'completed result is selected by its own job ID');
  assert.equal(ui.nodes['page-ocr'].disabled,false);assert.equal(ui.nodes['ocr-language'].disabled,false);
  assert.ok(ui.notifications.some(([text])=>text.includes('OCR 결과를 불러왔습니다')));

  const unavailable=harness();unavailable.choose('en');unavailable.setJob({status:'failed',error:'language_unavailable'});
  const failed=unavailable.request();failed.resolve({job_id:'failed-job'});await failed.run;
  assert.ok(unavailable.notifications.some(([text,kind])=>text.includes('선택한 OCR 언어가 Windows에 설치되어 있지 않습니다')&&kind==='warning'));
  assert.equal(unavailable.nodes['page-text'].innerHTML,'기존 OCR 텍스트');
  assert.equal(unavailable.nodes['evidence-form'].dataset.ocrJobId,'previous-job');
  assert.deepEqual(unavailable.renderedJobIds,[],'failure must not replace the previously displayed OCR result');
  assert.equal(unavailable.nodes['ocr-language'].disabled,false);assert.equal(unavailable.nodes['page-ocr'].disabled,false);

  const resultStart=source.indexOf('try{const data=await api(`/api/papers/',begin);
  const resultEnd=source.indexOf("}catch(err){if(state.readerGeneration===readerGeneration",resultStart);
  assert.ok(resultStart>=0&&resultEnd>resultStart,'OCR result display block must exist');
  const nodes={'page-text':{innerHTML:'',insertAdjacentHTML(){}},'evidence-form':{dataset:{}}},calls=[];
  const actual=vm.createContext({state:{paper:{id:'paper'},page:3,readerGeneration:1},$:id=>nodes[id.slice(1)],esc:String,
    api:async url=>{calls.push(url);return url.startsWith('/api/ocr-results/')?
      {job_id:'chosen job',paper_id:'paper',page_index:2,language:'en',text:'chosen OCR content'}:
      {status:'extracted',text:'page text',ocr:{job_id:'newer job',language:'ko',text:'other OCR content'}}}});
  vm.runInContext(`async function display(p,n,preferredOcrJobId){const readerGeneration=state.readerGeneration;${source.slice(resultStart,resultEnd)}}catch(err){throw err}};this.display=display;`,actual);
  await actual.display({id:'paper'},3,'chosen job');
  assert.equal(calls[1],'/api/ocr-results/chosen%20job');
  assert.equal(nodes['evidence-form'].dataset.ocrJobId,'chosen job');
  assert.match(nodes['page-text'].innerHTML,/OCR · en/);
  assert.match(nodes['page-text'].innerHTML,/chosen OCR content/);
  assert.doesNotMatch(nodes['page-text'].innerHTML,/other OCR content/);
}
main().catch(error=>{console.error(error);process.exitCode=1});
