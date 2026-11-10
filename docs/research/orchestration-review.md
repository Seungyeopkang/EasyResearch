# 오케스트레이션·서브에이전트 설계 검증과 개선안

- 조사일: 2026-11-10
- 대상: 연구 도우미 1차 구현(ExecPlan 004)의 연구 루프, 채팅, 안전장치, MCP·스킬, 논문 정리·연결·갭·분야 정리. 외부 제공자와 MCP 실제 연결처럼 아직 연결하지 않은 부분은 범위에서 뺐다.
- 방법:
  - Haiku 조사 에이전트 5개가 출처 약 210건(중복 포함)을 기록했다. 원본은 아래 표의 보고서 E–I에 있다.
  - Opus가 판정에 쓰는 핵심 주장을 원문 검색과 실제 API 호출로 다시 확인했다.
  - 코드 동작은 가짜 LLM을 쓴 시험과 이 PC의 실행 상태로 확인했다.
- 표기:
  - `[확인]`: Opus가 원문 또는 실제 호출로 확인했다.
  - `[V]`: 조사 에이전트가 원문을 열어 확인했다.
  - `[S]`: 검색 요약으로만 확인했다.
  - `[추론]`: 출처가 직접 보여주지 않으며 시험이 필요하다.

| 보고서 | 범위 |
|---|---|
| [E](raw/E-orchestration-architecture.md) | 워크플로 대 에이전트, 다중 에이전트의 득실, 오케스트레이터 설계, 딥리서치 구조 (출처 49건) |
| [F](raw/F-subagents-loops-durability.md) | 서브에이전트, 루프·맥락 공학, 내구성 있는 실행, 예산, 자기 교정의 한계 (45건) |
| [G](raw/G-research-loop-systems-hci.md) | 연구 자동화 시스템의 루프 구조, 사람 개입 지점, 인간-AI 아이디어 도구 HCI 연구 (40건) |
| [H](raw/H-extraction-links-gaps-taxonomy.md) | 작은 모델의 구조화 추출, 논문 연결, 갭 탐지, 분야 분류 (40건) |
| [I](raw/I-safety-hitl-mcp-skills.md) | 프롬프트 주입 방어, 승인 설계, 최신 MCP 규격, 에이전트 스킬 (약 40건) |

## 1. 결론

- **큰 구조는 유지한다.** 코드가 단계 순서를 정하는 워크플로, 앱 안의 단일 상태, 반복마다 사람이 검토하는 지점, 참신성을 판정하지 않는 원칙은 근거와 맞는다.
- **고칠 곳은 다섯 가지이다.**
  1. 실행 방식: 동기 HTTP 요청과 전역 잠금 때문에 취소가 늦고 실패가 불명확하다.
  2. 같은 모델의 자기 비평과 숫자 참신성 점수: 근거상 신뢰하기 어렵다.
  3. 근거 품질: 초록 문장만 쓰고, 용어 겹침으로 고른다.
  4. AI 논문 정리의 호출 방식과 로컬 모델 실행 위치.
  5. OpenAlex 키와 하루 예산.
- **하지 않는다.**
  - 앱 안의 다중 에이전트나 토론.
  - MCP sampling에 기대는 설계.
  - Semantic Scholar 인용 의도로 관계 유형을 자동 분류하는 것.

## 2. 오늘 직접 확인한 사실 `[확인]`

### 2.1 로컬 모델이 GPU가 아니라 CPU에서 돌았다

- `ollama ps`에 llama3-ko 6.4GB가 `100% CPU`로 표시됐다.
- `nvidia-smi`로 보니 GPU 8GB 중 6.2GB를 다른 프로그램이 쓰고 있었다. 사용자의 CUDA 실험 프로세스와 여러 데스크톱 앱이다.
- 같은 조건에서 AI 정리 호출은 10분이 넘도록 끝나지 않았다. 사용자 실험과 CPU를 다투지 않도록 시험을 중단하고 모델을 메모리에서 내렸다.
- 해석:
  - AC10 실패의 원인이 모델 품질만은 아닐 수 있다. VRAM이 부족하면 Ollama가 조용히 CPU로 내려가서 수 배 느려진다.
  - 이전 실패 시점에 모델이 어디서 돌았는지는 확인하지 못했다.
- 앱의 현재 동작: 이 상태를 감지하지 않는다.

### 2.2 실행 중에는 취소가 바로 되지 않는다

