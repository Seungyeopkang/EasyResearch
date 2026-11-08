# 003 — 프로젝트와 분리된 서재, 연속 스크롤·번역, 자동 분류, 검색, 디자인

This ExecPlan is a living document maintained under `.agent/PLANS.md`.

## Purpose / Big Picture

사용자 요청(2026-11-08): (1) PDF를 페이지 단위가 아니라 스크롤로 읽는다. (2) 번역이 된다. (3) 프로젝트 없이도 논문을 읽고 관리하며, 프로젝트는 연구 진행용이다. (4) 읽은 논문이 분야(최적화, 경량화 등)로 자동 분류된다. (5) 논문 검색을 쓸 수 있다. (6) 디자인을 개선한다. 조건: 무료, 품질은 괜찮을 것, 인터넷 연결 필수는 허용.

역할: Sol = Claude Opus(계획·검증·게이트), 구현·테스트 = Claude Haiku 서브에이전트.

## Decision Log

- 2026-11-08 / Opus: 번역은 브라우저 내장 Translator API(Chrome 138+, Edge 지원 버전)를 사용한다. 무료이고 기기 안에서 번역하며, 첫 사용 때 언어 모델을 내려받는다. 서버는 번역에 관여하지 않으므로 외부 전송 미리보기 규칙의 대상이 아니다. API가 없으면 지원 브라우저 안내를 표시한다. 유료·키가 필요한 API와 비공식 무료 엔드포인트는 쓰지 않는다.
- 2026-11-08 / Opus: 자동 분류는 (a) 편집 가능한 분야별 키워드 규칙과 (b) OpenAlex의 무료 topic/subfield/keyword 정보를 쓴다. 결과는 `suggested`로 저장하고 사용자가 `confirmed`/`rejected`로 확정한다. 읽기 상태가 `read`가 될 때와 사용자가 요청할 때 규칙 분류를 실행한다. OpenAlex 조회는 사용자가 누를 때만 하며 DOI 또는 제목만 보낸다.
- 2026-11-08 / Opus: 읽기 상태와 마지막 페이지는 논문 단위(전역)로 옮긴다(`paper_reading_state`). 기존 `project_papers.reading_status/last_page`는 호환을 위해 남긴다. v5→v6 이관 시 여러 프로젝트 값은 read > reading > on_hold > to_read 순으로 가장 진행된 상태, 마지막 페이지는 최댓값으로 정한다. 기록을 지우거나 바꾸지 않는다.
- 2026-11-08 / Opus: 검색 결과의 공개 PDF는 사용자가 누를 때만 https로 내려받고(최대 100MB, `%PDF-` 확인, 해시 저장) 논문에 원본으로 연결한다. 기존 원본이 있으면 교체하지 않는다.

## Scope and Non-Goals

범위: 스키마 v6과 이관·백업 호환, 프로젝트 없는 서재 API·화면, 연속 스크롤 뷰어, 선택 문구·페이지 번역, 분야 분류(규칙+OpenAlex), 검색 화면 수정과 공개 PDF 받기, 전체 디자인 개선.
비범위: AI 요약·분석, 유료 번역, 번역문 영구 저장, 기존 근거 좌표 하이라이트, 4단계 PDF 품질 평가.

## Acceptance Criteria

