"""Separate evidence origin, original checks, and text match status."""
from fastapi import HTTPException
from .pdf_processing import locate_quote

METHODS={'manual','pdf_selection','ocr','legacy_unknown'}

def capture_details(con, paper, payload, old=None):
    fields=payload.model_fields_set
    same=bool(old and old['page_index']==payload.page_index and old['quote']==payload.quote and old['prefix']==payload.prefix and old['suffix']==payload.suffix)
    previous=con.execute('SELECT * FROM evidence_provenance WHERE evidence_id=?',(old['id'],)).fetchone() if old else None
    if 'capture_method' in fields:
        method=payload.capture_method
        if method not in METHODS-{'legacy_unknown'}:
            raise HTTPException(422,'근거 출처를 선택해 주세요.')
    else:
        method=previous['capture_method'] if same and previous else ('legacy_unknown' if same else 'manual')
    checked=(bool(payload.verified_with_original) if payload.verified_with_original is not None
             else (previous['original_checked'] if same and previous else None))
    old_source=con.execute('SELECT job_id FROM evidence_ocr_source WHERE evidence_id=?',(old['id'],)).fetchone() if old else None
    ocr_job_id=None
    if method=='ocr':
        if not payload.quote.strip(): raise HTTPException(422,'OCR 문구를 입력해 주세요.')
        # Unchanged old records retain their precise source, or retain unknown
        # when an earlier app version never stored one. Never infer their source.
        if same and previous and previous['capture_method']=='ocr' and not payload.ocr_job_id:
            ocr_job_id=old_source['job_id'] if old_source else None
        else:
            if payload.ocr_job_id:
                ocr=con.execute('SELECT job_id,text FROM ocr_pages WHERE job_id=? AND paper_id=? AND page_index=?',
                                (payload.ocr_job_id,paper['id'],payload.page_index)).fetchone()
            else:
                rows=con.execute('SELECT job_id,text FROM ocr_pages WHERE paper_id=? AND page_index=? ORDER BY rowid DESC LIMIT 2',
                                 (paper['id'],payload.page_index)).fetchall()
                if len(rows)>1:
                    raise HTTPException(409,'OCR 결과가 여러 개입니다. 확인한 OCR 결과를 선택해 주세요.')
                ocr=rows[0] if rows else None
            if not ocr or locate_quote(ocr['text'],payload.quote)['status'] not in {'candidate','ambiguous'}:
                raise HTTPException(422,'선택한 페이지의 OCR 결과에서 문구를 찾을 수 없습니다.')
            ocr_job_id=ocr['job_id']
    elif payload.ocr_job_id:
        raise HTTPException(422,'OCR 출처를 선택한 경우에만 OCR 결과를 지정할 수 있습니다.')
    file=con.execute('SELECT sha256 FROM files WHERE id=?',(paper['file_id'],)).fetchone() if paper['file_id'] else None
    file_sha=file['sha256'] if file else None
    return method,checked,file_sha,ocr_job_id

def evidence_item(con, row, match=None):
    item=dict(row)
    provenance=con.execute('SELECT * FROM evidence_provenance WHERE evidence_id=?',(row['id'],)).fetchone()
    item['capture_method']=provenance['capture_method'] if provenance else 'legacy_unknown'
    item['original_checked']=bool(provenance['original_checked']) if provenance and provenance['original_checked'] is not None else None
    item['file_sha256']=provenance['file_sha256'] if provenance else None
    ocr_source=con.execute('SELECT job_id FROM evidence_ocr_source WHERE evidence_id=?',(row['id'],)).fetchone()
    item['ocr_job_id']=ocr_source['job_id'] if ocr_source else None
    item['ocr_source_unknown']=item['capture_method']=='ocr' and item['ocr_job_id'] is None
    paper=con.execute('SELECT page_count,file_id FROM papers WHERE id=?',(row['paper_id'],)).fetchone()
    if paper and paper['page_count'] is not None and row['page_index']>=paper['page_count']:
        item['status']='invalid_page'
    elif not row['quote'].strip(): item['status']='note_only'
    else:
        if item['capture_method']=='ocr':
            page=con.execute('SELECT text FROM ocr_pages WHERE job_id=? AND paper_id=? AND page_index=?',(item['ocr_job_id'],row['paper_id'],row['page_index'])).fetchone()
        else:
            page=con.execute('SELECT text FROM pages WHERE paper_id=? AND page_index=?',(row['paper_id'],row['page_index'])).fetchone()
        if page and page['text'].strip():
            match=locate_quote(page['text'],row['quote'],row['prefix'],row['suffix'])
            item['status']=match['status']
        else:
            item['status']='ocr_unavailable' if item['capture_method']=='ocr' else 'page_unverified'
    item['match']=match
    return item