- 시험: LLM 호출 하나에 3초가 걸리는 가짜 LLM으로 `/advance`를 실행하고, 그 중간에 `/cancel`을 보냈다.
- 취소 요청은 진행 중인 단계가 끝날 때까지 2.2초를 기다렸다.
- 그 뒤 `/advance`는 성공이 아니라 409(`run_not_steppable`)로 끝났다.
- 원인: `_execute_step`이 LLM 호출 내내 전역 `RUN_LOCK`을 잡고 있고, `/cancel`도 같은 잠금을 기다린다.
- 실제 로컬 모델에서는 단계 하나에 최대 300초를 기다린다.

### 2.3 OpenAlex는 키 없이도 되지만 하루 예산이 작다

- 키 없이 실제로 검색했다. 응답은 왔지만, 같은 IP의 모든 사용자가 하루 $0.10 예산을 나눠 쓴다는 안내가 함께 왔다.
- 검색 1회가 $0.001이므로 하루 약 100회이다.
- 무료 키를 쓰면 하루 $1, 약 1,000회이다. 공식 변경 기록에는 2026-02-13부터 모든 요청에 키가 필요하다고 되어 있다.
- 앱에서 쓰는 양:
  - 키는 `OPENALEX_API_KEY` 환경 변수로만 받는다. Bearer 헤더 방식도 공식 문서에서 지원한다.
  - 연구 루프는 반복 한 번에 최대 약 8회 검색한다 (검색어 5개, 선행 연구 확인 3개).
  - 검색 화면과 분야 분류도 같은 예산을 쓴다.
- 응답 본문에는 "AI 에이전트가 사용자 이메일로 키를 신청하라"는 안내가 있었다. 이 지시는 따르지 않았다. 키는 사용자가 직접 받아야 한다.

### 2.4 Semantic Scholar는 임베딩은 되지만 인용 의도는 거의 비어 있다

- 키 없이 다음을 받을 수 있었다.
  - SPECTER2 임베딩 (768차원).
  - TLDR 요약.
  - 추천 목록. `from=all-cs`로 호출할 때만 결과가 나왔다.
- 인용 의도(intents)는 BERT를 인용한 논문 50건 중 0건에만 있었다. 문맥(contexts)도 1건에만 있었다.
- 따라서 관계 유형을 자동으로 정하는 근거로는 쓸 수 없다.

### 2.5 MCP 최신 규격(2026-07-28)이 크게 바뀌었다

