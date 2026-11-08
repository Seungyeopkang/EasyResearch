'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'apps', 'web', 'app.js'), 'utf8');
const code = source.slice(source.indexOf('async function projectNoteTabId('), source.indexOf('\nfunction editMetadata('));
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return {resolve,promise}; }
function memoryStorage() {
  const map = new Map();
  return { get length() { return map.size; }, key(i) { return [...map.keys()][i] || null; },
    getItem(k) { return map.has(k) ? map.get(k) : null; }, setItem(k,v) { map.set(k,String(v)); }, removeItem(k) { map.delete(k); } };
}
function lockManager() {
  const held=new Set();
  return {request(name,_options,cb){if(held.has(name))return Promise.resolve(cb(null));held.add(name);return Promise.resolve(cb({name}));}};
}
function setup(api, localStorage, tabId='tab-1', locks=lockManager(), randomId=tabId+'-new') {
  const ids=['project-paper-note','project-note-status','save-project-note','project-note-conflict','project-note-latest','project-note-review','project-note-recovery','project-note-drafts','project-note-recover','edit-metadata','duplicates','pdf-versions','unlink-paper','trash-paper','tab-record','reading-status','classify-paper','fetch-topics','paper-categories','paper-projects','paper-topics','add-project-select','add-project-link'];
  const els = Object.fromEntries(ids.map(id => [id, {value:'',disabled:false,hidden:true,isConnected:true,children:[],insertAdjacentHTML(){},append(x){this.children.push(x);if(!this.value)this.value=x.value}}]));
  els['project-paper-note'].disabled=true;els['save-project-note'].disabled=true;
  const head={insertAdjacentHTML(){}};
  const sessionStorage=memoryStorage(); sessionStorage.setItem('easyresearch-note-tab',tabId);
  const ctx=vm.createContext({state:{projectId:'project',projects:[{id:'project',name:'P'}],workspaceScope:'scope'},
    $: s => s==='#content .page-head'?head:els[s.slice(1)] || null, esc:String, api, localStorage, sessionStorage,
    navigator:{locks},crypto:{randomUUID:()=>randomId},document:{createElement:()=>({})},error(){},notify(){},console});
  vm.runInContext(code+'\nthis.setup=setupPaperActions;',ctx);
  return {els,run:()=>ctx.setup({id:'paper',file_id:'file',projects:[{id:'project',name:'P'}]})};
}

async function main() {
  const storage=memoryStorage(),pending=deferred();let getCount=0,putCount=0;
  const api=async (_path,options)=>{
    if (!options) { getCount++; return getCount===1?pending.promise:{note:'다른 창 메모',revision:'b'.repeat(64)}; }
    putCount++;const body=JSON.parse(options.body);
    if(putCount===1){assert.equal(body.expected_revision,'a'.repeat(64));const e=new Error('conflict');e.status=409;throw e;}
    assert.equal(body.expected_revision,'b'.repeat(64));assert.equal(body.note,'내 입력');return {revision:'c'.repeat(64)};
  };
  const view=setup(api,storage);const loading=view.run();
  assert.equal(view.els['project-paper-note'].disabled,true,'typing is blocked while GET is pending');
  pending.resolve({note:'처음 메모',revision:'a'.repeat(64)});await loading;
  const note=view.els['project-paper-note'];assert.equal(note.disabled,false);note.value='내 입력';note.oninput();
  const key='easyresearch-project-note:scope:project:paper:draft:tab-1';
  assert.equal(JSON.parse(storage.getItem(key)).baseRevision,'a'.repeat(64));
  await view.els['save-project-note'].onclick();
  assert.equal(note.value,'내 입력');assert.equal(view.els['save-project-note'].disabled,true);
  assert.equal(view.els['project-note-latest'].value,'다른 창 메모');assert.ok(storage.getItem(key));
  view.els['project-note-review'].onclick();assert.equal(view.els['save-project-note'].disabled,false);
  await view.els['save-project-note'].onclick();assert.equal(storage.getItem(key),null);

  const legacy=memoryStorage(),base='easyresearch-project-note:scope:project:paper';legacy.setItem(base,'옛 임시 메모');
  const old=setup(async()=>({note:'현재 저장',revision:'d'.repeat(64)}),legacy,'tab-2');await old.run();
  assert.equal(old.els['project-note-recovery'].hidden,false);
  await old.els['project-note-recover'].onclick();
  assert.equal(old.els['project-paper-note'].value,'옛 임시 메모');
  assert.equal(old.els['project-note-latest'].value,'현재 저장');assert.equal(old.els['save-project-note'].disabled,true);
  assert.ok(legacy.getItem(base),'legacy draft remains until a successful save');

  const restored=memoryStorage();restored.setItem(`${base}:draft:tab-3`,JSON.stringify({value:'이전 입력',baseRevision:'e'.repeat(64)}));
  const stale=setup(async()=>({note:'변경된 저장',revision:'f'.repeat(64)}),restored,'tab-3');await stale.run();
  assert.equal(stale.els['project-paper-note'].value,'이전 입력');assert.equal(stale.els['save-project-note'].disabled,true);
  assert.equal(stale.els['project-note-latest'].value,'변경된 저장');

  const sharedStorage=memoryStorage(),sharedLocks=lockManager(),read=async()=>({note:'',revision:'a'.repeat(64)});
  const original=setup(read,sharedStorage,'copied-tab',sharedLocks,'first-new');await original.run();
  const duplicate=setup(read,sharedStorage,'copied-tab',sharedLocks,'duplicate-new');await duplicate.run();
  original.els['project-paper-note'].value='원본 탭 입력';original.els['project-paper-note'].oninput();
  duplicate.els['project-paper-note'].value='복제 탭 입력';duplicate.els['project-paper-note'].oninput();
  assert.equal(JSON.parse(sharedStorage.getItem(`${base}:draft:copied-tab`)).value,'원본 탭 입력');
  assert.equal(JSON.parse(sharedStorage.getItem(`${base}:draft:duplicate-new`)).value,'복제 탭 입력');
}
main().catch(error=>{console.error(error);process.exitCode=1});
