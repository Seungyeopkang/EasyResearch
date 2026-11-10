# ExecPlan 004 — 연구 도우미 기초 구현 (논문 정리·연결·갭·채팅·연구 루프·에이전트 연동)

- 크기: Large (스키마 v7, 외부 전송 경계, 새 하위 시스템 다수)
- 상태: active
- 조정: Opus (Sol 역할), 구현·테스트: Haiku 작업자 (사용자 지정), 최종 판정: Opus

## 목표와 맥락

사용자 요청(2026-11-10):

1. 읽은 논문의 분야를 자동으로 정리한다.
2. 논문을 넣으면 방법, 목표 문제, 장단점 등을 자세히 정리한다.
3. Obsidian처럼 논문끼리 연결한다.
4. 단일 논문 또는 여러 논문의 갭을 찾는다.
5. 아이디어를 구체화하거나 갭을 찾는 채팅을 제공한다.
6. 주제를 주면 근거를 찾고, 반복 작업으로 문제를 찾고, 메소드로 개선하고, contribution을 찾는다.
7. 오케스트레이션, 에이전트, 스킬, MCP를 갖춘다.

이전 제약 "무료, 성능은 괜찮게, 인터넷 연결 필수 허용"을 따른다.

조사 결과는 [docs/research/auto-research-landscape.md](../../research/auto-research-landscape.md)에 정리한다.

## 범위

- 범위에 포함:
  - LLM 제공자 계층
  - 스키마 v7
  - 위 1~7 기능의 기초 API와 UI
  - MCP 도구 확장
  - 스킬 파일
  - Obsidian 위키링크
- 범위에 포함하지 않음 (비목표):
  - 실험 코드 자동 생성·실행 (기존 실험 기능과 연결하지 않음)
  - 논문 초안 자동 작성
  - 유료 API 기본값
  - 모델 자동 내려받기
  - 스트리밍 응답
  - 다중 사용자

## 핵심 결정

- **D1. 기본 제공자는 Ollama이다.**
  - 이 PC에 설치되어 있다 (RTX 4060 8GB, llama3-ko 8B).
  - 이유: 무료이고, 비공개이며, 인터넷이 필요 없다.
  - 외부 무료 등급은 OpenAI 호환 주소로 선택할 수 있다 (Gemini, Groq, OpenRouter).
  - Gemini 무료 등급은 입력이 Google 제품 개선에 쓰일 수 있으므로 UI에 명시한다.
  - 구독형 Claude·ChatGPT는 백엔드 대용으로 쓰지 않는다. MCP와 스킬로 사람이 직접 구동할 때만 쓴다.
- **D2. 외부 전송 경계를 둔다.** 모든 AI 호출은 `llm.preview()`에서 보낼 메시지 전체와 `preview_hash`를 만든다.
  - 비로컬 제공자: 같은 해시가 없으면 409로 거절한다.
  - 로컬(loopback) 제공자: 해시를 요구하지 않는다.
  - 연구 루프: 실행 생성 시 데이터 정책과 첫 단계 프롬프트를 미리보기로 보이고 해시로 승인받는다. 이후 단계의 실제 프롬프트는 단계 기록에 보존해 감사할 수 있게 한다.
  - 연구 루프가 보내는 데이터: 주제, 공개 검색 메타데이터(제목·초록), 사용자가 고른 논문의 정리 프로필. 개인 메모와 발췌 메모는 보내지 않는다.
- **D3. API 키 보관 방식**
  - DB, 로그, API 응답에 넣지 않는다.
  - 환경 변수, 또는 `data/secrets/llm_api_key`에 둔다. 이 파일은 백업에 포함되지 않는다 (백업은 manifest·sqlite·files만 담는다).
- **D4. AI 출력은 항상 초안이다.**
  - 대상: 프로필 `draft`, 연결 `suggested`, 갭 `candidate`, 루프 결과.
  - 사용자가 확정하고, 출처(origin)·모델·입력 해시를 저장한다.
  - 인용 구절은 저장된 페이지 텍스트에서 검사하고 결과를 `match` 값으로 표시한다. 검사 결과가 `not_found`이면 근거로 표시하지 않는다.
