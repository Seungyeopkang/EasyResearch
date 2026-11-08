# 002 — 1·2·3·5단계 완료와 노트 도구·에이전트 연동

This ExecPlan is a living document maintained under `.agent/PLANS.md`.

## Purpose / Big Picture

사용자 요청(2026-11-08): `docs/pdf-library-milestones.md`의 1·2·3·5단계를 완료하고, 유사 제품·GitHub 조사로 사용자 경험과 AX(Agent Experience: 외부 에이전트·노트 도구가 보관함을 읽고 연결하는 경험)를 넓힌다. AI 비교·연구 갭 탐지·AI 연구 실행처럼 모델 호출이 필요한 기능은 제외한다. 4단계(실제 PDF 품질)는 범위 밖이다.

역할 대응: 이 저장소의 Sol 코디네이터 역할은 Claude Opus가 맡고, 구현·테스트·조사 작업자는 Claude Haiku 서브에이전트가 맡는다(사용자 지시).

## Context and Orientation

- 조사 결과 요약(2026-11-08, Haiku 조사 3건, 상당수가 2차 자료라 일부 미확인):
  - Zotero는 휴지통 30일 자동 비우기, 비우기 시 영향 미표시가 불만 사항이다. JabRef는 변경 시에만 백업하고 10개를 회전한다. Calibre는 복원 전 기존 DB를 보존한다.
  - Obsidian 연동 관례: YAML frontmatter(citekey, doi 등), 블록 ID `^id`, 생성 구간 마커로 재내보내기 시 사용자 편집을 보존한다. Better BibTeX 기본 citekey는 `auth.lower + shorttitle(3,3) + year`이고 충돌 시 a, b, c 접미사를 붙인다(https://retorque.re/zotero-better-bibtex/citing/).
  - W3C Web Annotation: `TextQuoteSelector{exact,prefix,suffix}`가 현재 근거 필드와 1:1 대응한다(https://www.w3.org/TR/annotation-model/).
  - MCP: zotero-mcp 등은 stdio 읽기 도구 중심이다. 도구 annotation `readOnlyHint`/`destructiveHint`는 신뢰할 수 없는 힌트다. PDF 본문은 신뢰하지 않는 데이터로 감싸야 한다.
- 기준선(2026-11-08, Python 3.12.7): `python -m unittest discover -s services/api/tests` → 169개 실행, 오류 18개, 건너뜀 5개. 오류는 모두 테스트의 `with sqlite3.connect()`가 연결을 닫지 않아 Windows 임시 폴더 정리가 실패한 것이다(제품 결함 아님). 포트 8000 관련 오류 1건은 조사 중이다.

## Scope and Non-Goals

범위:
- WP0 테스트 연결 누수 수정(테스트 코드만).
- WP1 1단계 마무리: 잘린 ZIP, 해시 변조, 누락 PDF, 목록 외 항목, 중단 표식, 저장 공간 부족 경로를 재현하는 테스트. 실제 콘솔 Ctrl+C, 브라우저 자동 실행, 실제 디스크 가득 참은 수동 확인 항목으로 남긴다.
- WP2 2단계 마무리: 휴지통 항목의 영구 삭제. 영향 미리보기와 확인 토큰, 아이디어 참조 시 차단, 원본 PDF는 다른 참조가 없고 사용자가 명시할 때만 삭제한다.
- WP3 연동 내보내기: BBT 방식 citekey(BibTeX에 적용), CSL-JSON, W3C Web Annotation JSON-LD, Obsidian 노트 ZIP과 노트 JSON.
- WP4 Obsidian 볼트 동기화 스크립트와 읽기 전용 MCP stdio 서버(선택 의존성).
- WP5 화면: 휴지통 영구 삭제 UI, 새 내보내기 형식, `#/paper/<id>?project=<id>&page=<n>` 딥링크, 키보드 단축키(←/→ 페이지, `?` 도움말).
- 3·5단계 완료 확인: 기존 테스트로 완료 기준을 대조하고 증거를 기록한다.

비범위: AI 분석·비교·연구 갭·실험 생성, 태그·저장 검색(스키마 v6 필요), 휴지통 자동 비우기(무인 파괴 동작), 자동 백업 스케줄, 중복 병합, Zotero 로컬 API 쓰기, MCP 쓰기 도구, 4단계.

## Acceptance Criteria

- AC-1: 전체 `services/api/tests`와 `tests`가 오류 없이 통과한다(환경상 건너뜀은 이유와 함께 허용).
- AC-2: 손상 백업(잘림, 해시 변조, 누락 PDF, 목록 외 항목, DB 해시 불일치)은 400대 오류로 거부되고, 기존 보관함과 `restores/`에 새 폴더가 남지 않는다. 복원 중 실패 시 `.incomplete` 표식 폴더가 정리되거나 실행 목록에서 제외된다.
- AC-3: `GET /api/trash/{kind}/{id}/purge-preview`는 삭제될 기록 수, 차단 사유, 삭제 가능한 원본 PDF 목록, `confirm_token`을 반환한다. `POST .../purge`는 토큰이 현재 상태와 다르면 409, 휴지통에 없는 항목은 404, 아이디어가 참조하는 근거가 있으면 409이고, 성공 시 해당 기록과 종속 기록만 삭제하며 무결성 검사와 외래키 검사가 통과한다. PDF 파일은 `delete_files=true`이고 어떤 논문·버전도 참조하지 않을 때만 삭제한다. 다른 프로젝트·논문의 기록은 변하지 않는다.
- AC-4: BibTeX 키는 BBT 기본 규칙과 같다(예: He 외 2016 "Deep Residual Learning for Image Recognition" → `heDeepResidualLearning2016`, 규칙은 아래 Decision Log). 같은 키가 생기면 a, b, c 접미사로 유일해진다.
- AC-5: CSL-JSON은 배열이며 각 항목에 `id`(citekey), `type`, `title`, `author[{family,given}]`, `issued`, `DOI`가 있다. Web Annotation JSON-LD는 `@context`가 W3C이고 근거마다 `TextQuoteSelector`와 물리 페이지가 있다.
- AC-6: Obsidian 노트는 YAML frontmatter, 딥링크, `<!-- easyresearch:begin -->`/`<!-- easyresearch:end -->` 생성 구간, 근거마다 `^ev-<id>` 블록 ID를 포함한다. 동기화 스크립트는 기존 파일의 생성 구간 밖 내용과 frontmatter를 보존하고, 마커가 없는 기존 파일은 덮어쓰지 않고 충돌로 보고하며, 같은 입력으로 두 번 실행해도 결과가 같다.
- AC-7: MCP 서버는 읽기 도구만 노출하고 쓰기 요청을 보내지 않는다. PDF 본문·발췌는 신뢰하지 않는 데이터로 표시한다. `mcp` 패키지가 없으면 설치 안내를 출력하고 종료한다.
- AC-8: 화면에서 영구 삭제는 미리보기 확인 후에만 실행되고, 딥링크로 지정 프로젝트·논문·페이지가 열리며, 새 내보내기 형식을 선택할 수 있다.
- AC-9: DB 스키마 버전은 5로 유지된다(스키마 변경 없음). 사용자 `data/`는 테스트에서 사용하지 않는다.

## Task Graph and Ownership

- WP0 테스트 Haiku: `services/api/tests/` 기존 파일. 진행 중.
- WP1 테스트 Haiku: 새 파일 `services/api/tests/test_backup_failures.py`만.
- WP2 구현 Haiku: `services/api/app/library_management.py`와 새 테스트 `test_trash_purge.py`.
- WP3 구현 Haiku: 새 모듈 `services/api/app/integrations.py`, `main.py`의 라우터 등록 한 줄과 BibTeX 키 생성 부분, 새 테스트 `test_integrations.py`.
- WP4 구현 Haiku: 새 파일 `scripts/sync_obsidian.py`, `services/mcp/easyresearch_mcp.py`, 테스트. WP3의 노트 JSON 계약에 의존한다(계약은 아래에 고정).
- WP5 구현 Haiku: `apps/web/app.js`. WP2·WP3 통합 후 진행한다.
- WP0~WP4는 파일이 겹치지 않아 병렬로 진행한다. Opus가 각 결과의 diff와 테스트를 검증한 뒤 통합 상태에서 전체 테스트를 실행하고 게이트를 판정한다.

### 고정 계약

- `GET /api/projects/{project_id}/export/csl-json` → `application/json` 배열.
- `GET /api/projects/{project_id}/export/annotations` → `application/ld+json` 객체 `{"@context":"http://www.w3.org/ns/anno.jsonld","type":"AnnotationCollection","items":[...]}`.
- `GET /api/projects/{project_id}/obsidian-notes` → `{"schema_version":1,"project":{...},"notes":[{"paper_id","citekey","filename","frontmatter":{...},"generated":"<begin~end 마커 포함 본문>","title"}]}`.
- `GET /api/projects/{project_id}/export/obsidian` → 위 노트를 `<filename>`으로 담은 ZIP.
- 딥링크: `http://127.0.0.1:8000/#/paper/<paper_id>?project=<project_id>&page=<1부터 시작>`.

## Decision Log

- 2026-11-08 / Opus: AX는 Agent Experience로 해석한다. 앱 내부에서 모델을 호출하지 않는 읽기 전용 연동(MCP, 구조화 내보내기, 딥링크)만 포함한다.
- 2026-11-08 / Opus: 영구 삭제는 자동 실행하지 않는다. 사용자 확인 토큰과 명시적 PDF 삭제 선택을 요구한다. 기존 백업 ZIP은 지우지 않으며 그 사실을 미리보기에 표시한다.
- 2026-11-08 / Opus: Obsidian 연동은 앱이 볼트 폴더에 직접 쓰지 않는다. ZIP 다운로드와 사용자가 실행하는 동기화 스크립트로 제공해 앱의 파일 쓰기 범위를 `data/`로 유지한다.
- 2026-11-08 / Opus: citekey는 BBT `auth.lower + shorttitle(3,3) + year`를 따른다. shorttitle은 기능어(a, an, the, of, for, on, in, and 등)를 제외한 앞 3단어를 첫 글자 대문자로 붙인다. 저자가 없으면 `anon`, 연도가 없으면 생략한다. 결과에서 ASCII 영숫자 외 문자는 제거(NFKD 후 결합 문자 제거)한다.

## Progress

- [x] 2026-11-08 조사 3건 완료, 기준선 테스트 실행.
- [x] WP0 테스트 연결 누수 수정(3개 테스트 파일, `closing(...)` + 기존 commit 동작 유지).
- [x] WP1 `test_backup_failures.py` 10개. 제품 결함 없음.
- [x] WP2 영구 삭제. Opus 검토에서 "커밋 후 PDF 삭제"와 동시 재업로드의 경쟁으로 파일이 사라질 수 있음을 발견 → 작업자가 쓰기 잠금 안 재확인으로 수정, Opus가 업로드 경로(`import_pdf`, `add_paper_version`)에 잠금 안 파일 존재 확인 추가.
- [x] WP3 연동 내보내기와 BibTeX citekey.
- [x] WP4 동기화 스크립트와 MCP 서버. Opus 실데이터 점검에서 두 번째 동기화가 "갱신"으로 처리되고 빈 줄이 늘어나는 결함 발견 → 수정. Python 3.9 비호환 테스트 수정.
- [x] WP5 화면. Opus 실제 브라우저 확인에서 열린 탭의 해시 이동이 오래된 프로젝트 목록을 쓰는 결함 발견 → `openDeepLink`가 한 번 새로 불러오도록 수정, 테스트 보강. 영구 삭제 미리보기의 `jobs` 라벨 한국어화.
- [x] 통합 검증, 문서 갱신, 게이트.

## Surprises & Discoveries

- WP4 작업자가 지시 없이 전역 Python에 `mcp[cli]==1.27.2`를 설치해 `starlette`가 1.10.0으로 올라가 FastAPI 0.115.12와 충돌했다. Opus가 `starlette` 0.46.2로 되돌렸다(`pip check`에서 FastAPI 충돌 해소, 대신 `sse-starlette 3.7.0`과 충돌). 전역 환경에는 `mcp`, `sse-starlette`가 남아 있다. MCP README에 별도 가상환경 설치를 명시했다.
- PATH의 `python`은 Anaconda 3.12(FastAPI 0.115.12)이고, Python 3.9 설치본은 `requirements.txt` 고정 버전(FastAPI 0.128.0)을 쓴다. 두 환경 모두에서 검증했다.

## Validation Evidence

작업 폴더 `C:\Users\user\Desktop\EasyResearch`, 2026-11-08.

- `PYTHONIOENCODING=utf-8 python -m unittest discover -s services/api/tests` (Anaconda 3.12.7): exit 0, `Ran 204 tests`, `OK (skipped=5)`. 같은 명령을 Python 3.9 설치본으로: exit 0, 204개, `OK (skipped=5)`. AC-1~AC-5, AC-8(가짜 DOM), AC-9.
- `python -m unittest discover -s tests` (두 인터프리터): exit 0, `Ran 28 tests`, OK. AC-6, AC-7.
- `node --check apps/web/app.js`: exit 0. `python scripts/check_development_structure.py`: exit 0.
- Opus 실데이터 점검: 임시 데이터 폴더에서 실제 `/obsidian-notes` 결과로 동기화 2회 → "생성 1" 후 "변경 없음 1". BibTeX 키 `heDeepResidualLearning2016`. AC-4, AC-6.
- Opus 실제 브라우저 점검(내장 브라우저, 임시 데이터, 포트 8765): 딥링크로 지정 프로젝트·논문·1쪽 열림, `?` 단축키 창, CSL-JSON·JSON-LD·Obsidian ZIP 200 응답, 영구 삭제 미리보기(기록 수·PDF 선택 상자·비활성 확인 버튼) → "삭제" 입력 후 실행 → 휴지통과 논문 목록 비움, PDF 미선택이므로 파일과 `files` 행 유지, `integrity_check` ok, `foreign_key_check` 없음, `user_version` 5. AC-3, AC-8, AC-9.
- 확인하지 못한 것: 실제 MCP 클라이언트와 stdio 세션, 실제 Obsidian 앱에서 딥링크 클릭, 실제 콘솔 Ctrl+C, 실제 디스크 가득 참. 사용자 `data/`는 사용하지 않았다.

## Blockers

없음.

## Outcome

Sol(Opus) 게이트: **PASS** (2026-11-08). AC-1~AC-9의 자동·실데이터·브라우저 증거가 있고, 스키마 변경이 없으며, 범위 밖 변경은 전역 Python 패키지 설치 사고뿐이고 이는 위에 기록했다. 남은 수동 확인 항목은 `implementation-status.md`와 이 문서에 적었다.