- AC-1: 새 DB는 v6으로 만들어지고, v1~v5 DB·백업은 v6으로 이관된다. 이관 전 스냅샷을 남기고 기존 기록은 바뀌지 않는다. v6 백업은 생성·검사·복원된다. 미래 버전은 거부된다.
- AC-2: 프로젝트 없이 PDF 등록, 수동 논문 등록, 목록 조회, 읽기 상태·마지막 페이지 저장, 근거 저장이 된다. 논문을 프로젝트에 연결·해제할 수 있다. 기존 프로젝트 API는 계속 동작한다.
- AC-3: 뷰어는 모든 페이지를 세로 연속 스크롤로 보여주고, 화면 근처 페이지만 렌더링하며 먼 페이지 캔버스는 해제한다. 현재 페이지가 바뀌면 마지막 페이지가 저장되고, 페이지 이동 입력·←/→·딥링크가 해당 페이지로 스크롤한다. 각 페이지에서 글을 선택하면 그 페이지 번호와 앞뒤 문맥이 입력된다.
- AC-4: 선택 문구 번역과 현재 페이지 추출 텍스트 번역이 Translator API로 동작하고, 미지원·모델 다운로드 중·실패 상태를 한국어로 표시한다. 번역문은 원문 근거를 대체하지 않는다.
- AC-5: 분야(이름+키워드) CRUD, 기본 분야(최적화, 경량화 등) 제공, 논문별 규칙 분류 결과(일치 키워드 포함)가 suggested로 저장되고, 사용자가 확정·거절하며, 거절한 분야는 재분류로 되살아나지 않는다. 읽음 처리 시 자동 분류된다. OpenAlex 주제를 가져와 저장하고 분류 근거로 쓴다. 서재를 분야로 거를 수 있다.
- AC-6: 검색 화면은 프로젝트 없이 동작하고, 결과를 서재에 추가하며, 공개 PDF가 있으면 받아 연결한다. 오류는 원인별 한국어 메시지로 보인다.
- AC-7: 영구 삭제가 새 테이블의 기록도 함께 지우고 무결성 검사를 통과한다.
- AC-8: 디자인이 일관된 색·간격·타이포그래피로 개선되고, 좁은 화면에서도 깨지지 않는다. 실제 브라우저 스크린숏으로 확인한다.
- AC-9: 전체 테스트가 Python 3.12와 3.9에서 통과한다. 사용자 `data/`는 쓰지 않는다.

## 고정 계약

스키마 v6 추가(`SCHEMA_V6_ADDITIONS`):

```sql
CREATE TABLE IF NOT EXISTS paper_reading_state (
 paper_id TEXT PRIMARY KEY REFERENCES papers(id), reading_status TEXT NOT NULL DEFAULT 'to_read',
 last_page INTEGER NOT NULL DEFAULT 0, last_opened_at TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, keywords_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS paper_categories (
 paper_id TEXT NOT NULL REFERENCES papers(id), category_id TEXT NOT NULL REFERENCES categories(id),
 source TEXT NOT NULL, status TEXT NOT NULL, matched_json TEXT NOT NULL DEFAULT '[]',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(paper_id,category_id)
);
CREATE TABLE IF NOT EXISTS paper_topics (
 paper_id TEXT NOT NULL REFERENCES papers(id), source TEXT NOT NULL, topic_id TEXT NOT NULL,
 name TEXT NOT NULL, subfield TEXT, field TEXT, score REAL,
 fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(paper_id,source,topic_id)
);
```

API:
- `GET /api/library/papers?status=&category_id=&q=&sort=recent|added|title|year` → `[{...paper, reading_status, last_page, last_opened_at, projects:[{id,name}], categories:[{id,name,status,source,matched}]}]`
- `POST /api/papers/import`: `project_id` 선택 항목이 된다. `POST /api/papers` (JSON, 수동 등록, 프로젝트 없음).
- `PATCH /api/papers/{id}`: `project_id` 없이 `reading_status`/`last_page`를 보내면 전역 상태를 갱신한다(있으면 기존처럼 프로젝트 값도 함께). 응답에 전역 상태 포함.
- `POST /api/projects/{pid}/papers/{paper_id}/link` → 기존 논문을 프로젝트에 연결.
- `GET/POST /api/categories`, `PATCH/DELETE /api/categories/{id}`(삭제는 연결된 분류도 삭제), `POST /api/papers/{id}/classify` → 규칙 분류 결과, `POST /api/library/classify` → 전체 재분류, `PUT /api/papers/{id}/categories/{cid}` `{status:"confirmed"|"rejected"}`, `POST /api/papers/{id}/topics/fetch` → OpenAlex 주제 저장·반환.
- `POST /api/papers/from-search`: `project_id` 선택 항목. `POST /api/papers/{id}/fetch-open-pdf` `{url?}` → 공개 PDF 받아 연결.