- **D5. AI가 없어도 동작하는 경로를 둔다.**
  - 규칙 기반 프로필: 단서 문장 추출.
  - 규칙 기반 갭: 한계, 공통 한계, 데이터셋·지표 공백, 방법×문제 조합.
  - 로컬 연결 추천: 분야·키워드 겹침.
  - OpenAlex 인용 연결.
- **D6. 연구 루프는 결정적 상태 기계이다.**
  - 단계: `plan_queries → search → screen → problems → methods → contributions → critique`. 반복이 끝날 때마다 사람 검토 지점(`awaiting_review`)에서 멈춘다.
  - 예산: 반복 3회, LLM 호출 40회, 반복당 논문 10편. 질의가 되풀이되는지도 검사한다.
  - 참신성은 주장하지 않는다. "가장 가까운 선행 연구" 검색 결과만 보인다.
  - 근거: Cognition "Don't build multi-agents", Anthropic "Building effective agents", Beel et al. 2502.14297.
- **D7. MCP 쓰기 도구는 초안 기록만 만든다.**
  - 대상: 프로필 `agent`/`draft`, 연결 `suggested`, 갭 `candidate`.
  - 삭제와 확정은 앱에서 사람이 한다.
  - 기존 읽기 전용 결정을 이 범위로만 넓힌다.

## 데이터 모델 (스키마 v7, `storage.SCHEMA_V7_ADDITIONS`)

새 테이블:
- `paper_profiles`
- `paper_links` (UNIQUE source, target, relation)
- `research_gaps`
- `chat_threads`
- `chat_messages`
- `research_runs`
- `research_steps`

v6→v7 이관은 테이블 생성만 한다. 영구 삭제 시 처리:
- 논문 삭제: 그 논문의 프로필·연결을 함께 삭제한다.
- 프로젝트 삭제: 그 프로젝트의 채팅·루프·갭을 함께 삭제한다.

### 프로필 JSON (`profile_json`)

```json
{"summary": "str",
 "facets": {"problem": [Item], "method": [Item], "contributions": [Item], "strengths": [Item],
            "limitations": [Item], "datasets": [Item], "metrics": [Item], "results": [Item], "future_work": [Item]},
 "keywords": ["str"]}
```

Item 형식:
`{"text": str, "origin": "author_stated"|"inferred", "evidence": [{"page": int(1-based physical), "quote": str, "match": "exact"|"normalized"|"not_found", "found_page": int|null}]}`

- facet 목록은 고정이다. 알 수 없는 키는 거부한다.
- 한 facet에는 최대 12개 항목, 항목 텍스트는 최대 1000자, quote는 최대 500자이다.
- origin 값: `rules`, `llm`, `agent`, `manual`.

### 연결 relation과 갭 gap_type

- 연결 relation: `cites`, `extends`, `compares_against`, `contradicts`, `supports`, `same_problem`, `same_method`, `uses_dataset`, `related`
- 연결 origin: `manual`, `openalex`, `rules`, `llm`, `agent`
- 연결 status: `suggested`, `accepted`, `rejected`
- 갭 gap_type: `unaddressed_limitation`, `common_limitation`, `missing_dataset_or_metric`, `method_not_applied_to_problem`, `conflicting_findings`, `untested_setting`, `other`
- 갭 status: `candidate`, `accepted`, `rejected`
- `evidence_json`: `[{"paper_id", "page"?, "quote"?, "facet"?, "match"?}]`

## API 계약

공통 규칙:
- 변경 요청에는 `X-EasyResearch: 1`이 필요하다.
- AI 엔드포인트는 `/preview` 짝을 두고, 본 호출은 `preview_hash`를 받는다.
- 오류는 `ai_routes.run_llm`으로 변환한다: 설정 없음 400, 해시 불일치 409, 서버 오류 502.

### W0 (Opus, 완료): `ai_routes.py`, `llm.py`

- 엔드포인트:
  - `GET /api/ai/config`: `has_api_key`, `external`, `presets`를 포함한다. 키 자체는 없다.
  - `PUT /api/ai/config`
  - `POST /api/ai/test/preview`
  - `POST /api/ai/test`
- `llm.preview(messages, purpose, json_output)`, `llm.complete(...)`, `llm.complete_json(...)` → `data`
- `llm.transport`는 테스트에서 가짜로 바꾼다.
- `llm.untrusted_block(label, text)`, `llm.UNTRUSTED_RULE`

