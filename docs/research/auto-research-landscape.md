# 연구 자동화·에이전트 조사 요약과 EasyResearch 적용

- 조사일: 2026-11-10
- 방법: Haiku 조사 에이전트 4개가 웹을 검색하고 원문 페이지를 확인했다. 원본 보고서는 [raw/](raw/)에 있으며 주장마다 출처 URL이 붙어 있다.
- 출처 상태 표기:
  - `UNVERIFIED`: 원문으로 확인하지 못했다.
  - `SEARCH-ONLY`: 검색 결과 요약으로만 확인했다.
- 별 수와 수치는 조사 시점 기준이다.

| 보고서 | 범위 |
|---|---|
| [A](raw/A-autonomous-research-systems.md) | 자율 연구 시스템 약 27종, 벤치마크, 실패 사례 |
| [B](raw/B-literature-gaps-ideas.md) | 논문 구조화 요약, 문헌 그래프, 갭 찾기, 아이디어 생성 도구·논문 |
| [C](raw/C-agent-engineering.md) | 에이전트 공학: 워크플로 패턴, 서브에이전트, 스킬 규격, MCP, 루프·예산·검증, 프롬프트 주입 |
| [D](raw/D-free-providers-graph.md) | 무료 LLM 제공자, OpenAlex·Semantic Scholar 그래프, Obsidian 그래프, JS force layout |

## 1. 자율 연구 시스템에서 배운 것 (A)

- **대표 설계**
  - Sakana AI Scientist v1·v2: 템플릿 기반 → BFTS 트리 탐색.
  - Agent Laboratory: 단계별 체크포인트와 Co-Pilot 모드.
  - Google AI co-scientist: Elo 토너먼트와 진화.
  - Kosmos: 문장마다 인용을 붙이며, 79.4%가 정확하다고 판정됐다.
  - data-to-paper: 모든 숫자를 코드까지 추적한다.
  - OpenEvolve·ShinkaEvolve: MAP-Elites 섬 모델.
  - AIDE: 해법 트리.
- **반복 공학**: 트리 탐색, 토너먼트, 진화, 리뷰어 보상 RL, 실패 기억을 이용한 탐색 등이 있다. 모두 예산(단계·초안·비용·시간)과 체크포인트·재개를 둔다.
- **실패 근거** (Beel et al., arXiv 2502.14297)
  - AI Scientist v1 실험의 42%가 코드 오류로 실패했다.
  - 실험 결과와 다른 숫자가 나왔다.
  - 잘 알려진 아이디어를 "새롭다"고 판정했다.
  - 인용은 중앙값 5개였다.
  - Agents4Science 2025에서는 314편 중 48편이 채택됐고, "기술적으로 맞지만 중요하지 않다"는 평가를 받았다.
- **결론: 무엇을 자동화하고 무엇을 사람이 정하는가**
  - 자동화: 검색, 중복 제거, 아이디어 후보 생성과 정렬.
  - 사람이 결정: 주제와 범위, 방향 선택, **기여(contribution) 문장과 참신성 주장**.
- **참신성 판정 원칙**
  - 모델의 판단이 아니라 기록된 검색으로 정한다. 가장 가까운 선행 연구를 링크와 함께 반드시 제시한다.
  - 반례 검색을 한다.
  - LLM 리뷰어를 유일한 관문으로 두지 않는다.

## 2. 문헌 도구와 갭 찾기 (B)

- **구조화 요약**
  - PaperQA2: 청크 요약과 페이지 인용을 쓰며 LitQA2 정확도는 66%이다.
  - Elicit: 열(column) 추출에 근거 구절을 붙인다.
  - Scideator: 목적·메커니즘·평가 facet을 쓴다.
  - 한계(limitation)는 별도 칸이 필요하다 (BAGELS, FutureGen).
- **연결**
  - 인용 의도(Semantic Scholar intents, scite의 supporting/contrasting)를 쓴다.
  - 공동 인용과 서지 결합을 쓴다 (Connected Papers).
  - 공유 문제나 방법은 인용과 다른 관계 유형으로 다룬다.
- **갭**
  - 근거가 있는 방법은 한계와 향후 과제 추출, 그리고 모순 탐지이다 (PaperQA2 ContraCrow, 전문가 검증 70%).
  - "비교표의 빈칸"으로 갭을 찾는 방법은 출처가 없는 제안이다. 그래서 앱에서는 **후보**로만 표시한다.
- **아이디어**
  - Si et al.: LLM 아이디어가 더 참신하다고 평가됐지만 실현 가능성은 낮았고, LLM의 자기 평가는 신뢰하기 어렵다.
  - SciMON, ResearchAgent, Chain-of-Ideas, Nova, Scideator: 검색 후 참신성을 확인하는 단계를 둔다.

## 3. 에이전트 공학 (C)

- **Anthropic "Building effective agents"**: 단순한 워크플로를 우선한다 (체이닝, 라우팅, 병렬화, 오케스트레이터-작업자, 평가자-최적화자).
- **Anthropic 다중 에이전트 연구 시스템**: 병렬 작업자는 서로 독립된 검색과 읽기 단위에만 쓴다.
- **Cognition "Don't build multi-agents"**: 문제 → 방법 → 기여처럼 서로 의존하는 결정은 한 맥락(공유 상태)에 둔다.
- **Manus 맥락 공학**: 덧붙이기만 하는 기록, 실패를 맥락에 남기기, 캐시하기 쉬운 프롬프트.
- **스킬 규격** (agentskills.io)
  - `SKILL.md` frontmatter의 `name`은 소문자와 하이픈 64자 이내이며 디렉터리 이름과 같아야 한다.
  - `description`은 1024자 이내이다.
  - 본문은 500줄 미만이며 점진적으로 공개한다.
  - 참고 사례: anthropics/skills, K-Dense claude-scientific-skills, obra/superpowers.