프런트 모듈:
- `pdf-viewer.js`: `renderPdfDocument(container, paperId, {startPage, zoom, onSelection(text,page,context), onPageChange(page), onReady({pageCount})}) → {scrollToPage(n), getCurrentPage()}`, `closePdfViewer()`.
- `translate.js`: `translatorAvailability(source,target)` → `'available'|'downloadable'|'downloading'|'unavailable'|'unsupported'`, `translateText(text,{source,target,onProgress})` → 문자열.

## Task Graph and Ownership

1. A1 (Haiku): `storage.py` v6·이관, `main.py`(프로젝트 선택 항목화, 전역 상태), 새 `reading_library.py` 라우터, `library_management.py` 영구 삭제의 새 테이블 처리, 테스트.
2. B (Haiku, A1과 병렬): `pdf-viewer.js` 연속 스크롤, 새 `translate.js`, 노드 테스트.
3. A2 (Haiku, A1 후): 새 `categories.py`(분야·규칙 분류·OpenAlex 주제), 테스트.
4. A3 (Haiku, A1 후, A2와 병렬): 새 `search_import.py`(공개 PDF 받기), 테스트.
5. C (Haiku, A·B 후): `app.js`, `style.css`, `index.html` — 서재 중심 화면, 뷰어·번역 통합, 분류 UI, 검색 화면, 디자인.
6. Opus: 단계마다 diff·테스트 검증, 통합 테스트, 실제 브라우저 확인, 문서 갱신, 게이트.

## Progress

- [x] A1 스키마 v6·전역 서재 API. [x] B 연속 스크롤·번역 모듈. [x] A2 분야·규칙 분류·OpenAlex 주제(Opus 검토 후 어형 변화 매칭 보강). [x] A3 공개 PDF 받기. [x] C 서재 중심 화면·디자인.
- [x] 통합 검증. Opus가 실제 브라우저에서 결함 5개를 찾아 고쳤다(아래 Surprises).
- [x] AC-4 실제 번역 결과 확인: 앱 내장 브라우저(Electron, Chrome 152)는 `Translator.availability`가 응답하지 않았다. 사용자 Chrome 157(Claude in Chrome)에서 상태 `downloadable` → "이 페이지 번역" 실제 클릭으로 모델 내려받기 → `available`, EEM-NAS 1쪽 한국어 번역 완료. 재실행 시 7개 문단으로 나뉘어 즉시 번역, 상태 줄 "바로 번역할 수 있습니다", PDF 선택 문구 → 떠 있는 "번역" 버튼 → "제로 비용 프록시는 …" 번역 표시와 기록 칸 자동 입력을 확인했다. 이 과정에서 (6) 번역 완료 뒤 상태 줄이 갱신되지 않던 문제와 (7) 빈 줄 없는 PDF 텍스트가 한 문단으로 묶이던 문제를 고쳤다(문장 단위 약 600자 묶음).

## Validation Evidence

작업 폴더 `C:\Users\user\Desktop\EasyResearch`, 2026-11-08.

