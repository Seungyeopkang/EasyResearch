# ExecPlan 005: 연구 루프 실행 안정화와 자기 점검 (개선안 1–5번)

- 상태: completed
- 크기: Large
  - 백그라운드 실행 엔진, LLM 전송 계층, OpenAlex 설정, UI를 함께 바꾼다.
  - API 동작도 바뀐다. `/step`·`/advance`는 202를 돌려주고, critique는 점수 대신 점검 결과를 낸다.
- 근거: [오케스트레이션 검증](../../research/orchestration-review.md) 4절 1순위 1–5번. 사용자가 2026-11-10에 구현을 승인했다.
- 역할 (사용자 지시):
  - 구현과 테스트: Haiku 작업자.
  - 계획, 검증, 게이트: Opus(Sol).

## 목표와 맥락

검증 문서에서 확인한 다섯 가지 문제를 고친다.

1. 연구 루프는 동기 HTTP 요청 안에서 전역 잠금을 잡고 실행한다. 그래서 취소가 진행 중인 LLM 단계가 끝날 때까지 기다리고, 그 뒤 `/advance`가 409로 끝난다 (가짜 LLM 시험에서 확인).
2. 재시도 정책, 원시 응답 기록, 실행 시간 예산이 없다.
3. 같은 모델이 "독립 리뷰어"로 1–5 점수를 매긴다. 참신성 점수는 선행 연구도 보지 않고 매긴다. 기여 문장은 한국어로 OpenAlex를 검색한다.
4. Ollama가 VRAM 부족으로 CPU에서 돌아도 앱이 알리지 않는다 (2026-11-10에 `100% CPU` 확인). `num_ctx`는 실제 입력 크기와 상관없이 정해진다.
5. OpenAlex 키는 환경 변수로만 받는다. 키가 없으면 같은 IP 사용자들과 하루 $0.10(검색 약 100회)를 나눠 쓴다. 남은 예산을 볼 수 없고 검색 캐시가 없다.

## 범위

- **W-A** (`services/api/app/llm.py`, `services/api/app/ai_routes.py`)
  - Ollama 스트리밍 전송과 중단 콜백(`should_stop`).
  - 호출 통계(stats).
  - 입력 크기에 맞춘 `num_ctx` 구간.
  - 실행 위치 확인(`runtime_status`)과 `GET /api/ai/status`.
- **W-B** (`scholarly.py`, 새 `openalex_routes.py`, `main.py`, `categories.py`)
  - OpenAlex 키 저장과 우선순위.
  - 예산 헤더 기록.
  - 검색 캐시.
  - 429 한국어 안내.
  - 설정 API.
- **W-C** (`research_agent.py`, `services/mcp/skills/easyresearch-research-loop/SKILL.md`)
  - 백그라운드 작업자, 실행별 잠금, 즉시 취소.
  - 재시도 정책, 원시 응답 기록과 재사용, 실행 시간 예산.
  - 자기 점검(critique 개편).
  - 기여 검색어(`search_query`).
  - OpenAlex 키 호출부.
- **W-D** (`apps/web/research.js`, `apps/web/style.css`)
  - 상태 조회(polling), 즉시 취소, 진행 표시.
  - 점검 결과 표시, 원시 응답 보기.
  - 실행 시간 예산 입력.
  - 로컬 모델 상태와 OpenAlex 설정 화면.
- **W-T** (`services/api/tests/` 아래 테스트만)
  - 수용 기준에서 도출한 테스트.
  - API 변경으로 깨지는 기존 테스트 수정.
- **Sol**: README, `docs/implementation-status.md`, 이 계획, 통합 검증, 게이트.

## 하지 않는 것

- DB 스키마 변경. 새 정보는 기존 `state_json`, `config_json`, `research_steps.output_json`에 넣는다. 그래서 백업 형식은 바뀌지 않는다.
- 외부 OpenAI 호환 제공자의 스트리밍. 이 경로는 보내기 전에만 중단을 확인한다.
- 앱 안 다중 에이전트, 모델 다운로드, MCP sampling.
- 개선안 6번 이후 (AI 정리 재설계, 인용 따라가기 검색 등).

