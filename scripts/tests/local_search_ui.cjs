'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'apps', 'web', 'app.js'), 'utf8');
const start = source.indexOf("  let localSerial=0,localQuery=''");
const end = source.indexOf('\n}', start);
assert.ok(start >= 0 && end > start, 'library search UI block must be present');
const code = `function attach(){${source.slice(start, end)}\n}\nthis.attach=attach;`;
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; }
function page(first, last, next) {
  return {results:Array.from({length:last-first},(_,n)=>({paper_id:`paper-${n+first}`,title:`Title ${n+first}`,
    kind:n+first===205?'page':'evidence',page_index:n+first===205?4:null,scope:'shared',snippet:`snippet ${n+first}`})),
    next_offset:next,total:206,notice:'notice'};
}
function harness(api) {
  const state={projectId:'project-a'}, notices=[], opened=[];
  const nodes={'local-search-results':{isConnected:true,innerHTML:'',textContent:''},
    'local-search-input':{value:'needle'},'local-search-form':{}};
  const context=vm.createContext({state,api,$:s=>nodes[s.slice(1)],esc:String,
    notify:(...args)=>notices.push(args),openPaper:async(...args)=>{opened.push(args)},error:e=>{throw e}});
  vm.runInContext(code,context);context.attach();
  return {state,nodes,notices,opened,submit:()=>nodes['local-search-form'].onsubmit({preventDefault(){}}),
    more:()=>nodes['local-search-results'].onclick({target:{closest:q=>q==='[data-local-more]'?{}:null}}),
    select:(id,page)=>nodes['local-search-results'].onclick({target:{closest:q=>q==='[data-local-paper]'?{dataset:{localPaper:id,...(page?{localPage:page}:{})}}:null}})};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));

async function main() {
  const calls=[];
  const ui=harness(async url=>{calls.push(url);return calls.length===1?page(0,200,200):page(200,206,null)});
  await ui.submit();
  assert.match(calls[0],/project-a\/library-search\?q=needle&offset=0$/);
  assert.match(ui.nodes['local-search-results'].innerHTML,/200 \/ 206개 표시/);
  assert.match(ui.nodes['local-search-results'].innerHTML,/Title 0/);
  assert.match(ui.nodes['local-search-results'].innerHTML,/data-local-more/);
  ui.more();await tick();
  assert.match(calls[1],/offset=200$/);
  assert.match(ui.nodes['local-search-results'].innerHTML,/206 \/ 206개 표시/);
  assert.match(ui.nodes['local-search-results'].innerHTML,/Title 0/);
  assert.match(ui.nodes['local-search-results'].innerHTML,/Title 205 · 파일 5쪽/);
  assert.doesNotMatch(ui.nodes['local-search-results'].innerHTML,/data-local-more/);
  ui.select('paper-205','5');ui.select('paper-1');await tick();
  assert.deepEqual(ui.opened,[['paper-205',5],['paper-1',null]]);

  let requests=0;
  const failure=harness(async()=>{if(++requests===1)return page(0,200,200);throw Error('network')});
  await failure.submit();const previous=failure.nodes['local-search-results'].innerHTML;
  failure.more();await tick();
  assert.equal(failure.nodes['local-search-results'].innerHTML,previous,'failed next page keeps existing results');
  assert.equal(failure.notices.length,1);

  const pending=deferred(),stale=harness(()=>pending.promise);
  const waiting=stale.submit();stale.state.projectId='project-b';pending.resolve(page(0,200,200));await waiting;
  assert.equal(stale.nodes['local-search-results'].innerHTML,'','old project success must not appear');

  const rejected=deferred(),staleFailure=harness(()=>rejected.promise);
  const waitingFailure=staleFailure.submit();staleFailure.state.projectId='project-b';rejected.reject(Error('old project failure'));await waitingFailure;
  assert.equal(staleFailure.nodes['local-search-results'].textContent,'검색 중입니다.','old project errors must not replace results');
  assert.equal(staleFailure.notices.length,0,'old project errors must not create a notification');

  const moreRejected=deferred();let count=0;
  const staleMore=harness(()=>++count===1?Promise.resolve(page(0,200,200)):moreRejected.promise);
  await staleMore.submit();const oldHtml=staleMore.nodes['local-search-results'].innerHTML;
  staleMore.more();staleMore.state.projectId='project-b';moreRejected.reject(Error('old page failure'));await tick();
  assert.equal(staleMore.nodes['local-search-results'].innerHTML,oldHtml);
  assert.equal(staleMore.notices.length,0,'old project next-page errors must not create a notification');
}
main().catch(error=>{console.error(error);process.exitCode=1});