- `PYTHONIOENCODING=utf-8 python -m unittest discover -s services/api/tests`: Anaconda 3.12와 Python 3.9 모두 exit 0, `Ran 259 tests`, `OK (skipped=5)`. `python -m unittest discover -s tests`: 두 환경 exit 0, 28개 OK. 모든 `scripts/tests/*.cjs` 통과, `node --check` 통과. AC-1, AC-2, AC-5, AC-6, AC-7, AC-9와 화면 로직.
- 실제 브라우저(내장 브라우저, 임시 데이터 `scratchpad/demo-data`, 포트 8765): v5 데모 DB가 v6으로 이관된 뒤 서재 표시. 전체 재분류로 사용자 업로드 논문 EEM-NAS가 경량화(pruning)·최적화(convergence, optimizer)·컴퓨터 비전으로 추천됨. 28쪽 PDF 연속 스크롤에서 화면 근처 4쪽만 렌더링, 스크롤 시 현재 쪽·주소·전역 `last_page`(4, 0부터) 갱신, 텍스트 레이어 투명. 딥링크 새로고침 시 3쪽으로 열림. 375px에서 가로 넘침 없음. 검색이 프로젝트 없이 동작하고 arXiv "Distilling the Knowledge in a Neural Network"를 서재에 추가 → 공개 PDF 받기(201, 106,630 bytes, `https://arxiv.org/pdf/1503.02531v1`) → 추출 완료. AC-3, AC-6, AC-8.
- 번역: 탭·선택 번역 버튼·이 페이지 번역 동작과 미지원·응답 없음 안내를 확인. 실제 번역문은 미확인(AC-4 미완).

## Surprises & Discoveries

- 2026-11-08: 사용자가 "검색이 안 된다"고 했으나 서버의 OpenAlex·arXiv·Crossref 검색은 정상 응답했고, 서버 기록에 사용자 검색이 없었다. 화면에서 프로젝트 선택 요구 등으로 요청이 나가지 않았을 가능성을 C 단계에서 재현·수정한다. Opus 재현 결과: 프로젝트를 선택하지 않으면 `needProject()`가 검색 화면 전체를 막는다. 프로젝트를 선택하면 "모델 경량화", "model pruning" 모두 OpenAlex 결과가 나온다. 검색 결과를 추가해도 PDF가 없어 바로 읽을 수 없다.

- 2026-11-08 / A3: 공개 PDF 받기는 https만 허용하고 사설·루프백 주소를 리다이렉트마다 다시 확인하지만, DNS 확인과 연결 사이의 rebinding은 막지 못한다. 사용자가 직접 누를 때만 동작하는 단일 사용자 로컬 앱이라 허용하고 한계로 기록한다.
- 2026-11-08 / A1: 프로젝트 범위 `GET /api/papers?project_id`는 기존 테스트 호환을 위해 프로젝트 값을 유지하고 `global_reading_status`/`global_last_page`를 추가로 돌려준다. 화면은 전역 상태만 표시한다(Opus 결정).

- 2026-11-08 / Opus 브라우저 검증에서 찾아 고친 결함:
  1. 서버가 화면 파일에 캐시 정책을 주지 않아 업데이트 뒤에도 옛 `style.css`가 남았다(적용 규칙 118개 vs 파일 189개). `/`와 `/assets/`(vendor 제외)에 `Cache-Control: no-cache`를 붙였다.
  2. 디자인 재작성 중 PDF.js 텍스트 레이어 CSS가 빠져 선택용 글자가 검게 겹쳐 보였다. 이전 규칙을 복원했다.
  3. 새 CSS의 `canvas{max-width:100%;height:auto}`가 캔버스만 축소해 선택 위치가 어긋날 수 있었다. 제거했다.
  4. 시작 시 서재를 먼저 그리며 `#/paper` 해시를 지워 딥링크 새로고침이 서재로 돌아갔다. 시작 해시를 먼저 저장하도록 고쳤다.
  5. 번역 API가 응답하지 않는 브라우저에서 "확인하는 중"에 영원히 멈췄다. 6초 제한과 안내 문구를 추가했다.

## Blockers

없음.

## Outcome

Sol(Opus) 게이트: **PASS**(2026-11-08). AC-1~AC-9 모두 자동 테스트와 실제 브라우저 증거가 있다(AC-4는 사용자 Chrome 157). 남은 한계: 데스크톱 앱의 미리보기 창 등 기기 내 번역 모델이 없는 브라우저에서는 번역 대신 안내가 표시된다. 규칙 분류는 키워드가 없는 분야를 놓칠 수 있다. 1100px 미만에서 오른쪽 패널은 접히는 서랍이 아니라 PDF 아래로 내려간다. 공개 PDF 받기는 DNS rebinding을 막지 못한다.