## API·데이터 계약

### W-A: llm.py

- `complete(messages, *, purpose, preview_hash=None, json_output=False, max_tokens=2000, schema=None, should_stop=None) -> dict`
  - `should_stop`: 인자 없는 함수이다. 계속하려면 `None`(또는 거짓 값)을, 멈추려면 이유 문자열(한국어)을 돌려준다.
  - 보내기 전에 `should_stop()`이 이유를 돌려주면 `LLMError("stopped", 이유)`를 던진다.
  - `schema`와 `should_stop`은 값이 있을 때만 transport에 넘긴다. 기존 테스트의 가짜 transport와 호환하기 위해서이다.
  - 반환값: `{"text", "model", "provider", "preview_hash", "stats"}`. `stats`는 Ollama 호출 통계이고, 없으면 `None`이다.
- `_http_transport(config, messages, *, json_output, max_tokens, schema=None, should_stop=None) -> str`
  - **Ollama**:
    - 요청은 `stream: true`로 보내고, `num_ctx`는 `ollama_num_ctx(messages, max_tokens)`로 정한다.
    - 응답의 NDJSON 줄을 읽어 `message.content`를 이어 붙인다.
    - 줄을 하나 읽을 때마다 `should_stop`을 확인한다. 이유가 오면 응답을 닫고 `LLMError("stopped", 이유)`를 던진다.
    - 소켓 timeout(설정 `timeout`)은 줄과 줄 사이의 무응답 제한으로 동작한다.
    - `{"error": ...}` 줄이 오면 `http_error`로 처리한다.
    - 누적 크기가 `MAX_RESPONSE_BYTES`를 넘으면 `invalid_response`로 처리한다.
    - `done: true` 줄의 통계를 thread-local에 저장한다. 필드: `prompt_eval_count`, `eval_count`, `prompt_eval_s`, `eval_s`, `load_s`, `total_s`, `num_ctx`.
  - **OpenAI 호환**: 비스트리밍을 유지한다. 보내기 전에만 `should_stop`을 확인한다.
  - HTTP 오류 매핑은 기존과 같다 (`rate_limited`, `auth_error`, `http_error`, `timeout`, `network_error`). `LLMError.status`에는 HTTP 코드를 담는다.
- `ollama_num_ctx(messages, max_tokens) -> int`
  - 추정 토큰 = 한글 글자 수 + (나머지 글자 수 / 3, 올림) + `max_tokens` + 512.
  - 한글 범위: U+AC00–D7A3, U+1100–11FF, U+3130–318F.
  - 추정값 이상인 가장 작은 구간을 고른다: `(4096, 8192, 16384, 32768)`. 모두 넘으면 32768이다.
- 실행 위치 확인:
  - `runtime_probe: Callable[[str], list]`의 기본값은 `_http_runtime_probe(base_url)`이다.
    - `GET {base_url}/api/ps`를 timeout 3초로 부른다.
    - 반환: `[{"name", "size", "size_vram"}]`.
    - 실패하면 `LLMError("network_error")`를 던진다.
    - 테스트는 이 함수를 가짜로 바꾼다.
  - `runtime_status(config=None) -> dict`
    - 제공자가 `ollama`가 아니거나 `base_url`이 로컬이 아니면 `{"applicable": False, "provider": ...}`를 돌려준다. 이때 probe를 **절대 호출하지 않는다**.
    - probe가 실패하면 `{"applicable": True, "reachable": False, "models": [], "warning": None}`를 돌려준다.
    - 성공하면 아래 필드를 돌려준다.
      - `applicable`(`True`), `reachable`(`True`).
      - `models`: 모델마다 `{name, size, size_vram, gpu_percent}`.
      - `configured_model`, `configured_loaded`, `configured_gpu_percent`.
      - `warning`.
    - `gpu_percent = round(100 * size_vram / size)`를 0–100으로 자르고, `size`가 0 이하이면 0이다.
    - 설정 모델 이름 일치 규칙: 이름이 정확히 같거나, 설정에 태그가 없으면 `이름 + ":latest"`와 같으면 일치로 본다.
    - 경고: 설정 모델이 메모리에 올라 있고 `gpu_percent < 90`이면 한국어 경고 문자열을 만든다. 0%이면 "전부", 그 외에는 "일부" CPU에서 실행 중이라고 쓴다. GPU %를 넣고, 다른 GPU 프로그램을 닫으라고 안내한다.