- **MCP 2026-07-28 개정**
  - 세션과 initialize 절차가 사라졌다. 그래서 run_id와 cursor는 도구 인자로 넘긴다.
  - 최종본인지는 출처마다 달라 `UNVERIFIED`이다.
- **루프 설계**
  - 결정적 상태 기계.
  - 단계마다 체크포인트.
  - 호출·반복 예산과 반복 감지.
  - 비평은 근거 인용을 요구하고 수정은 2~3회까지만 한다.
  - LLM 판정의 편향(길이, 순서, 자기 선호)에 주의한다.
- **문서 텍스트는 데이터이다.**
  - 구분자로 감싼다.
  - 읽기 단계는 도구 없이 격리한다 (CaMeL).
  - 인자는 허용 목록으로 검사한다.
  - 외부 전송은 미리보기를 거친다.

## 4. 무료 제공자와 그래프 (D)

- **로컬**
  - Ollama(`/api/chat`, `format` JSON)와 LM Studio(`/v1`).
  - 무료이며 비공개이다. 이 PC는 RTX 4060 8GB에 Ollama가 설치되어 있다.
- **외부 무료 등급**
  - Gemini: OpenAI 호환 주소가 확인됐다. **무료 등급 입력은 Google 제품 개선에 쓰인다.**
  - Groq.
  - OpenRouter `:free`: 하루 50회, 크레딧이 10 이상이면 하루 1000회, 분당 20회.
  - Cloudflare Workers AI: 하루 10,000 neurons.
- **기본값에서 뺀 것**
  - GitHub Models: 2026-07-30에 종료됐다.
  - Cerebras: 30일 체험만 있다.
  - Mistral 무료: 학습에 사용될 수 있다.
- **구독형 Claude·ChatGPT**
  - 무인 백엔드로 쓰는 것은 약관과 2026년 정책상 맞지 않는다.
  - 사람이 Claude Code나 Codex에서 MCP와 스킬로 직접 구동하는 방식으로만 쓴다.
- **그래프**
  - OpenAlex `referenced_works`, `related_works`, `cites:` 필터: 원문 페이지 확인 실패로 SEARCH-ONLY이다. 실제 호출로 다시 확인할 것.
  - Obsidian: 노트가 노드이고 `[[wikilink]]`가 간선이다.
  - 화면 그리기: 노드 500개까지는 단순 O(n²) force layout으로 충분하다.

## 5. EasyResearch 설계에 반영한 것

자세한 계약은 [ExecPlan 004](../exec-plans/active/004-research-assistant.md)에 있다.

| 조사 교훈 | 적용 |
|---|---|
| 기본은 로컬·무료·비공개 | 기본 제공자는 Ollama. 외부 무료 등급은 선택이며 미리보기·해시 승인을 거친다. Gemini 무료 등급의 데이터 사용 경고를 표시한다. |
| 모든 값에 근거 구절과 페이지 | 프로필 항목마다 구절과 1부터 세는 물리 페이지를 둔다. 저장된 페이지 텍스트로 `exact`/`normalized`/`not_found`를 검사한다. |
| 고정 facet과 별도 한계 칸 | 문제·방법·기여·장점·한계·데이터셋·지표·결과·향후 과제. 저자 서술과 추론을 구분한다. |
| 관계 유형이 있는 연결, 사용자 결정 분리 | relation 9종. origin에 따라 상태를 나눈다 (수동은 accepted, 규칙·AI·에이전트는 suggested). 사용자가 거절한 연결은 다시 만들지 않는다. |
| 갭은 출처를 인용한 가설 | 갭은 `candidate` 상태로 만든다. 근거(paper_id, facet, quote)가 필수이다. 규칙 갭과 AI 갭을 함께 둔다. |
| 아이디어 구체화 대화 | 모드별 채팅(Heilmeier 질문, 근거·반례 탐문). 인용 키를 검증한다. 대화 결과를 아이디어로 저장한다. |
| 결정적 상태 기계와 공유 상태 | 단계 순서는 `plan_queries → search → screen → problems → methods → contributions → critique`. 문제·방법·기여는 하나의 state를 공유한다. |
| 예산, 반복 감지, 체크포인트 | 반복 3회, LLM 호출 40회까지. 단계 기록과 실패 단계 재시도. 반복마다 `awaiting_review`에서 사람이 검토한다. |
| 참신성은 검색으로 | 기여 단계는 "가장 가까운 선행 연구"를 검색해 보여주기만 한다. 참신성은 판정하지 않는다. |
| 비평 관문 | 별도 리뷰어 지시로 점수·약점·다음 질의를 만든다. 최종 결정은 사람이 한다. |
| 문서는 신뢰하지 않는 데이터 | `<document>` 블록과 지시 무시 규칙. MCP 결과의 untrusted 래퍼. |
| 스킬과 MCP | 스킬 4종(정리, 갭, 아이디어 구체화, 연구 루프). MCP 쓰기 도구는 초안 기록만 만든다. |

## 6. 이번에 구현하지 않은 것 (후속 후보)

- 실험 단계: 샌드박스 코드 실행과 고정 평가자 (AIDE, AI Scientist v2 방식). 기존 Docker 실험 경로의 검증이 먼저 필요하다.
- 아이디어 토너먼트(Elo)와 다른 모델 계열을 판정자로 쓰는 방식.
- 아이디어 버전 관리.
- Semantic Scholar 인용 의도·영향 플래그, 공동 인용과 서지 결합 연결.
- 모순 탐지(ContraCrow 방식).
- 문장 역할 분류(argumentative zoning).
- 소규모 평가 세트(약 20개)로 프롬프트와 스킬 회귀 측정.