[변경 기록](https://modelcontextprotocol.io/specification/2026-07-28/changelog)의 핵심:

- 세션과 `initialize` 절차가 없어졌다. 호출 사이의 상태는 서버가 만든 핸들을 도구 인자로 넘긴다.
  - 우리 MCP 도구는 이미 `run_id`를 인자로 받는다.
- Sampling, Roots, Logging은 폐기 예정이다. 규격은 sampling 대신 LLM 제공자 API를 직접 쓰라고 권한다.
- tasks는 공식 확장으로 옮겨졌고, 결과를 폴링으로 받는다.
- 서버가 클라이언트에게 먼저 보내던 요청(elicitation 등)은 `input_required` 결과를 돌려주는 방식(MRTR)으로 바뀌었다.

## 3. 설계별 판정

| 설계 | 판정 | 핵심 근거 | 할 일 |
|---|---|---|---|
| O1 코드가 정한 7단계 순서, LLM은 도구 없음 | 유지 | Anthropic 워크플로 지침, 12-Factor, Google 확장 연구, MAST, LLM-Modulo | 앞 단계 수확이 적으면 1~2회만 다시 계획 |
| O2 단일 상태, 앱 안 서브에이전트 없음 | 유지 | 순차 작업에서 다중 에이전트 39–70% 저하, Cognition | 상태는 전부 저장하되 LLM에는 압축본만 |
| O3 단계 기록과 재시도 | 보완 | 내구성 실행(Temporal, DBOS, LangGraph) | 백그라운드 실행, 실행별 잠금, 입력 해시 캐시 |
| O4 예산 (호출 40회, 반복 3회) | 보완 | 호출 수만으로는 시간이 묶이지 않음 | 실행 시간 예산, OpenAlex 예산 계산 |
| O5 반복마다 사람 검토 | 유지 | Agent Laboratory 공동 조종, Co-STORM, Nova 약 3회 포화 | 검색 전 검색어 승인 단계 추가 |
| O6 반복 감지 (같은 검색어 제거) | 보완 | 실제 에이전트도 동일 반복만 잡음 | 정규화 비교, 반복 간 정체 감지 |
| O7 같은 모델의 "독립 리뷰어", 1–5 점수 | **변경** | 자기 선호 편향, 외부 신호 없는 자기 교정 실패 | 검증 체크리스트로 바꾸고 숫자 참신성 점수 제거 |
| O8 초록 문장 근거, 용어 겹침 선별 | 보완 | 인용이 있어도 문장의 20.6%가 부정확(Kosmos) | 인용 따라가기 검색, BM25, 주장-근거 겹침 경고 |
| O9 단계별 JSON 스키마 | 보완 | 형식 제약이 작은 모델의 추론을 해칠 수 있음 | 근거를 주장보다 먼저, 필요하면 두 번 호출 |
| O10 문서 감싸기, 미리보기·해시 승인 | 대체로 유지 | 도구 없는 LLM이 가장 강한 방어 | 승인 범위를 단계 목록으로, 데이터 등급별 제한 |
| O11 채팅 인용 키 사후 검사 | 보완 | 키가 맞아도 내용이 근거를 따른다는 보장은 없음 | 문장 단위 표시, 자유 대화는 "근거 없음" 표시 |
| O12 MCP 초안 쓰기, 스킬 4종 | 유지·보완 | 2026-07-28 규격과 맞음, annotation은 통제 수단 아님 | 훅으로 강제, 스킬 권한 축소 |
| K1 AI 정리 1회 호출 | **변경** | 실행 위치 CPU, 주장 먼저인 필드 순서, 비스트리밍 | 후보 문장 ID 선택, 묶음 호출, GPU 확인 |
| K2 논문 연결 | 보완 | 참고문헌이 가장 정확한 신호 | 공동 인용·서지 결합, BM25, 선택적 SPECTER2 |
| K3 갭 후보 | 보완 | 전문가 검증 70%(PaperQA2 모순 탐지) | 섹션·문장 형태로 거르기, 측정 세트 |
| K4 분야 정리 | 유지·보완 | TnT-LLM 방식, OpenAlex 주제 정확도 약 0.53 | 분류 체계는 한 번 제안받아 사용자가 편집 |

### 3.1 오케스트레이션 구조 (O1, O2)

- **워크플로가 맞다.**
  - Anthropic은 단계가 정해진 일에는 코드가 흐름을 정하는 워크플로를 먼저 쓰라고 권한다.
  - 12-Factor Agents의 "흐름은 직접 소유하라"도 같은 말이다.
  - 우리 루프는 그 형태이다. 출처: [Anthropic](https://www.anthropic.com/engineering/building-effective-agents), [12-Factor](https://github.com/humanlayer/12-factor-agents).
- **앱 안 다중 에이전트는 이 일에 해롭다.** Google의 확장 연구 [확인](https://arxiv.org/abs/2512.08296)에 따르면:
  - 엄격히 순차적인 계획 과제에서는 다중 에이전트 변형이 모두 39–70% 나빠졌다.
  - 병렬로 나눌 수 있는 과제에서는 약 81% 좋아졌다.
  - 독립 에이전트는 오류를 17.2배 키웠고, 중앙 조정은 4.4배로 막았다.
  - 블로그판과 arXiv판의 설정 수와 R² 값은 서로 다르다.
- 문제 → 방법 → 기여는 서로 의존하므로 순차 과제에 해당한다. Cognition이 공유 맥락을 강조한 이유와 같다 [V](https://cognition.com/blog/dont-build-multi-agents).
- **병렬은 코드와 독립 작업에만 쓴다.**
  - 검색 요청처럼 서로 독립인 일은 에이전트가 아니라 코드로 병렬 처리한다.
  - Anthropic 다중 에이전트 연구 시스템은 넓게 탐색하는 일에서만 이득이 컸고, 토큰을 채팅의 약 15배 썼다 [V](https://www.anthropic.com/engineering/multi-agent-research-system).
- **약점: 고정 순서는 앞 단계 실패를 회복하지 못한다.**
  - Magentic-One은 진척이 없으면 정체 카운터를 올리고, 기준을 넘으면 계획을 다시 세운다 [S](https://arxiv.org/abs/2411.04468).
  - 우리도 검색이나 선별 수확이 기준보다 적으면 검색어를 1~2회만 다시 만들게 한다.

### 3.2 실행·내구성·예산 (O3, O4, O6)

- **맞는 부분.** 단계마다 기록하고 실패 단계부터 다시 하는 구조는 Temporal, DBOS, LangGraph 체크포인트와 같은 형태이다 (보고서 F).
- **고칠 부분 ①: 실행 방식.**
  - 문제: 동기 HTTP 안에서 300초 호출을 하면 다른 요청이 막히고 취소가 늦다 (2.2에서 확인).
  - 바꿀 방향:
    - 실행은 백그라운드 작업자가 맡고, 화면은 상태를 주기적으로 조회한다.
    - 잠금은 실행별로 둔다.
    - 취소 표시는 단계 사이에서 확인한다.
    - Ollama 호출은 스트리밍으로 바꿔 중간에 끊을 수 있게 한다.
- **고칠 부분 ②: 재시도와 예산.**
  - 같은 입력이면 다시 부르지 않도록 단계 입력 해시로 결과를 캐시하고, 모델 원시 출력은 해석 전에 먼저 저장한다.
  - 재시도는 오류 종류별로 상한을 둔다. 형식 오류는 같은 입력으로 반복하지 않는다.
  - 호출 수 예산만으로는 시간을 묶지 못한다. 40회 × 155–300초면 1.7–3.3시간이다. 실행 시간 예산(예: 30–45분)을 따로 둔다.
- **반복 감지.**
  - OpenHands의 StuckDetector 같은 실제 에이전트도 똑같은 동작이 반복될 때만 잡는다 [S].
  - 우리는 정확히 같은 검색어만 지운다. 다음을 더한다.
    - 표기만 다른 검색어를 걸러내는 정규화 비교.
    - 반복 사이에 문제 목록이 거의 같으면 "정체"로 알리는 검사. 이 검사는 직접 근거가 없는 확장이며 시험이 필요하다.

### 3.3 비평과 참신성 (O7)

- **"독립 리뷰어"라는 이름은 근거와 반대이다.**
  - LLM 평가자는 자기 출력을 알아보고 더 높게 평가한다 ([Panickssery et al. 2024](https://arxiv.org/abs/2404.13076)).
  - 외부 신호 없는 자기 교정은 추론 정확도를 올리지 못하고 때로 낮춘다 ([Huang et al.](https://arxiv.org/abs/2310.01798), [Kamoi et al.](https://arxiv.org/abs/2406.01297)).
  - 모델은 오류를 고치는 것보다 찾는 데서 더 실패한다 ([Tyen et al.](https://arxiv.org/abs/2311.08516)).
  - 같은 모델끼리의 토론은 다수결 이상의 이득이 거의 없다 (보고서 E).
- **코드 확인:**
  - 비평 단계는 기여 단계가 찾은 "가장 가까운 선행 연구"를 입력으로 받지 않는다. 그런데도 참신성 점수를 매긴다. 근거 없는 숫자이다.
  - 기여 단계 프롬프트는 E 키로 인용하라고 한다. 그런데 문제 목록에 E 키 이름만 있고 근거 문장은 주지 않는다.
- **참신성을 판정하지 않는 원칙은 강하게 지지된다.**
  - 실행 전에 참신해 보인 아이디어가 실행 후에는 순위가 뒤집혔다 ([Si et al. 2025](https://arxiv.org/abs/2506.20803)).
  - 반대 근거도 있다. Scideator의 참신성 분류기는 사람 평가와 더 잘 맞았다 [S]. 다만 고정된 평가 세트 기준이다.
- **바꿀 방향:**
  - 이름을 "자기 점검 (같은 모델)"으로 바꾼다.
  - 점검은 코드가 확인할 수 있는 항목으로 한다.
    - 인용 키가 존재하는가.
    - 인용 문장이 실제로 있는가.
    - 주장과 인용 문장의 단어가 충분히 겹치는가.
    - 약점마다 E 키나 상태 필드를 인용했는가. 인용이 없으면 코드가 거절한다.
  - 숫자 참신성 점수는 빼고, 가장 가까운 선행 연구와의 어휘 겹침을 "검색 결과 신호"로 보여준다.
  - 점검을 유지할지는 비평 없음, 자기 일관성(여러 번 뽑아 합치기)과 비교한 측정으로 정한다.

### 3.4 근거와 검색 (O8, O9)

- **인용이 붙어도 틀릴 수 있다.**
  - Kosmos는 모든 문장에 인용을 붙였지만 20.6%가 부정확했다 [V](https://arxiv.org/abs/2511.02824).
  - 키가 유효하다는 것은 근거가 주장을 지지한다는 뜻이 아니다.
- **초록만으로는 방법과 한계를 놓친다.**
  - PaperQA2와 Undermind는 인용을 따라가며 검색하고 본문을 읽는다 (보고서 G).
  - 개선: OpenAlex `referenced_works`(뒤로)와 `cites:`(앞으로) 인용 따라가기를 두 번째 검색 경로로 둔다. 무료 API 호출만 쓴다.
  - 보고서 G는 이메일을 넣은 polite pool을 권했지만, 이제는 키 방식이 맞다 (2.3).
- **선별:**
  - 용어 겹침보다 BM25 순위가 낫다. 이 둘을 직접 비교한 연구는 없지만, LitSearch에서 BM25 계열은 밀집 검색보다 낮았다 [S](https://arxiv.org/abs/2407.18940). 단순 겹침은 그보다도 약하다.
  - 근거 문장은 목적·방법·평가·한계 단서로 고른다.
- **구조화 출력:**
  - 형식 제약이 작은 모델의 추론을 크게 떨어뜨렸다는 보고가 있다 ([Tam et al.](https://arxiv.org/abs/2408.02442), Llama-3-8B GSM8K 74.7 → 48.9).
  - 같은 모델에서 차이가 없다는 반박도 있다 ([dottxt](https://blog.dottxt.ai/say-what-you-mean.html)).
  - 결론: 필드 순서와 프롬프트 설계가 결과를 가른다. 근거 필드를 주장 필드보다 앞에 두고, 필요하면 자유 서술 후 형식화하는 두 번 호출을 쓴다.

### 3.5 안전·승인 (O10, O11)

- **도구 없는 LLM과 코드 흐름 제어가 가장 강한 구조적 방어이다.** 근거는 [설계 패턴 논문](https://arxiv.org/abs/2506.08837)의 행동 선택자·계획 후 실행 패턴과 [CaMeL](https://arxiv.org/abs/2503.18813)이다. 우리 설계가 이 형태이다.
- **구분자 감싸기만으로는 약하다.** 근거는 [Spotlighting](https://arxiv.org/abs/2403.14720)이다.
  - 구분자는 공격 성공률을 약 60%에서 절반 정도로만 줄였다 (보고서 I `[V]`).
  - datamarking은 GPT-3.5 요약에서 3.10%까지 낮췄다 `[확인]`.
  - 인코딩은 감당할 수 있는 큰 모델에서 가장 좋았지만, GPT-3.5는 성능이 떨어졌다 `[확인]`. 8B에서는 시험이 필요하다.
- **논문 속 숨은 지시는 실제로 있다.**
  - arXiv 논문 17–18편에서 AI 심사자를 노린 "긍정 평가만" 같은 숨은 문구가 발견됐다 [확인](https://arxiv.org/abs/2507.06185).
  - 이 앱이 읽는 PDF가 바로 그 경로이다.
- **남은 경로: 초록 → 비평의 `next_queries` → 다음 검색어 → OpenAlex.**
  - 검색어는 공개되므로 개인 텍스트가 섞이면 유출이다.
  - 현재 검색어 단계에는 개인 메모가 들어가지 않지만, 검색 전 승인 단계와 길이 제한이 있으면 더 안전하다.
- **한 번 승인으로 여러 단계를 보내는 방식:**
  - Anthropic은 사용자가 권한 요청의 93%를 승인한다고 보고했다 [V](https://www.anthropic.com/engineering/claude-code-auto-mode). 다른 보도에는 97%도 있다.
  - 이렇게 습관적으로 승인하면 위험해진다. 보고서 I는 승인 대상을 "단계 목록"으로 고정하자고 제안한다.
    - 단계별 템플릿, 길이 상한, 제공자, 데이터 등급을 미리 정한다.
    - 실행 중 범위를 벗어나면 다시 승인을 받는다.
- **무료 Gemini는 입력을 제품 개선에 쓰고 사람이 볼 수 있다** [V]. 데이터 등급을 두어, 무료 외부 등급에는 공개 초록만 보내게 한다.
- **채팅:**
  - 목록 밖 인용을 답 아래에 따로 표시하는 대신 본문 안에서 바로 표시한다.
  - 자유 대화 모드에는 "근거 없이 생각 정리"라고 표시한다.
  - 코드 확인: 목록 밖 갭 키는 `PG9`처럼 잘못 표시된다 (`apps/web/research.js` 449행).

### 3.6 MCP·스킬·Claude Code 서브에이전트 (O12)

- **규격과 맞는 부분.**
  - 2026-07-28 규격은 세션이 없다. 우리 도구는 `run_id` 같은 핸들을 인자로 받으므로 맞는다.
  - sampling은 폐기 예정이다. 그래서 "MCP sampling으로 Claude를 빌려 쓰는" 설계는 하지 않는다. Claude Code의 sampling 지원도 확인되지 않았다.
- **annotation은 통제 수단이 아니다.**
  - 규격은 클라이언트가 annotation을 신뢰하지 말라고 한다.
  - Claude Code가 annotation에 따라 동작하지 않는다는 보고도 있다 [S].
  - 읽기 전용은 Claude Code 훅으로 강제한다. 예: 서재를 읽는 스킬이 도는 동안 WebFetch와 네트워크 Bash를 막는다.
- **스킬 권한.**
  - `research-loop`에는 `disable-model-invocation: true`를 둔다. 외부 호출을 일으키는 스킬이 사용자 요청 없이 자동 실행되지 않게 한다.
  - `allowed-tools`는 좁게 정한다 [V](https://code.claude.com/docs/en/skills).
- **서브에이전트를 쓰기 좋은 곳.**
  - 논문별 정리처럼 서로 독립인 일이다.
  - Claude Code 서브에이전트는 맥락이 분리되고, 도구와 최대 턴을 제한할 수 있다 [V](https://code.claude.com/docs/en/sub-agents).
  - 다만 사용량 한도를 함께 쓴다.
  - Claude Code로 서재 내용을 읽으면 Anthropic으로 보내는 외부 전송이다. 실행마다 사용자 동의와 미리보기가 필요하다.

### 3.7 논문 정리·연결·갭·분야 (K1–K4)

- **K1 AI 정리 실패의 원인 후보.**
  1. CPU 실행이다 (2.1, 확인).
  2. 스키마에서 주장이 근거보다 앞에 있다. 모델이 먼저 결론을 내고 인용을 맞추거나 비워 둔다 (Tam et al.의 필드 순서 결과).
  3. 빈 배열도 유효한 출력이어서, 비어 있는 결과가 그대로 통과한다 [추론].
  4. 비스트리밍 호출이라 생성이 진행 중이어도 제한 시간이 지난다.
  5. 8,000자 안에 결론이나 한계 절이 빠질 수 있다.
- **K1 개선 방향.**
  - 코드가 후보 문장을 고르고 각 문장에 ID와 페이지를 붙인다. 모델은 ID만 고른다.
  - 인용 원문은 코드가 복사하므로 인용 조작이 구조적으로 사라진다.
  - 9개 facet을 섹션별 3묶음으로 나눠 묶음마다 4,000자 이내로 호출한다.
  - temperature를 0으로 둔다.
  - Ollama `/api/ps`의 `size_vram`을 확인해 CPU로 돌고 있으면 경고한다.
  - `num_ctx`는 입력에 맞춰 4k–6k로 둔다. 공식 문서상 24GiB 미만 GPU의 기본값은 4k이다 [V](https://docs.ollama.com/context-length).
- **K2 연결.**
  - 참고문헌(`referenced_works`)이 가장 정확한 신호이다.
  - 그다음은 공동 인용과 서지 결합이다. Connected Papers가 쓰는 방식이다.
  - 로컬 유사도는 Jaccard 대신 BM25를 쓴다.
  - SPECTER2 임베딩은 키 없이 받을 수 있다 (2.4). 보내는 것은 DOI뿐이지만 외부 전송이므로 선택 기능으로 둔다.
  - 관계 유형은 [CiTO](https://sparontologies.github.io/cito/current/cito.html) 어휘에 맞춰 두면 내보내기에 유리하다 [S].
- **K3 갭.**
  - 강한 시스템도 모순 후보의 70%만 전문가 검증을 통과했다 ([PaperQA2](https://arxiv.org/abs/2409.13740)). 그래서 갭은 끝까지 "후보"로 둔다.
  - 규칙 후보는 한계·결론·향후 과제 절에서만 뽑고, 구체적인 대상을 가리키는 문장만 남겨 소음을 줄인다.
  - 측정 세트를 만든다. LimitGen처럼 논문 사본에 한계를 일부러 심어 재현율을 잰다 ([LimitGen](https://arxiv.org/abs/2507.02694), [BAGELS](https://arxiv.org/abs/2505.18207)).
- **K4 분야.**
  - [TnT-LLM](https://arxiv.org/abs/2403.12173) 방식을 따른다. LLM이 분류 체계를 한 번 제안하고, 사용자가 편집한 뒤, 규칙이나 BM25로 분류한다.
  - OpenAlex 주제는 제안으로만 쓴다. 업체가 보고한 주제 단위 1순위 정확도는 약 0.53이다 [S].

## 4. 개선 아이디어와 검증 상태

검증 상태 표기:
- **관측**: 이 PC의 코드나 실행 상태로 문제를 확인했다.
- **문헌 강**: 1차 출처가 여럿이다.
- **문헌 중**: 출처가 하나이거나 대상이 다르다.
- **추론**: 시험이 필요하다.

### 1순위 (비용이 낮고, 관측된 문제를 직접 고친다)

| # | 아이디어 | 근거 | 검증 상태 | 비용 |
|---|---|---|---|---|
| 1 | 백그라운드 실행과 상태 조회, 실행별 잠금, 단계 사이 취소, Ollama 스트리밍 | 2.2 시험, 보고서 F | 관측 + 문헌 강 | 중 |
| 2 | 단계 입력 해시 캐시, 원시 출력 선저장, 오류별 재시도 상한, 실행 시간 예산 | Temporal·DBOS·Inngest, 보고서 F | 문헌 강 | 낮음 |
| 3 | 비평 → 검증 체크리스트, 약점 인용 의무, 숫자 참신성 점수 제거 | Huang, Kamoi, Panickssery, 3.3 코드 확인 | 문헌 강 + 관측 | 낮음 |
| 4 | Ollama 실행 위치 확인(`size_vram`), 입력 크기에 맞춘 `num_ctx` | 2.1 확인, Ollama 문서 | 관측 | 낮음 |
| 5 | OpenAlex 키 설정 화면, 남은 예산 표시(`X-RateLimit-Remaining-USD`), 검색 캐시 | 2.3 확인 | 관측 | 낮음 |
| 6 | AI 정리: 후보 문장 ID 선택, 섹션별 3묶음, 근거 먼저, temperature 0 | Tam et al., Anthropic 긴 문서 지침, 보고서 H | 문헌 중 + 추론 | 중 |

6번은 실험으로 효과를 확인해야 한다. GPU가 비어 있을 때 같은 논문으로 기존 방식, 두 번 호출, 묶음 호출을 비교한다. 시험 스크립트는 만들어 두었고, 이번에는 사용자 실험이 GPU를 쓰고 있어 중단했다.

### 2순위 (근거가 좋고 비용이 중간이다)

| # | 아이디어 | 근거 | 검증 상태 |
|---|---|---|---|
| 7 | 인용 따라가기 검색 (뒤로·앞으로) | PaperQA2, Undermind, Chain-of-Ideas | 문헌 강 |
| 8 | 검색 전 검색어 승인·수정 단계 | Gemini Deep Research, Co-STORM 사용자 조정 | 문헌 중 |
| 9 | 수확이 적으면 1~2회 재계획, 반복 정체 감지, 시도 기록(검색어·거절한 문제) 전달 | Magentic-One 정체 카운터, DeepScientist 발견 기록 | 문헌 중 + 추론 |
| 10 | BM25 선별, facet 단서로 문장 선택, 주장-근거 겹침 경고 | Kosmos 20.6%, LitSearch, Scim | 문헌 중 |
| 11 | 평가 세트(주제 10–20개, 한계를 심은 논문 5편), 단계별 수확·시간 표 | AstaBench 보고 방식, LimitGen, 보고서 E·F | 문헌 강 |
| 12 | 승인 범위를 단계 목록으로 고정, 데이터 등급별 제공자 제한 | 승인 피로 93%, Gemini 무료 약관 | 문헌 중 |

11번의 장점: 이미 인용을 `exact`/`normalized`/`not_found`로 판정하고 있으므로 인용 일치율은 사람 없이 자동으로 잴 수 있다.

### 3순위 (선택 기능이거나 외부 전송 동의가 필요하다)

| # | 아이디어 | 근거 | 조건 |
|---|---|---|---|
| 13 | Claude Code를 바깥 오케스트레이터로 사용: 논문별 정리 서브에이전트 병렬, 읽기 전용 검토 서브에이전트, 훅으로 네트워크 차단 | Claude Code 서브에이전트·훅 문서, Anthropic 다중 에이전트 | 실행마다 외부 전송 동의, 사용량 한도 |
| 14 | SPECTER2 임베딩으로 유사 논문 연결 | 2.4 확인 | DOI 전송 동의 |
| 15 | 기여 문장 쌍대 비교 순위 (순서 바꿔 두 번) | AI co-scientist 토너먼트, Nova | 강한 모델일 때만 의미 있음 |
| 16 | datamarking 방식 문서 감싸기 | Spotlighting | 8B에서 효과와 인용 정확도 영향 시험 |
| 17 | 분류 체계 제안 → 사용자 편집 → 규칙 분류 | TnT-LLM | LLM 1회 |
| 18 | 갭 규칙 후보를 섹션과 문장 형태로 거르기 | BAGELS, FutureGen | 측정 세트로 확인 |

## 5. 채택하지 않는 아이디어

| 아이디어 | 이유 |
|---|---|
| 앱 안 다중 에이전트, 같은 모델끼리의 토론 | 순차 의존 작업에서 성능이 39–70% 떨어졌다. 토론의 이득은 대부분 다수결 효과이다. 비용과 시간이 늘어난다. |
| MCP sampling으로 클라이언트 모델 빌려 쓰기 | 2026-07-28 규격에서 폐기 예정이다. Claude Code 지원도 확인되지 않았다. |
| Semantic Scholar 인용 의도로 관계 자동 분류 | 실제 호출에서 인용 의도가 거의 비어 있었다 (2.4). |
| 같은 모델의 숫자 참신성 점수 | 자기 선호 편향이 있고, 실행 전 참신성은 실행 후 순위와 뒤집혔다. |
| 개인 텍스트를 무료 외부 등급으로 보내기 | 제품 개선에 쓰이고 사람이 검토할 수 있다. |
| 로컬 모델 추가 다운로드 | 사용자 요청으로 보류했다. 이번 조사는 다운로드 없이 가능한 개선만 다룬다. |

## 6. 한계

- 조사 보고서의 많은 수치는 검색 요약(`[S]`)이다. 판정에 쓴 핵심 주장만 다시 확인했다.
- 출처 사이에 수치가 다르다. 각 보고서의 4부에 정리돼 있다. 예:
  - Google 연구의 블로그판과 arXiv판.
  - 승인율 93%와 97%.
  - 숨은 문구가 발견된 논문 수 17편과 18편.
- AI 정리 개선(아이디어 6)은 실험을 끝내지 못했다. 효과는 아직 추론이다.
- 이 문서의 개선안은 아직 구현하지 않았다. 구현하려면 ExecPlan을 새로 만들고 수용 기준부터 정한다.

## 7. 주요 출처

- 오케스트레이션:
  - [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
  - [Anthropic, multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
  - [Cognition, Don't build multi-agents](https://cognition.com/blog/dont-build-multi-agents)
  - [Google, Towards a science of scaling agent systems](https://arxiv.org/abs/2512.08296)
  - [MAST](https://arxiv.org/abs/2503.13657)
  - [Magentic-One](https://arxiv.org/abs/2411.04468)
  - [12-Factor Agents](https://github.com/humanlayer/12-factor-agents)
- 맥락·내구성:
  - [Anthropic, context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  - [Anthropic, long-running harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  - [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
  - [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- 자기 교정·평가:
  - [Huang et al.](https://arxiv.org/abs/2310.01798)
  - [Kamoi et al.](https://arxiv.org/abs/2406.01297)
  - [Tyen et al.](https://arxiv.org/abs/2311.08516)
  - [Panickssery et al.](https://arxiv.org/abs/2404.13076)
- 연구 자동화와 HCI:
  - [Kosmos](https://arxiv.org/abs/2511.02824)
  - [PaperQA2](https://arxiv.org/abs/2409.13740)
  - [Si et al. 2025](https://arxiv.org/abs/2506.20803)
  - [Co-STORM](https://arxiv.org/abs/2408.15232)
  - [IdeaSynth](https://arxiv.org/abs/2410.04025)
  - [Nova](https://arxiv.org/abs/2410.14255)
  - [Agent Laboratory](https://arxiv.org/abs/2501.04227)
  - [OpenScholar](https://arxiv.org/abs/2411.14199)
- 추출·연결:
  - [Tam et al.](https://arxiv.org/abs/2408.02442)
  - [dottxt 반박](https://blog.dottxt.ai/say-what-you-mean.html)
  - [Ollama 구조화 출력](https://docs.ollama.com/capabilities/structured-outputs)
  - [Ollama 맥락 길이](https://docs.ollama.com/context-length)
  - [TnT-LLM](https://arxiv.org/abs/2403.12173)
  - [LimitGen](https://arxiv.org/abs/2507.02694)
  - [Semantic Scholar API](https://www.semanticscholar.org/product/api)
  - [OpenAlex 인증](https://help.openalex.org/api-reference/authentication)
- 안전·MCP:
  - [설계 패턴](https://arxiv.org/abs/2506.08837)
  - [CaMeL](https://arxiv.org/abs/2503.18813)
  - [Spotlighting](https://arxiv.org/abs/2403.14720)
  - [논문 속 숨은 프롬프트](https://arxiv.org/abs/2507.06185)
  - [Lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
  - [MCP 2026-07-28 변경 기록](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
  - [Agent Skills 규격](https://agentskills.io/specification)