- ai_routes.py
  - `GET /api/ai/status` → `{"provider", "model", "runtime": runtime_status(config)}`.
  - `POST /api/ai/test` 응답에 `runtime`을 추가한다.
  - `llm_http_error`는 `stopped` 코드를 409로 돌려준다.

### W-B: OpenAlex

- **scholarly.py: 키**
  - `openalex_key()`: 환경 변수 `OPENALEX_API_KEY`(공백 제거)가 있으면 그것을 쓴다. 없으면 `data/secrets/openalex_api_key` 파일을 쓰고, 그것도 없으면 `None`이다.
  - `openalex_key_source()`: `"env"`, `"file"`, `None` 중 하나이다.
  - `save_openalex_key(api_key, clear=False)`
    - 형식 검사: 8–200자, 출력 가능한 ASCII, 공백 없음. 어기면 `ValueError`를 던진다.
    - 저장: 파일 하나에 쓴다.
    - `clear=True`이면 파일을 지운다.
- **scholarly.py: 예산 기록**
  - `_get`이 OpenAlex 응답을 받을 때마다 헤더를 기록한다. HTTP 오류 응답도 포함한다.
    - `X-RateLimit-Remaining-USD`, `X-RateLimit-Limit-USD`, `X-RateLimit-Reset`(초), `X-RateLimit-Credits-Used`, `X-RateLimit-Cost-USD`.
    - `observed_at`(UTC ISO, `Z`)과 `keyed`(요청에 Authorization 헤더가 있었는지)도 함께 기록한다.
  - `openalex_budget()`은 기록의 사본을 돌려주고, 기록이 없으면 `None`이다.
- **scholarly.py: 검색 캐시**
  - `search_openalex`는 결과를 메모리 LRU에 캐시한다. 최대 256개, TTL 24시간, 키는 (공백 정규화한 소문자 질의, limit)이다.
  - 성공한 결과만 캐시하고, 꺼낼 때는 깊은 복사본을 준다.
  - `clear_openalex_cache()`로 비울 수 있다.
  - `api_key=None`이면 `openalex_key()`를 쓴다.
- **scholarly.py: 429**
  - OpenAlex 429는 코드 `rate_limited`, 상태 429로 처리한다.
  - 메시지는 한국어로, 무료 OpenAlex 키를 AI 설정에서 넣으면 하루 약 1,000회까지 검색할 수 있다고 안내한다.
- **openalex_routes.py**
  - `GET /api/settings/openalex` 응답 필드:
    - `has_key`, `source`, `budget`.
    - `free_key_url`: `https://openalex.org/settings/api`.
    - `keyless_note`: 키 없이 쓸 때의 한국어 안내.
    - **키 값은 절대 돌려주지 않는다.**
  - `PUT /api/settings/openalex {api_key?: str, clear_key?: bool}`
    - 저장한 뒤 GET과 같은 형태로 응답한다.
    - 형식 오류는 422이다.
- **main.py**: 라우터를 등록한다. 검색 경로는 `scholarly.openalex_key()`를 쓰고, `rate_limited`이면 429와 메시지를 돌려준다.
- **categories.py**: `_openalex_headers()`는 `scholarly.openalex_key()`를 쓴다. 429는 같은 한국어 안내로 처리한다.
  - knowledge.py 연결 찾기는 이 함수를 쓰므로 함께 바뀐다.

### W-C: 연구 엔진 (research_agent.py)

- **설정**
  - `RunConfigIn.max_run_minutes`: 5–240, 기본 45.
  - 이 값으로 `config["max_run_seconds"]`를 만든다.
  - 이전 실행에 이 값이 없으면 2700으로 본다.
