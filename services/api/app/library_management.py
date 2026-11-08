"""Recoverable local library operations. Original files are never removed here."""
from fastapi import APIRouter, HTTPException, Response, File, Form, UploadFile, Query
from fastapi.responses import FileResponse
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pydantic import BaseModel, Field
from . import storage

router = APIRouter()
MAX_DUPLICATE_CANDIDATES = 200
MAX_DUPLICATE_SIMILARITY_CHECKS = 2000

class ProjectNote(BaseModel):
    note: str = Field(default='', max_length=100000)
    expected_revision: str = Field(min_length=64, max_length=64, pattern=r'^[0-9a-f]{64}$')

class VersionRevision(BaseModel):
    expected_revision: str = Field(min_length=64, max_length=64, pattern=r'^[0-9a-f]{64}$')

class VersionLabel(VersionRevision):
    label: str = Field(max_length=200)

def version_revision(row):
    # Label and visibility are both part of the version's state. Check the
    # token inside a write transaction so another window cannot silently win.
    if row['stored_revision']:
        return row['stored_revision']
    data = json.dumps([row['id'], row['file_id'], row['label'], row['deleted_at']],
                      ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def version_row(con, paper_id, version_id):
    return con.execute('''SELECT v.id,v.paper_id,v.file_id,v.label,v.created_at,
             t.deleted_at,p.deleted_at AS paper_deleted_at,f.sha256,f.size,s.revision AS stored_revision
             FROM paper_versions v JOIN papers p ON p.id=v.paper_id
             JOIN files f ON f.id=v.file_id
             LEFT JOIN paper_version_trash t ON t.version_id=v.id
             LEFT JOIN paper_version_state s ON s.version_id=v.id
             WHERE v.paper_id=? AND v.id=?''', (paper_id, version_id)).fetchone()

def advance_version_revision(con, version_id):
    revision = hashlib.sha256(storage.new_id().encode('ascii')).hexdigest()
    con.execute('''INSERT INTO paper_version_state(version_id,revision) VALUES(?,?)
                   ON CONFLICT(version_id) DO UPDATE SET revision=excluded.revision''', (version_id,revision))

def version_item(row):
    item = dict(row)
    item.pop('paper_deleted_at', None)
    item.pop('stored_revision', None)
    item['revision'] = version_revision(row)
    item['url'] = f'/api/papers/{row["paper_id"]}/versions/{row["id"]}/file'
    return item

def note_revision(row):
    data = b'present\0' + row['note'].encode('utf-8') if row else b'missing'
    return hashlib.sha256(data).hexdigest()

def require_link(con, project_id, paper_id):
    if not con.execute("""SELECT 1 FROM project_papers pp JOIN projects pr ON pr.id=pp.project_id
          JOIN papers p ON p.id=pp.paper_id WHERE pp.project_id=? AND pp.paper_id=?
          AND p.deleted_at IS NULL AND pr.id NOT IN (SELECT project_id FROM project_trash)""",
          (project_id, paper_id)).fetchone():
        raise HTTPException(404, '프로젝트에 연결된 논문을 찾을 수 없습니다.')

def attach_paper(con, project_id, paper_id):
    """Re-adding a removed link restores its original reading state."""
    old = con.execute('SELECT * FROM link_trash WHERE project_id=? AND paper_id=?', (project_id, paper_id)).fetchone()
    if old:
        con.execute('INSERT OR IGNORE INTO project_papers(project_id,paper_id,reading_status,last_page) VALUES(?,?,?,?)',
                    (project_id,paper_id,old['reading_status'],old['last_page']))
        con.execute('DELETE FROM link_trash WHERE id=?', (old['id'],))
    else:
        con.execute('INSERT OR IGNORE INTO project_papers(project_id,paper_id) VALUES(?,?)', (project_id,paper_id))

@router.get('/api/projects/{project_id}/papers/{paper_id}/note')
def get_note(project_id: str, paper_id: str):
    with storage.transaction() as con:
        require_link(con, project_id, paper_id)
        row = con.execute('SELECT note,updated_at FROM project_paper_notes WHERE project_id=? AND paper_id=?', (project_id,paper_id)).fetchone()
        return {'project_id':project_id,'paper_id':paper_id,'note':row['note'] if row else '', 'updated_at':row['updated_at'] if row else None, 'revision':note_revision(row)}

@router.put('/api/projects/{project_id}/papers/{paper_id}/note')
def put_note(project_id: str, paper_id: str, payload: ProjectNote):
    with storage.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        require_link(con, project_id, paper_id)
        current = con.execute('SELECT note FROM project_paper_notes WHERE project_id=? AND paper_id=?', (project_id,paper_id)).fetchone()
        if note_revision(current) != payload.expected_revision:
            raise HTTPException(409, '다른 창에서 메모가 변경되었습니다. 최신 내용과 입력 내용을 확인해 주세요.')
        con.execute("""INSERT INTO project_paper_notes(project_id,paper_id,note) VALUES(?,?,?)
           ON CONFLICT(project_id,paper_id) DO UPDATE SET note=excluded.note,updated_at=CURRENT_TIMESTAMP""", (project_id,paper_id,payload.note))
        row = con.execute('SELECT * FROM project_paper_notes WHERE project_id=? AND paper_id=?', (project_id,paper_id)).fetchone()
        return {**dict(row), 'revision':note_revision(row)}

@router.delete('/api/projects/{project_id}/papers/{paper_id}', status_code=204)
def detach(project_id: str, paper_id: str):
    with storage.transaction() as con:
        require_link(con, project_id, paper_id)
        if con.execute("""SELECT 1 FROM ideas i JOIN idea_evidence ie ON ie.idea_id=i.id
             JOIN evidence e ON e.id=ie.evidence_id WHERE i.project_id=? AND e.paper_id=? LIMIT 1""", (project_id,paper_id)).fetchone():
            raise HTTPException(409, '이 프로젝트의 아이디어가 논문 근거를 사용합니다. 아이디어 연결을 먼저 해제해 주세요.')
        link = con.execute('SELECT * FROM project_papers WHERE project_id=? AND paper_id=?', (project_id,paper_id)).fetchone()
        con.execute('INSERT INTO link_trash(id,project_id,paper_id,reading_status,last_page) VALUES(?,?,?,?,?)',
                    (storage.new_id(),project_id,paper_id,link['reading_status'],link['last_page']))
        con.execute('DELETE FROM project_papers WHERE project_id=? AND paper_id=?', (project_id,paper_id))
    return Response(status_code=204)

@router.delete('/api/projects/{project_id}', status_code=204)
def trash_project(project_id: str):
    with storage.transaction() as con:
        if not con.execute('SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)', (project_id,)).fetchone():
            raise HTTPException(404, '프로젝트를 찾을 수 없습니다.')
        con.execute('INSERT INTO project_trash(project_id) VALUES(?)', (project_id,))
    return Response(status_code=204)

@router.delete('/api/papers/{paper_id}', status_code=204)
def trash_paper(paper_id: str):
    with storage.transaction() as con:
        if not con.execute('UPDATE papers SET deleted_at=CURRENT_TIMESTAMP WHERE id=? AND deleted_at IS NULL', (paper_id,)).rowcount:
            raise HTTPException(404, '논문을 찾을 수 없습니다.')
    return Response(status_code=204)

@router.delete('/api/evidence/{evidence_id}', status_code=204)
def trash_evidence(evidence_id: str):
    with storage.transaction() as con:
        if not con.execute('SELECT 1 FROM evidence WHERE id=? AND id NOT IN (SELECT evidence_id FROM evidence_trash)', (evidence_id,)).fetchone():
            raise HTTPException(404, '근거를 찾을 수 없습니다.')
        # Existing idea links are retained, and their user must explicitly remove
        # the reference before hiding a record from normal library views.
        if con.execute('SELECT 1 FROM idea_evidence WHERE evidence_id=?', (evidence_id,)).fetchone():
            raise HTTPException(409, '아이디어에 연결된 근거입니다. 연결을 먼저 해제해 주세요.')
        con.execute('INSERT INTO evidence_trash(evidence_id) VALUES(?)', (evidence_id,))
    return Response(status_code=204)

@router.get('/api/trash')
def list_trash():
    with storage.transaction() as con:
        project_rows = con.execute("""SELECT p.id,p.name,t.deleted_at,
           (SELECT count(*) FROM project_papers pp WHERE pp.project_id=p.id) AS paper_count
           FROM project_trash t JOIN projects p ON p.id=t.project_id ORDER BY t.deleted_at DESC""").fetchall()
        paper_rows = con.execute("""SELECT p.id,p.title,p.deleted_at,
           (SELECT count(*) FROM project_papers pp WHERE pp.paper_id=p.id) AS project_count,
           (SELECT count(*) FROM evidence e WHERE e.paper_id=p.id) AS evidence_count
           FROM papers p WHERE p.deleted_at IS NOT NULL ORDER BY p.deleted_at DESC""").fetchall()
        evidence_rows = con.execute("""SELECT e.id,e.paper_id,e.page_index,e.quote,e.note,p.title AS paper_title,t.deleted_at,
           (SELECT count(*) FROM idea_evidence i WHERE i.evidence_id=e.id) AS idea_count
           FROM evidence_trash t JOIN evidence e ON e.id=t.evidence_id JOIN papers p ON p.id=e.paper_id
           ORDER BY t.deleted_at DESC""").fetchall()
        link_rows = con.execute("""SELECT t.id,t.project_id,t.paper_id,t.deleted_at,p.title AS paper_title,
           pr.name AS project_name FROM link_trash t JOIN papers p ON p.id=t.paper_id JOIN projects pr ON pr.id=t.project_id
           ORDER BY t.deleted_at DESC""").fetchall()
        return {'projects':[dict(x) for x in project_rows], 'papers':[dict(x) for x in paper_rows],
                'evidence':[dict(x) for x in evidence_rows], 'links':[dict(x) for x in link_rows]}

@router.post('/api/trash/{kind}/{item_id}/restore')
def restore(kind: str, item_id: str):
    with storage.transaction() as con:
        if kind == 'projects':
            if not con.execute('DELETE FROM project_trash WHERE project_id=?', (item_id,)).rowcount:
                raise HTTPException(404, '휴지통에서 프로젝트를 찾을 수 없습니다.')
        elif kind == 'papers':
            if not con.execute('UPDATE papers SET deleted_at=NULL WHERE id=? AND deleted_at IS NOT NULL', (item_id,)).rowcount:
                raise HTTPException(404, '휴지통에서 논문을 찾을 수 없습니다.')
        elif kind == 'evidence':
            row = con.execute('SELECT p.deleted_at FROM evidence e JOIN papers p ON p.id=e.paper_id JOIN evidence_trash t ON t.evidence_id=e.id WHERE e.id=?', (item_id,)).fetchone()
            if not row: raise HTTPException(404, '휴지통에서 근거를 찾을 수 없습니다.')
            if row['deleted_at'] is not None: raise HTTPException(409, '논문을 먼저 복구해 주세요.')
            con.execute('DELETE FROM evidence_trash WHERE evidence_id=?', (item_id,))
        elif kind == 'links':
            row = con.execute('SELECT * FROM link_trash WHERE id=?', (item_id,)).fetchone()
            if not row: raise HTTPException(404, '휴지통에서 연결을 찾을 수 없습니다.')
            project_active = con.execute('SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)', (row['project_id'],)).fetchone()
            paper_active = con.execute('SELECT 1 FROM papers WHERE id=? AND deleted_at IS NULL', (row['paper_id'],)).fetchone()
            if not project_active or not paper_active: raise HTTPException(409, '프로젝트와 논문을 먼저 복구해 주세요.')
            attach_paper(con,row['project_id'],row['paper_id'])
        else:
            raise HTTPException(404, '알 수 없는 휴지통 항목입니다.')
    return {'kind':kind,'id':item_id,'status':'restored'}

@router.get('/api/projects/{project_id}/library-search')
def library_search(project_id: str, q: str, offset: int = Query(default=0, ge=0),
                   limit: int = Query(default=200, ge=1, le=200)):
    q = q.strip()
    if not q or len(q) > 200:
        raise HTTPException(422, '검색어를 1~200자로 입력해 주세요.')
    with storage.transaction() as con:
        if not con.execute('SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)', (project_id,)).fetchone():
            raise HTTPException(404, '프로젝트를 찾을 수 없습니다.')
        papers = con.execute('''SELECT p.* FROM papers p JOIN project_papers pp ON pp.paper_id=p.id
            WHERE pp.project_id=? AND p.deleted_at IS NULL ORDER BY p.title,p.id''', (project_id,))
        results=[]
        total=0
        incomplete_pages=0
        unknown_papers=0
        needle=q.casefold()
        def add(paper, kind, text, page_index=None, evidence_id=None, scope='shared'):
            nonlocal total
            if not text: return
            i=text.casefold().find(needle)
            if i<0: return
            if offset <= total < offset+limit:
                start=max(0,i-60)
                result={'paper_id':paper['id'],'title':paper['title'],'kind':kind,
                        'snippet':text[start:min(len(text),i+len(q)+100)],
                        'page_index':page_index,'scope':scope}
                if evidence_id is not None: result['evidence_id']=evidence_id
                results.append(result)
            total+=1
        for paper in papers:
            import json
            authors=' '.join(json.loads(paper['authors'] or '[]'))
            add(paper,'metadata',' '.join(str(x or '') for x in (paper['title'],authors,paper['year'],paper['doi'])))
            note=con.execute('SELECT note FROM project_paper_notes WHERE project_id=? AND paper_id=?', (project_id,paper['id'])).fetchone()
            if note: add(paper,'project_note',note['note'],scope='project')
            for e in con.execute('''SELECT * FROM evidence WHERE paper_id=? AND id NOT IN
                (SELECT evidence_id FROM evidence_trash) ORDER BY page_index,id''',(paper['id'],)):
                add(paper,'evidence',e['quote']+'\n'+e['note'],e['page_index'],e['id'])
            complete=0
            for page in con.execute('SELECT page_index,text,status FROM pages WHERE paper_id=? ORDER BY page_index',(paper['id'],)):
                if page['status']=='extracted' and page['text'].strip():
                    complete+=1
                add(paper,'page',page['text'],page['page_index'])
            if paper['file_id']:
                if paper['page_count'] is None: unknown_papers+=1
                else: incomplete_pages+=max(0,paper['page_count']-complete)
            for ocr in con.execute('''SELECT o.* FROM ocr_pages o WHERE o.paper_id=? AND o.rowid=(SELECT max(x.rowid)
                 FROM ocr_pages x WHERE x.paper_id=o.paper_id AND x.page_index=o.page_index) ORDER BY o.page_index''',(paper['id'],)):
                add(paper,'ocr',ocr['text'],ocr['page_index'])
        next_offset=offset+limit if offset+limit<total else None
        return {'results':results, 'truncated':next_offset is not None,
                'offset':offset, 'limit':limit, 'total':total, 'next_offset':next_offset,
                'incomplete_pages':incomplete_pages, 'unknown_papers':unknown_papers,
                'notice':'추출되지 않은 페이지와 OCR 오류로 검색 결과가 누락될 수 있습니다.'}

@router.get('/api/papers/{paper_id}/duplicate-candidates')
def duplicate_candidates(paper_id: str):
    with storage.transaction() as con:
        paper=con.execute('SELECT * FROM papers WHERE id=? AND deleted_at IS NULL',(paper_id,)).fetchone()
        if not paper: raise HTTPException(404, '논문을 찾을 수 없습니다.')
        def normalize(value): return ' '.join((value or '').casefold().split())
        title=normalize(paper['title'])
        doi=normalize(paper['doi'])
        def words(value):
            return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', value or '').casefold()).strip()
        def author_names(raw):
            try:
                names=json.loads(raw or '[]')
                if not isinstance(names,list): return set()
                return {words(name) for name in names if isinstance(name,str) and len(words(name)) >= 3}
            except (TypeError,ValueError):
                return set()
        canonical_title=words(paper['title'])
        title_words=set(canonical_title.split())
        authors=author_names(paper['authors'])
        exact_doi,exact_title,similar=[],[],[]
        found=0
        similarity_checked=0
        similarity_limited=False
        for other in con.execute('SELECT id,title,authors,year,doi FROM papers WHERE id<>? AND deleted_at IS NULL ORDER BY id',(paper_id,)):
            reasons=[]
            if doi and doi==normalize(other['doi']): reasons.append('doi')
            if title and title==normalize(other['title']): reasons.append('title')
            rank='doi' if 'doi' in reasons else 'title'
            if not reasons and len(canonical_title)>=20 and len(title_words)>=3 and authors:
                other_title=words(other['title'])
                other_words=set(other_title.split())
                shared=authors.intersection(author_names(other['authors']))
                year=paper['year'] if isinstance(paper['year'],int) else None
                other_year=other['year'] if isinstance(other['year'],int) else None
                valid_years=(year is None or other_year is None or abs(year-other_year)<=1)
                union=title_words | other_words
                overlap=len(title_words & other_words)/len(union) if union else 0
                if len(other_title)>=20 and len(other_words)>=3 and shared and valid_years and overlap>=0.6:
                    if similarity_checked>=MAX_DUPLICATE_SIMILARITY_CHECKS:
                        similarity_limited=True
                    else:
                        similarity_checked+=1
                        left,right=title_words-other_words,other_words-title_words
                        # Changed technical terms can be different papers even
                        # when the surrounding title is nearly identical.
                        comparable=(not left or not right or
                            (len(left)<=12 and len(right)<=12 and
                             all(any(SequenceMatcher(None,a,b,autojunk=False).ratio()>=0.78 for b in right) for a in left) and
                             all(any(SequenceMatcher(None,a,b,autojunk=False).ratio()>=0.78 for a in left) for b in right)))
                        score=SequenceMatcher(None,canonical_title,other_title,autojunk=False).ratio() if comparable else 0
                        if score>=0.9:
                            year_reason=('year_unknown' if year is None or other_year is None else
                                         'year_same' if year==other_year else 'year_close')
                            reasons=['similar_title','shared_author',year_reason]
                            rank='similar'
            if reasons:
                found+=1
                target=exact_doi if rank=='doi' else exact_title if rank=='title' else similar
                if len(target)<MAX_DUPLICATE_CANDIDATES:
                    try:
                        other_authors=json.loads(other['authors'] or '[]')
                        if not isinstance(other_authors,list): other_authors=[]
                    except (TypeError,ValueError): other_authors=[]
                    target.append({'id':other['id'],'title':other['title'],'authors':other_authors,
                                   'year':other['year'],'doi':other['doi'],'reasons':reasons})
        return {'candidates':(exact_doi+exact_title+similar)[:MAX_DUPLICATE_CANDIDATES],
                'truncated':found>MAX_DUPLICATE_CANDIDATES,
                'similarity_limited':similarity_limited,
                'notice':'확정된 중복이 아닌 후보입니다. 원본과 서지정보를 비교하세요. 자동으로 병합하지 않습니다.'}

@router.get('/api/papers/{paper_id}/impact')
def paper_impact(paper_id: str):
    with storage.transaction() as con:
        p=con.execute('SELECT id,title FROM papers WHERE id=? AND deleted_at IS NULL',(paper_id,)).fetchone()
        if not p: raise HTTPException(404,'논문을 찾을 수 없습니다.')
        projects=[dict(row) for row in con.execute('''SELECT pr.id,pr.name FROM project_papers pp JOIN projects pr ON pr.id=pp.project_id
             WHERE pp.paper_id=? ORDER BY pr.name''',(paper_id,))]
        return {'paper_id':paper_id,'title':p['title'],'projects':projects,
                'evidence_count':con.execute('SELECT count(*) FROM evidence WHERE paper_id=?',(paper_id,)).fetchone()[0],
                'file_preserved':True,'message':'휴지통으로 이동해도 원본 PDF와 연결된 기록은 보존됩니다.'}

@router.get('/api/papers/{paper_id}/versions')
def paper_versions(paper_id: str):
    with storage.transaction() as con:
        paper=con.execute('SELECT id,file_id FROM papers WHERE id=? AND deleted_at IS NULL',(paper_id,)).fetchone()
        if not paper: raise HTTPException(404,'논문을 찾을 수 없습니다.')
        primary=con.execute('SELECT id,sha256,size FROM files WHERE id=?',(paper['file_id'],)).fetchone() if paper['file_id'] else None
        versions=[]
        trashed_versions=[]
        for row in con.execute('''SELECT v.id,v.paper_id,v.file_id,v.label,v.created_at,f.sha256,f.size,
                                   t.deleted_at,p.deleted_at AS paper_deleted_at,s.revision AS stored_revision FROM paper_versions v
                                   JOIN files f ON f.id=v.file_id JOIN papers p ON p.id=v.paper_id
                                   LEFT JOIN paper_version_trash t ON t.version_id=v.id
                                   LEFT JOIN paper_version_state s ON s.version_id=v.id
                                   WHERE v.paper_id=? ORDER BY v.created_at,v.id''',(paper_id,)):
            (trashed_versions if row['deleted_at'] is not None else versions).append(version_item(row))
        return {'primary':{'file_id':primary['id'],'sha256':primary['sha256'],'size':primary['size'],'url':f'/api/papers/{paper_id}/file'} if primary else None,
                'versions':versions,'trashed_versions':trashed_versions,
                'notice':'추가 버전은 보관과 별도 열람만 지원합니다. 근거는 기존 원본 PDF에 연결됩니다.'}

@router.post('/api/papers/{paper_id}/versions',status_code=201)
def add_paper_version(paper_id: str, file: UploadFile = File(...), label: str = Form(default='')):
    if len(label)>200: raise HTTPException(422,'버전 이름은 200자 이하여야 합니다.')
    with storage.transaction() as con:
        paper=con.execute('SELECT file_id FROM papers WHERE id=? AND deleted_at IS NULL',(paper_id,)).fetchone()
        if not paper: raise HTTPException(404,'논문을 찾을 수 없습니다.')
        if not paper['file_id']: raise HTTPException(422,'기존 원본 PDF를 먼저 연결해 주세요.')
    try:
        sha,size,key=storage.store_stream(file.file)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    finally:
        file.file.close()
    with storage.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        paper=con.execute('SELECT file_id FROM papers WHERE id=? AND deleted_at IS NULL',(paper_id,)).fetchone()
        if not paper: raise HTTPException(409,'논문 상태가 바뀌었습니다. 다시 시도해 주세요.')
        old=con.execute('SELECT id FROM files WHERE sha256=?',(sha,)).fetchone()
        fid=old['id'] if old else storage.new_id()
        if not storage.file_path(key).is_file():
            raise HTTPException(409,'PDF를 저장하는 중 파일이 정리되었습니다. 다시 등록해 주세요.')
        if not old: con.execute('INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)',(fid,sha,size,key))
        if paper['file_id']==fid:
            return {'duplicate':True,'primary':True,'file_id':fid,'sha256':sha,'notice':'기존 원본과 같은 파일입니다.'}
        existing=con.execute('SELECT id FROM paper_versions WHERE paper_id=? AND file_id=?',(paper_id,fid)).fetchone()
        if existing:
            row=version_row(con,paper_id,existing['id'])
            return {**version_item(row),'duplicate':True,'primary':False,
                    'trashed':row['deleted_at'] is not None,
                    'notice':'휴지통에 있는 버전입니다. 복구해 주세요.' if row['deleted_at'] is not None else '이미 추가된 버전입니다.'}
        version_id=storage.new_id()
        other=con.execute('''SELECT count(*) FROM papers p WHERE p.file_id=? AND p.id<>?''',(fid,paper_id)).fetchone()[0]
        con.execute('INSERT INTO paper_versions(id,paper_id,file_id,label) VALUES(?,?,?,?)',(version_id,paper_id,fid,label.strip()))
        return {'id':version_id,'duplicate':False,'primary':False,'file_id':fid,'sha256':sha,'other_papers':other,
                'revision':version_revision(version_row(con,paper_id,version_id)),
                'url':f'/api/papers/{paper_id}/versions/{version_id}/file',
                'notice':'기존 원본과 근거를 유지하고 추가 버전만 보관했습니다.'}

@router.patch('/api/papers/{paper_id}/versions/{version_id}')
def rename_paper_version(paper_id: str, version_id: str, payload: VersionLabel):
    with storage.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        row=version_row(con,paper_id,version_id)
        if not row or row['paper_deleted_at'] is not None or row['deleted_at'] is not None:
            raise HTTPException(404,'활성 PDF 버전을 찾을 수 없습니다.')
        if version_revision(row)!=payload.expected_revision:
            raise HTTPException(409,'다른 창에서 버전이 변경되었습니다. 다시 확인해 주세요.')
        con.execute('UPDATE paper_versions SET label=? WHERE id=?',(payload.label.strip(),version_id))
        advance_version_revision(con,version_id)
        return version_item(version_row(con,paper_id,version_id))

@router.delete('/api/papers/{paper_id}/versions/{version_id}')
def trash_paper_version(paper_id: str, version_id: str, payload: VersionRevision):
    with storage.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        row=version_row(con,paper_id,version_id)
        if not row or row['paper_deleted_at'] is not None:
            raise HTTPException(404,'PDF 버전을 찾을 수 없습니다.')
        if version_revision(row)!=payload.expected_revision:
            raise HTTPException(409,'다른 창에서 버전이 변경되었습니다. 다시 확인해 주세요.')
        if row['deleted_at'] is not None:
            raise HTTPException(409,'이미 휴지통에 있는 버전입니다.')
        con.execute('INSERT INTO paper_version_trash(version_id) VALUES(?)',(version_id,))
        advance_version_revision(con,version_id)
        return version_item(version_row(con,paper_id,version_id))

@router.post('/api/papers/{paper_id}/versions/{version_id}/restore')
def restore_paper_version(paper_id: str, version_id: str, payload: VersionRevision):
    with storage.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        row=version_row(con,paper_id,version_id)
        if not row:
            raise HTTPException(404,'휴지통에서 PDF 버전을 찾을 수 없습니다.')
        if row['paper_deleted_at'] is not None:
            raise HTTPException(409,'논문을 먼저 복구해 주세요.')
        if version_revision(row)!=payload.expected_revision:
            raise HTTPException(409,'다른 창에서 버전이 변경되었습니다. 다시 확인해 주세요.')
        if row['deleted_at'] is None:
            raise HTTPException(409,'이미 복구된 PDF 버전입니다.')
        con.execute('DELETE FROM paper_version_trash WHERE version_id=?',(version_id,))
        advance_version_revision(con,version_id)
        return version_item(version_row(con,paper_id,version_id))

@router.get('/api/papers/{paper_id}/versions/{version_id}/file')
def get_version_file(paper_id: str, version_id: str):
    with storage.transaction() as con:
        row=con.execute('''SELECT f.storage_key,f.sha256 FROM paper_versions v JOIN files f ON f.id=v.file_id
                           JOIN papers p ON p.id=v.paper_id LEFT JOIN paper_version_trash t ON t.version_id=v.id
                           WHERE v.id=? AND v.paper_id=? AND p.deleted_at IS NULL AND t.version_id IS NULL''',
                         (version_id,paper_id)).fetchone()
        if not row: raise HTTPException(404,'추가 PDF 버전을 찾을 수 없습니다.')
        path=storage.file_path(row['storage_key'])
        if not path.is_file(): raise HTTPException(409,'PDF 파일이 없습니다. 백업을 확인해 주세요.')
        digest=hashlib.sha256()
        with path.open('rb') as source:
            for part in iter(lambda:source.read(1024*1024),b''): digest.update(part)
        if digest.hexdigest()!=row['sha256']: raise HTTPException(409,'PDF 파일이 변경되었거나 손상되었습니다. 백업을 확인해 주세요.')
        return FileResponse(path,media_type='application/pdf',filename='paper-version.pdf',content_disposition_type='inline')


# ---- Permanent purge of items already in trash (AC-3) ----
PURGE_NOTICE = '영구 삭제는 되돌릴 수 없습니다. 기존 백업 ZIP 파일은 변경되지 않습니다.'

class PurgeConfirm(BaseModel):
    confirm_token: str = Field(min_length=1, max_length=128)
    delete_files: bool = False

def _in(values):
    return ','.join('?' * len(values)) if values else 'NULL'

def _column(con, sql, params=()):
    return sorted({row[0] for row in con.execute(sql, params).fetchall()}, key=str)

def _evidence_specs(con, ev):
    """Delete specs for evidence rows in FK-safe order: (table, where, params)."""
    rev = _column(con, f'SELECT id FROM evidence_revisions WHERE evidence_id IN ({_in(ev)})', ev)
    blocked = []
    linked = _column(con, f'SELECT DISTINCT evidence_id FROM idea_evidence WHERE evidence_id IN ({_in(ev)})', ev)
    if linked:
        blocked.append({'reason': 'idea_linked_evidence', 'ids': linked})
    specs = [
        ('revision_provenance', f'revision_id IN ({_in(rev)})', rev),
        ('revision_ocr_source', f'revision_id IN ({_in(rev)})', rev),
        ('evidence_revisions', f'evidence_id IN ({_in(ev)})', ev),
        ('evidence_provenance', f'evidence_id IN ({_in(ev)})', ev),
        ('evidence_ocr_source', f'evidence_id IN ({_in(ev)})', ev),
        ('evidence_trash', f'evidence_id IN ({_in(ev)})', ev),
        ('evidence', f'id IN ({_in(ev)})', ev),
    ]
    return specs, blocked, rev

def _finish_plan(con, kind, item_id, title, specs, blocked, deletable=(), retained=False):
    counts = {}
    for table, where, params in specs:
        counts[table] = counts.get(table, 0) + con.execute(f'SELECT count(*) FROM {table} WHERE {where}', params).fetchone()[0]
    return {'kind': kind, 'id': item_id, 'title': title, 'specs': specs,
            'counts': dict(sorted(counts.items())), 'blocked_by': blocked,
            'deletable': list(deletable),
            'retained_files_reason': '다른 논문이나 버전이 같은 PDF를 사용하므로 원본 파일은 삭제하지 않습니다.' if retained else ''}

def _paper_plan(con, paper):
    pid = paper['id']
    ev = _column(con, 'SELECT id FROM evidence WHERE paper_id=?', (pid,))
    specs, blocked, rev = _evidence_specs(con, ev)
    jobs = sorted(set(_column(con, 'SELECT id FROM jobs WHERE target_id=?', (pid,)))
                  | set(_column(con, 'SELECT job_id FROM ocr_pages WHERE paper_id=?', (pid,))))
    if jobs:
        shared_page = _column(con, f'SELECT job_id FROM ocr_pages WHERE job_id IN ({_in(jobs)}) AND paper_id<>?', [*jobs, pid])
        if shared_page:
            blocked.append({'reason': 'ocr_job_shared', 'ids': shared_page})
        outside = ([str(x) for x in _column(con, f'SELECT evidence_id FROM evidence_ocr_source WHERE job_id IN ({_in(jobs)})', jobs) if x not in set(ev)]
                   + [str(x) for x in _column(con, f'SELECT revision_id FROM revision_ocr_source WHERE job_id IN ({_in(jobs)})', jobs) if x not in set(rev)])
        if outside:
            blocked.append({'reason': 'ocr_source_in_use', 'ids': sorted(outside)})
    specs += [
        ('page_extraction_details', 'paper_id=?', (pid,)),
        ('pages', 'paper_id=?', (pid,)),
        ('ocr_pages', 'paper_id=?', (pid,)),
    ]
    if jobs:
        specs += [
            ('job_events', f'job_id IN ({_in(jobs)})', jobs),
            ('jobs', f'id IN ({_in(jobs)})', jobs),
        ]
    versions = _column(con, 'SELECT id FROM paper_versions WHERE paper_id=?', (pid,))
    specs += [
        ('project_papers', 'paper_id=?', (pid,)),
        ('link_trash', 'paper_id=?', (pid,)),
        ('project_paper_notes', 'paper_id=?', (pid,)),
        ('paper_version_state', f'version_id IN ({_in(versions)})', versions),
        ('paper_version_trash', f'version_id IN ({_in(versions)})', versions),
        ('paper_versions', 'paper_id=?', (pid,)),
        ('papers', 'id=?', (pid,)),
    ]
    # A PDF is deletable only when no other paper row or version row still uses it.
    candidates = set(_column(con, 'SELECT file_id FROM paper_versions WHERE paper_id=?', (pid,)))
    if paper['file_id']:
        candidates.add(paper['file_id'])
    deletable, retained = [], False
    for fid in sorted(candidates):
        users = con.execute('''SELECT (SELECT count(*) FROM papers WHERE file_id=? AND id<>?)
            + (SELECT count(*) FROM paper_versions WHERE file_id=? AND paper_id<>?)''', (fid, pid, fid, pid)).fetchone()[0]
        if users:
            retained = True
        else:
            deletable.append(dict(con.execute('SELECT id,sha256,size,storage_key FROM files WHERE id=?', (fid,)).fetchone()))
    return _finish_plan(con, 'papers', pid, paper['title'], specs, blocked, deletable, retained)

def _project_plan(con, project):
    pid = project['id']
    ideas = _column(con, 'SELECT id FROM ideas WHERE project_id=?', (pid,))
    specs = [
        ('idea_evidence', f'idea_id IN ({_in(ideas)})', ideas),
        ('ideas', 'project_id=?', (pid,)),
        ('experiments', 'project_id=?', (pid,)),
        ('search_runs', 'project_id=?', (pid,)),
        ('project_papers', 'project_id=?', (pid,)),
        ('link_trash', 'project_id=?', (pid,)),
        ('project_paper_notes', 'project_id=?', (pid,)),
        ('project_trash', 'project_id=?', (pid,)),
        ('projects', 'id=?', (pid,)),
    ]
    return _finish_plan(con, 'projects', pid, project['name'], specs, [])

def _evidence_plan(con, row):
    specs, blocked, _ = _evidence_specs(con, [row['id']])
    return _finish_plan(con, 'evidence', row['id'], row['title'], specs, blocked)

def _link_plan(con, row):
    specs = [('link_trash', 'id=?', (row['id'],))]
    return _finish_plan(con, 'links', row['id'], row['title'], specs, [])

def _purge_plan(con, kind, item_id):
    if kind == 'papers':
        paper = con.execute('SELECT id,title,file_id FROM papers WHERE id=? AND deleted_at IS NOT NULL', (item_id,)).fetchone()
        if not paper: raise HTTPException(404, '휴지통에서 논문을 찾을 수 없습니다.')
        return _paper_plan(con, paper)
    if kind == 'projects':
        row = con.execute('''SELECT p.id,p.name FROM projects p JOIN project_trash t ON t.project_id=p.id
                             WHERE p.id=?''', (item_id,)).fetchone()
        if not row: raise HTTPException(404, '휴지통에서 프로젝트를 찾을 수 없습니다.')
        return _project_plan(con, row)
    if kind == 'evidence':
        row = con.execute('''SELECT e.id,p.title FROM evidence e JOIN evidence_trash t ON t.evidence_id=e.id
                             JOIN papers p ON p.id=e.paper_id WHERE e.id=?''', (item_id,)).fetchone()
        if not row: raise HTTPException(404, '휴지통에서 근거를 찾을 수 없습니다.')
        return _evidence_plan(con, row)
    if kind == 'links':
        row = con.execute('''SELECT t.id,p.title FROM link_trash t JOIN papers p ON p.id=t.paper_id
                             WHERE t.id=?''', (item_id,)).fetchone()
        if not row: raise HTTPException(404, '휴지통에서 연결을 찾을 수 없습니다.')
        return _link_plan(con, row)
    raise HTTPException(404, '알 수 없는 휴지통 항목입니다.')

def _preview_body(plan):
    files = [{'file_id': f['id'], 'sha256': f['sha256'], 'size': f['size']} for f in plan['deletable']]
    basis = {'kind': plan['kind'], 'id': plan['id'], 'counts': plan['counts'],
             'blocked_by': plan['blocked_by'], 'deletable_files': files}
    token = hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False,
                                      separators=(',', ':')).encode('utf-8')).hexdigest()
    return {'kind': plan['kind'], 'id': plan['id'], 'title': plan['title'], 'counts': plan['counts'],
            'blocked_by': plan['blocked_by'], 'deletable_files': files,
            'retained_files_reason': plan['retained_files_reason'],
            'confirm_token': token, 'notice': PURGE_NOTICE}