### W1 (`knowledge.py`): 프로필·연결·그래프·갭·AI 분류

프로필:
- `GET /api/papers/{id}/profile` → `{"profile": {id, paper_id, origin, status, model, created_at, data} | null, "history": [{id, origin, status, model, created_at}]}`
- `POST /api/papers/{id}/profile/rules` → 규칙 프로필 생성 (201)
- `POST /api/papers/{id}/profile/ai/preview` / `POST /api/papers/{id}/profile/ai {preview_hash}` → LLM 프로필 (201)
  - 입력: 제목, 초록, 페이지 텍스트를 `max_input_chars` 안에서 쓴다. 앞부분과 결론·한계 단서 페이지를 우선한다. 페이지 텍스트는 `untrusted_block`으로 감싼다.
- `POST /api/papers/{id}/profile {data, origin: manual|agent, model?}` → 검증하고 구절을 다시 검사해 저장한다 (201).
- `PATCH /api/profiles/{profile_id} {status: draft|confirmed}`

연결:
- `GET /api/papers/{id}/links` → 양방향, 상대 논문 제목을 포함한다.
- `POST /api/paper-links {source_paper_id, target_paper_id, relation, note?, origin: manual|agent}`
  - 같은 논문끼리의 연결은 422, 중복은 409이다.
  - manual은 `accepted`, agent는 `suggested`로 저장한다.
- `PATCH /api/paper-links/{id} {status?, note?}`
- `DELETE /api/paper-links/{id}`
- `POST /api/library/links/discover {use_openalex: bool}`
  - 로컬 규칙 연결: 확정·추천 분야가 같거나 프로필 키워드·방법 토큰 Jaccard가 0.2 이상이면 `same_method`/`same_problem`/`related` 추천을 만든다.
  - `use_openalex`일 때: DOI가 있는 논문의 `referenced_works`를 서재 논문(DOI·OpenAlex ID)과 대조해 `cites`(accepted, openalex)를 만든다.
  - 사용자가 거절한 연결은 다시 만들지 않는다.
  - 반환: `{created, skipped, errors}`
- `GET /api/library/graph` → `{nodes: [{id, title, year, reading_status, categories: [name]}], edges: [{id, source, target, relation, origin, status}]}`. rejected 연결과 삭제된 논문은 빠진다.

갭:
- `POST /api/gaps/rules {paper_ids (1~20), project_id?}` → 규칙 갭 후보를 만들어 반환한다 (201). 같은 제목·같은 논문 집합의 후보는 중복 생성하지 않는다.
- `POST /api/gaps/ai/preview` / `POST /api/gaps/ai {paper_ids, project_id?, focus?, preview_hash}`
  - 논문은 `P1..Pn` 키로 보낸다. 응답의 paper 키가 목록 밖에 있으면 그 항목을 버린다.
- `GET /api/gaps?project_id=&paper_id=`
- `PATCH /api/gaps/{id} {status?, title?, description?}`
- `POST /api/gaps/{id}/to-idea {project_id}` → 아이디어를 만든다 (201).

AI 분류:
- `POST /api/papers/{id}/classify/ai/preview` / `POST /api/papers/{id}/classify/ai {preview_hash}`
- 기존 분야 이름 중에서 고른다. 결과는 `paper_categories`에 `source='llm'`, `status='suggested'`로 넣는다.
- 확정(confirmed)이나 거절(rejected)된 분류는 바꾸지 않는다.
- 목록에 없는 분야 이름은 `proposed_new`로만 반환한다.

### W2 (`research_agent.py`): 채팅과 연구 루프

채팅:
- `POST /api/chat/threads {title?, mode: idea|gap|free, project_id?, paper_ids: [], gap_ids: []}`
- `GET /api/chat/threads?project_id=`
- `GET /api/chat/threads/{id}` → thread와 messages를 반환한다.
- `DELETE /api/chat/threads/{id}`
- `PATCH /api/chat/threads/{id} {title?, paper_ids?, gap_ids?}`
- `POST /api/chat/threads/{id}/preview {content}` / `POST /api/chat/threads/{id}/messages {content, preview_hash}`
  - 사용자 메시지와 assistant 메시지를 저장하고 assistant 메시지를 반환한다.
  - 문맥: 모드별 시스템 지시, 논문 `[P1]..` 카드(제목·연도·초록·최신 프로필 요약), 갭 카드, 최근 대화 12개.
  - 모드 지시:
    - `idea`: Heilmeier 질문으로 구체화한다.
    - `gap`: 근거와 반례를 묻는다.
  - 인용 규칙: `[P1]`. 목록 밖 인용은 `meta.unknown_refs`로 표시한다.