- **실행 요청과 응답**
  - `POST /{id}/step`, `POST /{id}/advance`
    - 실행별 잠금 안에서 상태를 확인한다. 진행할 수 없으면 409 `run_not_steppable`, 이미 작업자가 돌고 있으면 409 `run_busy`이다.
    - 상태를 `running`으로 바꾸고, 데몬 작업자 스레드를 시작한 뒤, **202**와 상세 정보를 돌려준다.
    - `step`은 한 단계만, `advance`는 `ready`가 아닐 때까지 진행한다.
  - `POST /cancel`
    - 잠금을 짧게만 잡고 즉시 `cancelled`로 기록한 뒤, 작업자의 취소 이벤트를 켜고 200을 돌려준다.
    - 이미 끝났으면 409이다.
  - `POST /feedback`: 작업자가 돌고 있으면 409 `run_busy`이다.
- **잠금과 저장**
  - 전역 `RUN_LOCK`은 없앤다.
  - 실행별 잠금은 DB를 읽고 고치는 짧은 구간에만 쓰고, LLM 호출 중에는 잡지 않는다.
  - 상태 저장은 `status != 'cancelled'` 조건부 UPDATE로 한다. 영향 행이 0이면 취소된 것으로 본다.
- **단계 기록 (`research_steps`)**
  - 상태 값: `running`, `done`, `failed`, `cancelled`.
  - 취소되면 진행 중이던 단계는 `cancelled`가 된다.
  - LLM이 응답하면 해석 전에 원시 응답을 즉시 저장한다: `{"raw_response": 최대 20,000자, "raw_truncated": bool, "attempt": n}`와 `prompt_hash`.
  - 단계가 끝나면 출력은 상태에 따라 이렇게 남긴다.

    | 상태 | 출력 |
    |---|---|
    | done | 단계 출력과 `attempts`, `stats`, `runtime`. `replayed_from_step`은 해당할 때만. |
    | failed | `raw_response`(있을 때), `raw_truncated`, `attempts` |

- **재사용 (멱등 재실행)**
  - 같은 반복·같은 단계에서 중단 표시("중단된 단계입니다. 다시 실행하세요.")로 끝난 이전 단계가 있으면, 그 단계의 원시 응답을 다시 쓴다.
  - 조건: `prompt_hash`가 같고, 원시 응답이 잘리지 않았어야 한다.
  - 이때는 LLM을 부르지 않으므로 호출 수에 넣지 않는다.
- **재시도**
  - 일시 오류는 1회만 자동 재시도한다. 일시 오류: `timeout`, `network_error`, `rate_limited`, `http_error` 중 상태 500 이상.
    - 대기 시간은 `_backoff_seconds()`(2–5초 무작위)이다.
    - 취소 이벤트가 켜지면 기다리지 않고 바로 깬다.
  - 형식이나 검증 실패는 이유를 붙여 1회 다시 묻는다. 이전 응답(assistant)과 이유를 담은 user 메시지를 덧붙인다.
  - 그 밖의 오류(`auth_error`, 4xx 등)는 바로 실패한다.
  - 시도마다 `llm_calls`에 넣는다. 호출 예산을 넘으면 단계는 실패하고, 실행은 `budget_exhausted`와 `stop_reason: "calls"`로 끝난다.
- **실행 시간 예산**
  - `state.elapsed_seconds`에는 단계가 실제로 실행된 시간만 더한다. 검토 대기 시간은 넣지 않는다.
  - 단계를 시작하기 전에 예산을 넘었으면 실행은 `budget_exhausted`, `stop_reason: "time"`으로 끝난다.
  - LLM 호출 중 기한이 지나면 `should_stop`으로 멈춘다. 그 단계는 `failed`(시간 예산 오류 메시지), 실행은 `budget_exhausted`/`time`이다.
- **실행 정보 (`_run_view`)**
  - 추가 필드: `busy`, `elapsed_seconds`, `max_run_seconds`, `stop_reason`, `runtime_warning`, `max_llm_calls`.
  - 목록 API에도 `busy`를 넣는다.
