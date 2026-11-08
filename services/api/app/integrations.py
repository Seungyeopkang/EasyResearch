"""Read-only export integrations: citekeys, CSL-JSON, Web Annotation, and Obsidian notes.

Nothing here writes to the database or to the filesystem outside the response body.
Note text and quotes are untrusted user content and are neutralized before they
are placed inside the generated Obsidian marker region.
"""
import io
import json
import re
import unicodedata
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from . import evidence_records, storage

router = APIRouter()

APP_BASE = "http://127.0.0.1:8000/#/paper/"
FUNCTION_WORDS = {"a", "an", "the", "of", "for", "on", "in", "and", "to", "with", "at", "by", "from", "as", "or", "via"}
RFC3778 = "http://tools.ietf.org/rfc/rfc3778"
MARKER_BEGIN = "<!-- easyresearch:begin -->"
MARKER_END = "<!-- easyresearch:end -->"


def _strip_marks(text):
    """NFKD-decompose and drop combining marks (accents)."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(ch))


def _ascii_alnum(text):
    return re.sub(r"[^A-Za-z0-9]", "", text)


def _family_name(name):
    name = (name or "").strip()
    if "," in name:
        return name.split(",", 1)[0].strip()
    parts = name.split()
    return parts[-1] if parts else ""


def _split_name(name):
    """Split 'Given Family' or 'Family, Given' into CSL name parts."""
    name = (name or "").strip()
    if "," in name:
        family, given = name.split(",", 1)
        return {"family": family.strip(), "given": given.strip()}
    parts = name.split()
    if not parts:
        return {"family": "", "given": ""}
    if len(parts) == 1:
        return {"family": parts[0], "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def citekey(authors, title, year):
    """Better-BibTeX-style key: auth.lower + shorttitle(3,3) + year."""
    names = [a for a in (authors or []) if (a or "").strip()]
    author_part = _ascii_alnum(_strip_marks(_family_name(names[0]) if names else "")).lower() or "anon"
    words = [w for w in re.findall(r"[A-Za-z0-9]+", _strip_marks(title or "")) if w.lower() not in FUNCTION_WORDS][:3]
    short = "".join(w[0].upper() + w[1:] for w in words)
    year_part = "" if year is None else _ascii_alnum(str(year))
    return author_part + short + year_part


def _suffix(index):
    """0 -> a, 1 -> b, ..., 25 -> z, 26 -> aa."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(97 + rem) + letters
    return letters


def assign_citekeys(papers):
    """Return {paper_id: unique citekey}. Ordering is (created_at, id); collisions get a, b, c suffixes."""
    used = set()
    result = {}
    for paper in sorted(papers, key=lambda p: (p.get("created_at") or "", p["id"])):
        base = citekey(paper.get("authors") or [], paper.get("title") or "", paper.get("year"))
        key, n = base, 0
        while key in used:
            key = base + _suffix(n)
            n += 1
        used.add(key)
        result[paper["id"]] = key
    return result


def _require_project(con, project_id):
    if not con.execute("SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)", (project_id,)).fetchone():
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")


def _load_project(con, project_id):
    _require_project(con, project_id)
    project = con.execute("SELECT id,name,description FROM projects WHERE id=?", (project_id,)).fetchone()
    papers = []
    rows = con.execute("""SELECT p.*, pp.reading_status, f.sha256 AS file_sha256
        FROM papers p JOIN project_papers pp ON p.id=pp.paper_id
        LEFT JOIN files f ON f.id=p.file_id
        WHERE pp.project_id=? AND p.deleted_at IS NULL ORDER BY p.title, p.id""", (project_id,)).fetchall()
    for row in rows:
        item = dict(row)
        item.pop("metadata_json", None)
        item["authors"] = json.loads(item.get("authors") or "[]")
        item["evidence"] = [evidence_records.evidence_item(con, e) for e in con.execute(
            "SELECT * FROM evidence WHERE paper_id=? AND id NOT IN (SELECT evidence_id FROM evidence_trash) ORDER BY page_index,id",
            (item["id"],))]
        note = con.execute("SELECT note FROM project_paper_notes WHERE project_id=? AND paper_id=?", (project_id, item["id"])).fetchone()
        item["project_note"] = note["note"] if note else ""
        papers.append(item)
    return dict(project), papers


def _respond(payload, media_type, filename=None):
    headers = {"Content-Disposition": 'attachment; filename="' + filename + '"'} if filename else None
    return Response(content=json.dumps(payload, ensure_ascii=False, indent=2), media_type=media_type, headers=headers)


# ---------- CSL-JSON ----------

def _csl_item(paper, key):
    item = {
        "id": key,
        "type": "article-journal" if paper.get("doi") else "document",
        "title": paper.get("title") or "",
        "author": [_split_name(a) for a in paper["authors"] if (a or "").strip()],
    }
    year = paper.get("year")
    if year is not None and str(year).strip().isdigit():
        item["issued"] = {"date-parts": [[int(year)]]}
    if paper.get("doi"):
        item["DOI"] = paper["doi"]
    if paper.get("source_url"):
        item["URL"] = paper["source_url"]
    return item


@router.get("/api/projects/{project_id}/export/csl-json")
def export_csl_json(project_id: str):
    with storage.transaction() as con:
        _project, papers = _load_project(con, project_id)
    keys = assign_citekeys(papers)
    return _respond([_csl_item(p, keys[p["id"]]) for p in papers], "application/json", "easyresearch.csl.json")


# ---------- W3C Web Annotation ----------