- `POST /api/chat/messages/{message_id}/to-idea {project_id, title}`

연구 루프:
- `POST /api/research-runs/preview {topic, project_id?, seed_paper_ids?, max_iterations (1~3), papers_per_iteration (3~10)}` → `{policy, first_prompt: llm.preview(...), preview_hash}`
- `POST /api/research-runs {..., preview_hash}` → `ready` 상태의 실행을 만든다 (201). 외부 제공자이고 해시가 다르면 409이다.
- `GET /api/research-runs`
- `GET /api/research-runs/{id}` → run, steps, 현재 결과(state)를 반환한다.
- `POST /api/research-runs/{id}/step` → 다음 단계를 1개 실행한다.
- `POST /api/research-runs/{id}/advance` → 검토 지점까지 실행한다.
- `POST /api/research-runs/{id}/feedback {note?, focus_problem?: int}` → 다음 반복으로 진행한다.
- `POST /api/research-runs/{id}/cancel`
- `POST /api/research-runs/{id}/save {project_id, problems?: [int], contributions?: [int]}` → 아이디어와 갭으로 저장한다.

단계 정의:
- `plan_queries`: LLM이 질의 3~5개를 만든다.
- `search`: OpenAlex에서 공개 메타데이터를 가져온다. 시드 논문이 있으면 포함한다.
- `screen`: 근거 카드 `E1..`를 만든다. quote는 초록 문장이며, 초록 안에 있는지 검사한다.
- `problems`: 문제 후보를 만든다. 각 후보는 `evidence: [E#]`, `type`, `why_open`을 가진다.
- `methods`: 상위 문제마다 방법 개선안을 만든다.
- `contributions`: 기여 문장 초안을 만들고, 가장 가까운 선행 연구를 OpenAlex에서 검색한다. 참신성은 판정하지 않는다.
- `critique`: 별도 리뷰어 지시로 점수와 약점을 매기고 다음 질의를 만든다.

단계 기록:
- 각 단계의 입력 요약·출력·프롬프트 해시·모델·오류를 `research_steps`에 남긴다.
- 실패한 단계는 `failed`로 기록한다. 같은 단계를 다시 실행할 수 있다.

### W3 (`apps/web/research.js` + 최소 `app.js`/`index.html`/`style.css` 훅): UI

- 사이드바 "연구 도우미" 그룹: `연구 채팅`, `갭 찾기`, `자동 연구`, `연결 그래프`, `AI 설정`
- 논문 화면 `정보` 탭에 "논문 정리" 섹션:
  - 규칙/AI 정리 버튼
  - facet별 항목
  - 인용 구절과 일치 배지. 클릭하면 해당 페이지로 이동한다.
  - 확정 버튼
  - 연결 목록과 연결 추가
- 분야 화면에 "AI로 분류" 버튼 (읽은 논문에 차례로 실행)
- 모든 외부 전송 직전에 미리보기 대화상자를 띄운다: 제공자, 호스트, 글자 수, 메시지 전문 접기. "보내기"를 눌러야 전송한다. 로컬 제공자일 때는 보내는 내용 요약만 보이고 바로 실행한다.
- 그래프: 의존성 없는 SVG force layout (300 노드까지). relation 필터를 둔다. 노드를 클릭하면 논문을 연다.

### W4 (`integrations.py`, `services/mcp/*`): 에이전트 연동