- **실행 위치 기록**: Ollama 호출이 성공하면 `llm.runtime_status()` 결과를 단계 출력의 `runtime`(gpu_percent, warning)에 넣는다. 경고가 있으면 `state.last_runtime_warning`에도 넣는다.
- **자기 점검 (critique) 출력**
  - JSON 형태: `{"weaknesses": [{"text": str, "refs": [str]}], "next_queries": [str]}`.
  - 점수는 없다.
  - 키 규칙:
    - 프롬프트에 쓰는 키: 문제 `P1..`, 방법 `M1..`, 기여 `C1..`, 근거 `E#`. 기여마다 가장 가까운 선행 연구 제목을 함께 보여준다.
    - 유효한 키가 없는 약점은 버리고 그 수를 `dropped_uncited`에 센다.
    - 약점은 최대 8개, 문장은 최대 300자이다.
  - `state.critique` 필드:
    - `weaknesses`: `[{text, refs}]`.
    - `next_queries`.
    - `checks`: 코드가 계산한 점검.
      - 문제마다 `key`, `title`, `evidence_count`, `source_papers`, `seed_evidence`, `flags`. 근거 논문이 2편 미만이면 `flags`에 `single_source`.
      - 방법마다 `key`, `problem`, `evidence_inherited`, `flags`. 근거를 이어받았으면 `inherited_evidence`.
      - 기여마다 `key`, `search_query`, `closest_prior_count`, `prior_overlap`, `prior_overlap_label`, `flags`. 플래그는 `no_prior_found`, `prior_search_failed`, `high_prior_overlap` 중 해당하는 것.
      - `summary`: 플래그별 개수.
    - `dropped_uncited`.
    - `note`: 점검 안내 문구.
  - 이전 형식(`scores`, 문자열 약점)의 실행도 읽고 피드백할 수 있어야 한다.
- **기여 단계**
  - 출력 형태: `{"contributions": [{"statement": 한국어, "search_query": 영어 12단어 이내}]}`.
  - 가장 가까운 선행 연구는 `search_query`로 검색한다. 검색어가 3자 미만이거나 형식이 틀리면 문장 앞부분(300자)으로 검색한다.
  - 검색 때 받은 제목과 초록 앞 600자로 `prior_overlap`을 계산한다.
    - 값: 검색어 단어 중 검색 결과에 나오는 비율의 최댓값.
    - 단어 분리: 기존 `_terms`.
    - 라벨: 0.6 이상 "높음", 0.3 이상 "보통", 그 아래 "낮음".
  - 프롬프트에서 근거 없는 E 키 인용 지시를 뺀다.
- **방법 단계**: 문제의 근거를 이어받았으면 `evidence_inherited: true`를 남긴다.
- **반복 요약과 다음 반복**
  - 반복 요약에서 `scores`를 빼고 `check_summary`를 넣는다.
  - 다음 반복으로 넘길 약점은 문장만 넘긴다. 이전 형식의 문자열 약점도 받는다.
- **OpenAlex 호출부**: `scholarly.openalex_key()`를 쓴다.
- **테스트용 연결점**
  - `_join_workers(timeout)`: 테스트 정리 시 작업자 종료를 기다린다.
  - `_backoff_seconds()`: 테스트에서 0으로 바꿀 수 있다.

### W-D: UI

- **실행 화면**
  - 단계 실행이나 검토 지점까지 실행을 누르면 202를 받는다. 그 뒤 `busy`가 거짓이 될 때까지 2초마다 조회해 다시 그린다.
    - 조회는 실행당 하나만 돌고, 화면을 떠나면 멈춘다.
    - 이미 진행 중인 실행을 열어도 조회를 시작한다.
  - 진행 줄을 보여준다: 현재 단계, 경과 시간/예산(분), AI 호출 수/최대. 함수 `runProgressText(run)`을 export한다.
  - 진행 중에는 중단 버튼만 쓸 수 있다.
  - 상태가 `running`인데 `busy`가 아니면 "멈춤 · 다시 실행 가능"으로 표시한다.
  - `budget_exhausted`는 `stop_reason`에 따라 시간 예산인지 호출 예산인지 설명한다.
  - `runtime_warning`이 있으면 경고를 표시한다.