@router.get('/api/trash/{kind}/{item_id}/purge-preview')
def purge_preview(kind: str, item_id: str):
    with storage.transaction() as con:
        con.execute('BEGIN')
        return _preview_body(_purge_plan(con, kind, item_id))

@router.post('/api/trash/{kind}/{item_id}/purge')
def purge_trash_item(kind: str, item_id: str, payload: PurgeConfirm):
    with storage.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        plan = _purge_plan(con, kind, item_id)
        body = _preview_body(plan)
        if payload.confirm_token != body['confirm_token']:
            raise HTTPException(409, '휴지통 항목이 바뀌었습니다. 미리보기를 다시 확인해 주세요.')
        if plan['blocked_by']:
            raise HTTPException(409, '차단 사유가 있어 영구 삭제할 수 없습니다. 미리보기의 차단 사유를 확인해 주세요.')
        for table, where, params in plan['specs']:
            con.execute(f'DELETE FROM {table} WHERE {where}', params)
        if payload.delete_files and plan['deletable']:
            ids = [f['id'] for f in plan['deletable']]
            con.execute(f'DELETE FROM files WHERE id IN ({_in(ids)})', ids)
    # The database change is committed; only now remove the unreferenced PDFs.
    deleted_files, not_removed = [], []
    if payload.delete_files:
        for f in plan['deletable']:
            # A re-upload of the same bytes may have re-created a files row after
            # the commit above. Check and unlink under one write lock so no insert
            # can slip in between the check and the unlink.
            with storage.transaction() as con:
                con.execute('BEGIN IMMEDIATE')
                if con.execute('SELECT 1 FROM files WHERE sha256=?', (f['sha256'],)).fetchone():
                    not_removed.append({'sha256': f['sha256'], 'reason': 'reuploaded'})
                    continue
                try:
                    storage.file_path(f['storage_key']).unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    not_removed.append({'sha256': f['sha256'], 'reason': 'os_error'})
                    continue
            deleted_files.append(f['sha256'])
    return {'status': 'purged', 'kind': kind, 'id': item_id, 'deleted': plan['counts'],
            'deleted_files': deleted_files, 'files_not_removed': not_removed}