- MCP 읽기 도구: `list_library_papers`, `get_paper_profile`, `get_library_graph`, `list_gaps`, `list_research_runs`, `get_research_run`
- MCP 초안 쓰기 도구: `save_paper_profile`, `suggest_paper_link`, `add_gap_candidate`
- 스킬: `services/mcp/skills/<name>/SKILL.md` 4종 (paper-profile, gap-finder, idea-refiner, research-loop). agentskills 규격을 따른다. name은 디렉터리와 같고, description은 1024자 이하이다.
- Obsidian 노트:
  - "연결된 논문": `accepted` 연결을 `[[citekey]]` 위키링크로 넣는다.
  - "논문 정리": 최신 프로필의 summary·problem·method·limitations를 넣는다.

## 수용 기준

- **AC1** 스키마
  - v6 DB가 v7로 이관되고 기존 행이 보존된다.
  - 새 DB는 v7 엄격 검증을 통과한다.
  - v7 백업은 검사와 복원을 통과한다.
  - 논문·프로젝트 영구 삭제 시 새 테이블 행도 지워지고 FK 오류가 없다.
- **AC2** 제공자
  - API 응답과 DB에 API 키가 나타나지 않는다.
  - 외부 제공자에서 해시가 없거나 다르면 409이다.
  - 로컬 제공자에서는 해시 없이 동작한다.
  - 제공자가 `none`이면 AI 엔드포인트가 400이고 규칙 기능은 동작한다.
- **AC3** 프로필
  - 규칙·AI·agent·manual 프로필이 버전으로 쌓인다.
  - quote 검사 결과가 `exact`/`normalized`/`not_found`로 표시되고, 다른 페이지에서 찾으면 `found_page`가 기록된다.
  - 잘못된 facet 키는 422이다.
  - 문서 텍스트는 untrusted 블록 안에서만 전송된다.
- **AC4** 연결과 그래프
  - 수동 연결 생성, 중복 409, 자기 연결 422가 동작한다.
  - discover가 규칙 추천을 만들고 거절한 연결은 다시 만들지 않는다.
  - OpenAlex 인용 대조가 동작한다 (모의 응답).
  - graph에서 rejected 연결과 삭제된 논문이 제외된다.
- **AC5** 갭
  - 1편과 여러 편 모두 규칙 갭이 만들어지고 근거(paper_id, facet, quote)가 붙는다.
  - AI 갭에서 목록 밖 paper 키는 버려진다.
  - 상태 변경과 아이디어 변환이 동작한다.
- **AC6** 채팅
  - 스레드와 메시지가 저장된다.
  - 미리보기 해시 규칙이 지켜진다.
  - 문맥에 선택 논문 카드가 들어가고, 개인 메모는 들어가지 않는다.
  - 목록 밖 인용이 표시된다.
  - 아이디어 변환이 동작한다.
- **AC7** 루프
  - 모의 LLM·검색으로 1회 반복 전 단계가 실행되고 `awaiting_review`에서 멈춘다.
  - feedback 후 2회차가 진행된다.
  - 예산 초과 시 `budget_exhausted`가 된다.
  - 단계 실패는 기록되고 재시도할 수 있다.
  - 근거 ID 검증으로 목록 밖 E#는 버려진다.
  - save가 아이디어와 갭을 만든다.
- **AC8** UI: 새 화면과 논문 정리 섹션이 브라우저에서 동작하고, 375px에서 가로 넘침이 없다. 실제 브라우저로 확인한다.
- **AC9** MCP·스킬
  - 새 도구 함수가 올바른 경로와 메서드를 호출한다 (단위 테스트).
  - SKILL.md frontmatter가 규격을 따른다.
  - Obsidian 노트에 위키링크와 정리가 들어간다.
- **AC10** 실제 확인: 로컬 Ollama(llama3-ko)로 프로필 1건, 채팅 1회, 루프 1단계 이상을 실제 실행한다. 외부 검색이 가능하면 루프 search도 실제로 실행한다.
- **AC11** 회귀: 기존 API 테스트, 상위 테스트, node UI 테스트가 Python 3.12와 3.9에서 통과한다.

## 작업 그래프와 담당