- **자기 점검 영역**
  - 약점마다 키 칩을 붙인다 (`P1` → 문제 #1 등). E 칩에는 원문 구절을 보여준다.
  - 점검 플래그는 `CHECK_FLAG_LABELS`(export)로 표시한다.
  - 이전 형식 점수는 "이전 형식 점수(참고용)"로 표시한다.
- **기여**: 선행 연구 검색어와 겹침 라벨을 보여준다.
- **방법**: "근거 이어받음" 표시를 붙인다.
- **단계 기록**: 상태를 한국어로 표시한다 (`cancelled`는 "취소됨"). 시도 횟수와 재사용 여부, "AI 원문 보기"(`raw_response` 앞 4,000자, 이스케이프한 `<pre>`)를 보여준다.
- **시작 양식**: "실행 시간 예산(분)" 입력(5–240, 기본 45)을 추가한다.
- **AI 설정 화면**
  - "로컬 모델 상태" 영역: Ollama일 때 `GET /api/ai/status`로 모델별 GPU %와 경고를 보여준다.
  - 연결 확인 결과에 `runtime.warning`이 있으면 함께 보여준다.
  - "OpenAlex 검색" 영역에 보여줄 것:
    - 키 상태와 출처.
    - 남은 하루 예산과 다시 채워지기까지 남은 시간.
    - 키 입력(password)과 삭제, 저장.
    - 무료 키 받기 링크(`rel="noopener noreferrer"`).
- **AI 실행 후 경고**: AI 정리와 채팅 응답이 끝나면 `/api/ai/status`를 확인해 경고가 있으면 알린다. 실패해도 조용히 넘어간다.
- **모바일**: 375px에서 가로 넘침이 없어야 한다.

## 수용 기준

- **AC1** 백그라운드 실행
  - LLM 단계가 3초 걸려도 `/step`·`/advance`는 1초 안에 202를 돌려준다.
  - 실행 중에는 `busy=true`·`running`이다. 끝나면 `awaiting_review`나 `completed`가 되고 `busy=false`이다.
  - 실행 중에 다시 `/advance`를 보내면 409 `run_busy`이다.
- **AC2** 즉시 취소
  - LLM 단계 진행 중에 `/cancel`을 보내면 1초 안에 200이 온다.
  - 실행은 `cancelled`로 끝나고 진행 중 단계도 `cancelled`가 된다. 이후 상태가 덮어써지지 않는다.
  - Ollama 스트리밍은 `should_stop`이 이유를 돌려준 뒤 다음 줄을 읽기 전에 멈춘다.
- **AC3** 실행 격리: 실행 A가 느린 단계를 진행하는 동안에도 실행 B의 조회와 단계 진행이 막히지 않는다.
- **AC4** 재시도
  - 일시 오류는 정확히 1회 재시도한 뒤 `failed_step`이 된다.
  - 검증 실패는 이유를 담아 정확히 1회 다시 묻는다.
  - 인증 오류와 4xx는 다시 시도하지 않는다.
  - 모든 시도는 `llm_calls`에 들어가고, 호출 예산을 넘으면 `budget_exhausted`/`calls`가 된다.
- **AC5** 원시 응답
  - 검증에 실패한 단계 출력에 `raw_response`와 `attempts`가 남는다.
  - 중단 표시로 끝난 단계는 같은 프롬프트로 다시 실행하면 LLM을 부르지 않는다. 대신 저장된 응답을 쓰고 `replayed_from_step`을 남긴다.
- **AC6** 실행 시간 예산
  - 누적 실행 시간이 예산에 닿으면 `budget_exhausted`, `stop_reason: "time"`으로 끝난다.
  - 진행 중인 LLM 호출도 기한이 지나면 멈춘다.
  - 검토 대기 시간은 예산에 넣지 않는다.
  - 예산 값이 없는 이전 실행은 2700초로 동작한다.
- **AC7** 자기 점검
  - critique에 `scores`가 없다.
  - 약점마다 보여준 키 중 하나 이상을 인용하고, 인용 없는 약점은 버려지며 그 수를 센다.
  - `checks` 필드가 계약대로 계산된다.
  - 기여의 선행 연구 검색은 `search_query`를 쓴다.
  - 이전 형식 실행도 피드백할 수 있다.
  - UI 이름은 "자기 점검 (같은 모델)"이다.
- **AC8** 실행 위치
  - `GET /api/ai/status`는 로컬 Ollama에서 `/api/ps`로 GPU %를 계산하고, 90% 미만이면 한국어 경고를 돌려준다.
  - 로컬이 아니거나 Ollama가 아닌 제공자에서는 probe를 부르지 않는다.
  - 연구 단계는 `runtime`을 기록한다.
- **AC9** `num_ctx`: Ollama 요청은 계약에 정한 추정식과 구간 `{4096, 8192, 16384, 32768}`을 따른다.
- **AC10** OpenAlex 키
  - 키는 `data/secrets/openalex_api_key`에 저장하고, 환경 변수가 우선한다.
  - GET 응답, DB, 백업 어디에도 키가 나오지 않는다.
  - 검색, 분야 분류, 연결 찾기, 연구 루프 모두 `openalex_key()`를 쓴다.
- **AC11** OpenAlex 예산·캐시
  - 응답 헤더의 예산을 설정 API로 볼 수 있다.
  - 같은 질의는 TTL 안에서 HTTP 없이 캐시로 처리한다.
  - 429는 `rate_limited`와 무료 키 안내 메시지가 된다.
- **AC12** UI: AC1·2·7·8·10·11의 화면 동작이 있다. 375px에서 가로 넘침이 없다. Node UI 테스트를 통과한다.
- **AC13** 회귀
  - API 테스트 전체, 상위 테스트, Node UI 테스트가 Python 3.9와 3.12에서 통과한다.
  - 구조 점검을 통과한다.
  - README, 구현 현황, 스킬 문서를 갱신한다.
- **AC14** 실제 확인
  - 데모 서버에서 실제 OpenAlex 예산 헤더를 표시한다.
  - `/api/ai/status`가 실제 Ollama 실행 위치를 보고한다.
  - 사용자 GPU 작업이 돌고 있으면 실제 모델 추론 대신 가짜 LLM으로 확인하고, 그 사실을 기록한다.

## 작업 그래프와 담당

| 단계 | 작업 | 담당 | 의존 |
|---|---|---|---|
| 1 | W-A llm·ai_routes | Haiku 작업자 A | 없음 |
| 1 | W-B OpenAlex | Haiku 작업자 B | 없음 |
| 1 | W-D UI | Haiku 작업자 D | 계약만 |
| 2 | W-C 연구 엔진 | Haiku 작업자 C | W-A, W-B 통합 후 |
| 2 | W-T 테스트 | Haiku 테스트 작업자 | 수용 기준. 최종 실행은 통합 후 |
| 3 | 통합 검증, 실제 확인, 문서, 게이트 | Opus | 1, 2 |

작업자들은 서로의 파일을 건드리지 않는다. W-T는 운영 코드를 고치지 않는다.

## 검증 계획

- API 테스트: `cd services/api && python -m unittest discover -s tests`. Python 3.9와 3.12에서 실행한다.
- 상위 테스트: 저장소 루트에서 `python -m unittest discover -s tests`.
- Node UI 테스트: `node services/api/tests/research_ui.test.cjs`.
- 구조 점검: `python scripts/check_development_structure.py`.
- 실제 확인: 임시 데이터 폴더의 데모 서버에서 확인한다.
  - OpenAlex 실제 검색 1회와 예산 표시.
  - `/api/ai/status` 실제 응답.
  - 가짜 LLM 없이는 무거운 추론을 하지 않는다 (사용자 GPU 작업 보호).
  - 375px 화면에서 넘침 확인.

## 진행

- [x] 계획과 계약 작성 (Opus)
- [x] W-A, W-B, W-D (Haiku). Opus가 diff를 검토했다. `main.py` 공백 하나를 고쳤다.
- [x] W-C, W-T (Haiku). W-T가 찾은 경쟁 조건은 Opus가 고쳤다: `busy`를 행보다 먼저 읽는다.
- [x] 통합 검증
- [x] 실제 확인
- [x] 문서와 게이트

## 검증 증거

| 명령·확인 | 결과 | 수용 기준 |
|---|---|---|
| `python -m unittest discover -s services/api/tests` (3.12.7) | Ran 367, OK (skipped=5), 종료 0 | AC1–AC11, AC13 |
| 같은 명령 (3.9.13) | Ran 367, OK (skipped=5), 종료 0 | AC13 |
| `python -m unittest discover -s tests` (3.12) | Ran 44, OK | AC13 |
| `node services/api/tests/research_ui.test.cjs` | research_ui ok | AC12 |
| `python scripts/check_development_structure.py` | passed | AC13 |
| 엔진 테스트 3회 반복, 경쟁 조건 재현 스크립트 | 모두 OK. 재현 결과 `status=awaiting_review busy=False` | AC1 |
| 실제 서버(데모 데이터 사본) + 로컬 llama3-ko | `/advance` 202 (0.01초). 다시 보내면 409 `run_busy`. 1회 반복 `completed`, 34초, 호출 5회, GPU 94% 기록 | AC1, AC8, AC14 |
| 실제 취소 | 200 (0.01초). 작업자는 1.1초 뒤 멈춤. 실행·단계 모두 `cancelled` | AC2, AC14 |
| 실제 OpenAlex | 검색 1.4초. 같은 검색 다시 0.03초(캐시). 예산 $0.098/$0.1(키 없음) 표시 | AC11, AC14 |
| 실제 자기 점검 | `scores` 없음. 약점에 키 인용. `high_prior_overlap` 표시 | AC7 |
| 375px 브라우저 | AI 설정·실행 화면 가로 넘침 없음. "자기 점검 (같은 모델)"과 진행 줄 표시 | AC12 |

남은 한계는 다음과 같다.

- Ollama가 프롬프트를 처리하는 동안에는 첫 토큰이 나올 때까지 취소가 늦을 수 있다.
- `num_ctx` 구간이 바뀌면 모델을 다시 올리며 약 2초 걸린다 (D6).
- 일반적인 검색어는 선행 연구 겹침이 "높음"으로 나오기 쉽다. 이 값은 신호일 뿐이다.

## 결정 기록

- **D1** 실행은 프로세스 안의 데몬 스레드로 한다. 앱은 단일 사용자·단일 프로세스(`server.lock`)이므로 작업 큐 서버는 두지 않는다. 서버가 다시 시작되면 `running`이면서 `busy`가 아닌 실행은 사용자가 다시 실행한다.
- **D2** 단계 캐시는 "응답을 받은 뒤 중단된 단계의 원시 응답 재사용"으로 한정한다.
  - 검증에 실패한 응답은 재사용하지 않는다. 같은 잘못된 응답이 반복되기 때문이다.
  - 단일 프로세스에서는 응답과 저장 사이에 중단될 일이 드물다. 그래서 효과는 작지만 비용도 작다.
- **D3** 숫자 점수(참신성 포함)는 없앤다. 근거는 같은 모델의 자기 선호 편향과, 외부 신호 없는 자기 교정 실패이다. 판정 대신 코드 점검과 인용된 약점만 남긴다.
- **D4** 선행 연구 겹침은 영어 검색어와 영어 검색 결과로만 계산한다. 한국어 문장과 영어 초록 사이의 단어 겹침은 의미가 없기 때문이다.
- **D5** OpenAlex 검색 캐시는 메모리에만 둔다. 스키마를 바꾸지 않고, 재시작하면 비워진다.
- **D6** `num_ctx`는 구간으로만 바꾼다. 값이 바뀌면 Ollama가 모델을 다시 올리기 때문이다.

## 차단 요소

- 없음. 사용자 GPU 작업이 실행 중이면 실제 LLM 추론 확인은 하지 않는다 (AC14).

## 결과

- Sol 게이트 (Opus): **PASS**. AC1–AC14를 모두 충족했고 증거는 위 표에 있다.
- 상태: completed.