def _annotation(paper, item):
    quote = item["quote"] or ""
    note = item["note"] or ""
    page = item["page_index"] + 1
    selectors = []
    if quote.strip():
        selectors.append({"type": "TextQuoteSelector", "exact": quote, "prefix": item["prefix"] or "", "suffix": item["suffix"] or ""})
    selectors.append({"type": "FragmentSelector", "conformsTo": RFC3778, "value": "page=" + str(page)})
    source = "urn:sha256:" + paper["file_sha256"] if paper.get("file_sha256") else "urn:easyresearch:paper:" + paper["id"]
    annotation = {
        "id": "urn:easyresearch:evidence:" + item["id"],
        "type": "Annotation",
        "motivation": "highlighting" if quote.strip() else "commenting",
        "target": {"source": source, "selector": selectors},
        "easyresearch": {
            "paper_id": paper["id"],
            "page_index": item["page_index"],
            "status": item["status"],
            "capture_method": item["capture_method"],
            "original_checked": item["original_checked"],
        },
    }
    if note.strip():
        annotation["body"] = {"type": "TextualBody", "value": note, "format": "text/plain", "purpose": "commenting"}
    return annotation


@router.get("/api/projects/{project_id}/export/annotations")
def export_annotations(project_id: str):
    with storage.transaction() as con:
        _project, papers = _load_project(con, project_id)
    items = []
    for paper in papers:
        for item in paper["evidence"]:
            if (item["quote"] or "").strip() or (item["note"] or "").strip():
                items.append(_annotation(paper, item))
    body = {"@context": "http://www.w3.org/ns/anno.jsonld", "type": "AnnotationCollection", "items": items}
    return Response(content=json.dumps(body, ensure_ascii=False, indent=2), media_type="application/ld+json")


# ---------- Obsidian notes ----------

def _neutralize(text):
    """Keep user text from forming or terminating the generated marker region."""
    return (text or "").replace("<!--", "&lt;!--")


def _lines(text):
    if not (text or "").strip():
        return []
    return [_neutralize(line).rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def _deeplink(paper_id, project_id, page):
    return APP_BASE + paper_id + "?project=" + project_id + "&page=" + str(page)


def _generated(project, paper):
    pid, proj = paper["id"], project["id"]
    lines = ["[EasyResearch에서 열기](" + _deeplink(pid, proj, 1) + ")", "", "## 프로젝트 메모", ""]
    lines += _lines(paper["project_note"])
    lines += ["", "## 발췌", ""]
    for item in paper["evidence"]:
        quote, note = item["quote"] or "", item["note"] or ""
        if not (quote.strip() or note.strip()):
            continue
        page = item["page_index"] + 1
        if quote.strip():
            lines += [("> " + line).rstrip() for line in _lines(quote)]
            lines.append("")
        paragraph = ["파일 " + str(page) + "쪽 · [원문 열기](" + _deeplink(pid, proj, page) + ") · " + item["status"]]
        paragraph += [line for line in _lines(note) if line.strip()]
        paragraph[-1] += " ^ev-" + item["id"]
        lines += paragraph + [""]
    body = "\n".join(lines).rstrip("\n")
    return MARKER_BEGIN + "\n" + body + "\n" + MARKER_END + "\n"


def _frontmatter(project, paper, key):
    return {
        "citekey": key,
        "title": paper["title"],
        "authors": list(paper["authors"]),
        "year": paper.get("year"),
        "doi": paper.get("doi") or None,
        "easyresearch_id": paper["id"],
        "easyresearch_project": project["id"],
        "reading_status": paper["reading_status"],
        "tags": ["easyresearch"],
    }


def _obsidian_notes(project, papers):
    keys = assign_citekeys(papers)
    notes = []
    for paper in papers:
        key = keys[paper["id"]]
        notes.append({
            "paper_id": paper["id"],
            "citekey": key,
            "filename": key + ".md",
            "frontmatter": _frontmatter(project, paper, key),
            "generated": _generated(project, paper),
            "title": paper["title"],
        })
    return notes


def _yaml_str(text):
    value = json.dumps(text, ensure_ascii=False)
    for char, escape in (("\u0085", "\\u0085"), (" ", "\\u2028"), (" ", "\\u2029"), ("\x7f", "\\u007f")):
        value = value.replace(char, escape)
    return value


def _yaml_value(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_value(v) for v in value) + "]"
    return _yaml_str(str(value))


def _render_markdown(note):
    frontmatter = "---\n" + "\n".join(k + ": " + _yaml_value(v) for k, v in note["frontmatter"].items()) + "\n---\n\n"
    heading = " ".join(_neutralize(note["title"]).split())
    return frontmatter + "# " + heading + "\n\n" + note["generated"]


@router.get("/api/projects/{project_id}/obsidian-notes")
def obsidian_notes(project_id: str):
    with storage.transaction() as con:
        project, papers = _load_project(con, project_id)
    notes = _obsidian_notes(project, papers)
    return _respond({"schema_version": 1,
                     "project": {"id": project["id"], "name": project["name"], "description": project["description"]},
                     "notes": notes}, "application/json")


@router.get("/api/projects/{project_id}/export/obsidian")
def export_obsidian(project_id: str):
    with storage.transaction() as con:
        project, papers = _load_project(con, project_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for note in _obsidian_notes(project, papers):
            archive.writestr(note["filename"], _render_markdown(note).encode("utf-8"))
    return Response(content=buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="easyresearch-obsidian.zip"'})