| ID | 내용 | 담당 | 파일 | 의존 |
|---|---|---|---|---|
| W0 | llm, ai_routes, 스키마 v7, 삭제 계획, 라우터 등록 | Opus | storage.py, library_management.py, main.py, llm.py, ai_routes.py | — |
| W1 | knowledge.py + tests/test_knowledge.py | Haiku A | knowledge.py, tests | W0 |
| W2 | research_agent.py + tests/test_research_agent.py | Haiku B | research_agent.py, tests | W0 |
| W3 | research.js, app.js 훅, index.html, style.css, UI 테스트 | Haiku C | apps/web/* | API 계약 |
| W4 | MCP 도구, 스킬, Obsidian 위키링크 + 테스트 | Haiku D | integrations.py, services/mcp/*, tests | API 계약 |
| W5 | 스키마·백업·삭제·제공자 테스트 | Opus | tests/test_ai_provider.py, 기존 스키마 테스트 갱신 | W0 |
| G | 통합 검증, 실제 Ollama 확인, 문서, 게이트 | Opus | docs | 전부 |

작업자 규칙:
- 지정 파일만 수정한다.
- `pip install`을 하지 않는다.
- `data/`를 쓰지 않는다. 테스트는 임시 폴더를 쓴다.
- sqlite 연결은 `closing()`으로 연다.

## 검증 계획

```
python -m unittest discover -s services/api/tests        # 3.12, 3.9
python -m unittest discover -s tests
node services/api/tests/*.cjs (래퍼 포함)
```

- 실제 확인: 임시 데이터 폴더의 데모 서버, 브라우저, Ollama.

## 진행

- [x] 조사 4건 (A 자동 연구, B 문헌·갭, C 에이전트 공학, D 제공자·그래프). 결과: [docs/research/](../../research/auto-research-landscape.md)
- [x] W0
- [x] W1–W4: Haiku 작업자 4명이 병렬로 구현했다. 파일은 겹치지 않았다.
- [x] W5
- [x] G: 통합 수정, 실제 확인. AC10 일부는 차단 상태이다 (아래).

## 검증 증거

모든 명령은 저장소 루트(`C:\Users\user\Desktop\EasyResearch`)에서 2026-11-10에 실행했다.

| 명령 | 결과 | 다룬 AC |
|---|---|---|
| `python -m unittest discover -s services/api/tests` (3.9.13, FastAPI 0.128) | Ran 310, OK (skipped=5), 종료 0 | AC1–AC7, AC11 |
| `C:/Users/user/anaconda3/python.exe -m unittest discover -s services/api/tests` (3.12.7, FastAPI 0.115.12) | Ran 310, OK (skipped=5), 종료 0 | 같음 |
| `python -m unittest discover -s tests` (3.9, 3.12) | Ran 44, OK | AC9, AC11 |
| `node services/api/tests/research_ui.test.cjs`, `node --check apps/web/{app,research}.js` | `research_ui ok`, 종료 0 | AC8 일부 |

새 테스트 파일:
- `test_ai_provider.py` (13개)
  - 키 비공개: API 응답, DB 덤프, 백업에 키가 없다.
  - 해시 409와 제공자 변경 시 해시 무효화.
  - Ollama 네이티브 경로.
  - v6→v7 이관과 스냅샷.
  - 논문·프로젝트 영구 삭제.
- `test_knowledge.py` (20개)
- `test_research_agent.py` (16개)
- `tests/test_easyresearch_mcp.py`: 도구 경로·헤더·untrusted, SKILL.md 규격.
- `test_integrations.py`: Obsidian 위키링크와 정리.
- 기존 백업 테스트 2개: v7 테이블을 지우는 픽스처로 갱신했다.

실제 확인 (데모 서버, 임시 데이터 폴더의 v6 보관함, Ollama 0.7.0 llama3-ko 8B Q5, RTX 4060):
- v6 데모 보관함이 v7로 이관되어 열렸다. 이관 전 스냅샷이 생성됐다.
- AI 설정 화면에서 Ollama 프리셋 저장과 연결 확인이 성공했다. 응답은 실제 모델이 했다.
- 규칙 프로필 (Distilling the Knowledge): facet별 항목, 원문 구절, "원문 일치" 배지, 페이지 링크가 나왔다.
- 연결 찾기로 규칙 연결 1개를 만들었다. 그래프에 노드 5개와 간선이 표시됐다 (배치 수정 후).
- 규칙 갭 (2편): 후보 25개, 근거 구절, 원문 일치 배지가 나왔다.
- 채팅 1회 (idea 모드, 논문 2편): 저장과 meta는 정상이었다. 그러나 llama3-ko가 답 대신 논문 카드를 되풀이했고, 목록 밖 키 "P3"을 썼다.
- 연구 루프 1회 반복을 실제 Ollama와 **실제 OpenAlex**로 실행했다.
  - 7단계가 모두 done이었고 약 3.7분 걸렸으며, 마지막 상태는 completed였다.
  - search: 후보 5편. screen: 근거 12개.
  - problems·methods·contributions·critique에서 각각 1건 이상이 나왔다.
  - 내용 품질은 낮았다 (영어 혼용, 얕음).
- 375px 너비: 새 화면 5개와 서재에서 가로 넘침이 없다 (scrollWidth 375). AI 설정 화면은 프리셋 버튼 줄바꿈을 수정한 뒤 통과했다.
- AI 프로필 저장: **실패.**
  - llama3-ko는 JSON 스키마를 강제하자 형식은 맞췄지만 facet이 비고 요약은 원문을 복사했다 (155초, 별도 스크립트).
  - 앱 경로에서는 120초와 300초 제한을 모두 넘겨 timeout이 났다.

모의 검증과 실제 검증의 구분:
- 외부 제공자(Gemini·Groq·OpenRouter)의 해시 흐름은 모의로만 검증했다. 실제 키로 호출하지 않았다.
- OpenAlex 인용 연결(discover use_openalex)은 모의로만 검증했다.
- 루프 검색은 실제로 검증했다.
- MCP 새 도구는 실제 MCP 클라이언트로 확인하지 않았다.

## 결정 기록

- 2026-11-10: D1–D7 채택. 근거는 조사 문서에 있다.
- 2026-11-10: 작업자 간 계약 추가: `POST /api/gaps` (manual|agent). MCP `add_gap_candidate`가 사용한다.
- 2026-11-10: W1 해석을 채택했다.
  - 대칭 관계(same_problem, same_method, related, contradicts)는 정렬한 순서로 저장한다.
  - AI 갭 근거 중 not_found 구절은 버린다.
  - found_page는 다른 페이지에서 찾았을 때만 기록한다.
- 2026-11-10: W2 해석을 채택했다.
  - focus_problem은 같은 제목의 문제로 다음 반복에 이어진다.
  - 0부터 세는 문제 번호를 쓴다.
  - 입력이 없는 단계는 skipped로 기록한다.
  - 로컬 제공자라도 해시를 주면 검사한다.
- 2026-11-10 (Opus): 통합 중 다음을 추가했다.
  - `llm.complete(schema=...)`: Ollama structured outputs로 프로필과 루프 단계의 출력 형식을 강제한다.
  - Ollama `num_ctx`를 입력과 출력을 함께 담는 크기로 늘렸다.
  - 프로필 정리기가 최상위 facet, 문자열 항목, 문자열 페이지를 받아들인다.
  - plan_queries가 빈 결과를 내면 주제로 검색한다 (`model_fallback` 기록).
  - UI와 응답 형식을 맞췄다 (evidence key, closest_prior, problem_index, config.max_iterations).
  - UTC 시각 표시, 그래프 배치(반발 반경 2k, 중심 인력), 프리셋 버튼 줄바꿈, 오류 detail.message 표시.
  - MCP의 서재 목록과 그래프도 untrusted로 감쌌다.

## 차단 요소

- **AC10 (실제 AI 프로필):** 설치된 llama3-ko 8B는 이 작업에 너무 느리고 약하다.
  - 진행 조건: 더 나은 무료 모델을 사용자 승인 후 내려받는 것. 후보는 Ollama `qwen3:8b` (약 5GB, 8GB VRAM에 맞음) 또는 `gemma3:4b`(빠름).
  - 또는 외부 무료 등급(Gemini 무료 키)을 선택한다.
  - 코드 경로(스키마 강제, 미리보기, 검증, 저장)는 테스트로 검증했다.

## 결과

- Sol 게이트 (Opus): AC1–AC9, AC11은 **PASS**이다. AC10은 루프와 채팅은 실제로 실행됐지만 프로필이 모델 한계로 **BLOCKED**이다.
- 따라서 이 계획은 `active`에 둔다. 더 나은 모델로 AC10 프로필을 확인하면 `completed`로 옮긴다.
