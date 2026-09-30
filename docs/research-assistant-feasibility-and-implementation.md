# EasyResearch 기능 평가 및 구현 설계

작성일: 2026-10-01 (Asia/Seoul)  
목적: 개인용 연구 어시스턴트의 유사 서비스, 구현 가능성, 기술 구성과 개발 단계를 정리한다.

> 아래는 조사 기반 설계안이다. 코드 예시와 환경 설정은 실행 검증된 애플리케이션이 아니며, 초기 작업값은 실제 사용 후 조정한다. 기존 제품은 공식 페이지와 저장소에서 기능을 조사했고, 직접 가입해 성능을 비교하지 않았다.

## 1. 평가 요약

개인 프로젝트로 충분히 구현할 수 있다. 우선 가치가 큰 구성은 **논문 관리 + 근거가 연결된 분석 + 개인 메모·아이디어 + 논문 간 탐색**이다. 자동 연구는 이 지식 기반이 쌓인 뒤 단계적으로 추가한다.

현재 기능안에 대한 평가:

| 기능 | 가능성 | 가장 큰 난점 | 권장 접근 |
|---|---|---|---|
| 연구 프로젝트·문맥 관리 | 높음 | 오래된 요약의 오류, 프로젝트 간 문맥 혼합 | 사용자가 확정한 결정과 출처 ID를 저장하고 필요한 문맥만 전달 |
| 논문 검색·추천 | 높음 | 검색 누락, 분야·언어별 색인 차이 | 복수 데이터 소스, 검색식 기록, 직접 저장·제외 지원 |
| 상세 분석·개념 설명 | 높음, 품질은 조건부 | PDF의 표·수식·페이지 위치 추출 | 페이지 근거를 먼저 저장하고 설명과 저자 주장을 구분 |
| 논문 비교 | 높음 | 조건이 다른 수치를 직접 비교하는 오류 | 데이터·분할·지표·예산을 함께 구조화 |
| 연구 공백·참신함 탐색 | 후보 제시는 가능 | 문헌 검색만으로 ‘최초’를 증명 불가 | 검색 범위와 유사 논문을 밝힌 후보로 제시 |
| 아이디어 검토 | 높음, 품질은 조건부 | 새 아이디어가 실제로 새롭고 유효한지 판단 | 반례·검증 방법·실패 조건을 함께 관리 |
| 읽기 관리·지식 그래프 | 높음 | 자동 연결 오류, 그래프 과밀 | 관계의 근거·상태를 저장하고 현재 노드 주변만 표시 |
| Codex·Claude 실행 | 제한된 연구에서 가능 | 권한·재개·비용·실험 재현 관리 | 작은 작업 명세와 중앙 작업 관리자를 사용 |
| 서브에이전트 토큰 절약 | 보장 불가 | 추가 호출이 비용을 늘릴 수 있음 | 좁은 입력·캐시·호출 제한으로 실제 사용량 비교 |
| 내보내기·품질 관리 | 높음 | 데이터 이식성·근거 오류의 추적 | Markdown/BibTeX/JSON 내보내기, 버전·출처 보존 |

권장 초기 가정은 1인 사용, 한국어 질문과 영어 논문, 로컬 PC 운영이다. 자동 실험은 먼저 CPU로 검증 가능한 소규모 계산 연구를 목표로 한다. 실험실 장비·물리 실험 자동화는 별도 장비와 통합이 필요하다.

## 2. 기존 서비스 및 벤치마크

| 제품 | 확인한 주요 범위 | 참고할 점 |
|---|---|---|
| [Elicit](https://elicit.com/solutions/systematic-review) | 검색, 선별, 구조화 정보 추출, systematic review 지원 | 추출 기준을 표의 열로 다루고 원문 근거를 연결 |
| [SciSpace](https://scispace.com/) | 논문 검색, 문헌 검토, 초안·다이어그램 도구 | 하나의 연구 질문에서 다음 연구 작업으로 이동 |
| [ResearchRabbit](https://www.researchrabbit.ai/features) | 논문·저자 관계 탐색, 컬렉션, 추천, 시각화 | 컬렉션 중심 탐색과 읽을 논문 추천 |
| [Litmaps](https://www.litmaps.com/features) | 인용 연결, 지도, 새 논문 모니터링, Zotero 동기화 안내 | 인용 그래프와 주제 추적 |
| [Zotero](https://www.zotero.org/support/quick_start_guide) | 서지정보·PDF·메모·컬렉션·인용 관리 | 성숙한 자료 보관 기능을 가져오거나 연동 |
| [Obsidian Graph](https://obsidian.md/help/plugins/graph) | 노트 링크 기반 그래프와 현재 노트 주변 보기 | 개념과 개인 메모를 연결하는 UX |
| [PaperQA2](https://github.com/Future-House/paper-qa) | 과학 문서 RAG, 근거 인용, 검색·재정렬 | 논문 질의응답 파이프라인의 오픈소스 기준 |
| [Edison Scientific Kosmos](https://edisonscientific.com/news/announcing-kosmos) | 문헌 검토와 데이터 분석을 연결하는 자율 연구 시스템 | 장시간 연구 작업·중간 결과를 유지하는 방향 |
| [AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | 가설·실험·분석·논문 작성을 포함한 코드 공개 | 실험 관리와 탐색 구조 참고. 성공은 보장되지 않음 |
| [Rosalind Workbench](https://learn.chatgpt.com/blog/rosalind-workbench) | 생명과학 데이터·도구·근거를 연결하는 연구 작업 공간 | 전문 분야의 도구와 기록을 한 흐름에 배치 |

기능의 존재를 공개 페이지에서 확인한 것이며 제품별 품질 순위는 아니다. Connected Papers는 후보에 포함해 검토했으나 이번 조사에서는 공식 페이지 내용을 충분히 확인하지 못해 표에서 세부 기능 비교를 하지 않았다.

자신만의 벤치마크는 이미 아는 논문 10~20편과 낯선 주제 하나로 시작한다. 같은 질문과 같은 원문을 서비스마다 넣고 추천 상위 10편의 유용성, 알고 있는 핵심 논문 포함 여부, 주장 20개의 근거 정확성, 비교 조건 오류, 비용, 응답 시간을 기록한다. 이 작은 표본은 전체 문헌 검색의 재현율을 증명하지 않지만 실제 사용성 비교에는 도움이 된다.

## 3. 구현 불가·조건부 기능

| 기대 | 실제 한계 | 대안 |
|---|---|---|
| 모든 관련 논문 검색 | 색인과 메타데이터가 빠질 수 있음 | 복수 API, 인용 확장, 검색식·날짜 보존, 수동 추가 |
| 유료 논문 자동 원문 확보 | 구독·접근 권한 우회 불가 | 공개 원문만 자동 확보하고 사용자가 가진 PDF 지원 |
| 인용이 붙은 답변이면 사실 | 근거 구절과 주장의 의미가 맞지 않을 수 있음 | 인용 존재 검사와 의미 검토를 별도 표시 |
| 자동 생성 연구 공백이 참신함 증명 | ‘검색 결과가 없음’은 ‘세상에 연구가 없음’이 아님 | 확인한 검색 범위 안에서 후보로 표현 |
| 논문 수치로 항상 공정 비교 | 지표, 분할, 전처리, 연산량이 다를 수 있음 | 조건을 보존하고 비교 가능성 상태 표시 |
| 자동 실험이 논문 결과 재현 | 데이터·환경·가중치·하드웨어 차이가 남음 | 재현 가능성 사전 점검과 측정 로그 보존 |
| Claude와 Codex 무인 실행 | 별도 인증, 프로세스 격리, 비용 관리 필요 | 서버 측 SDK/API 키와 승인 단계 |
| 서브에이전트가 더 저렴함 | 여러 인스턴스의 합산 호출량이 늘 수 있음 | 단일 에이전트 기준선을 만들고 비용 비교 |
| 환각 0% | 현재 모델·파서로 보장 불가 | 원문 이동, 오류 수정, 처리 버전 추적 |

자동화의 첫 성공 기준은 독창성 판정이 아니라, 제한된 실험을 실행하고 같은 조건으로 다시 확인할 수 있는 기록을 만드는 것으로 둔다. Kosmos의 공개 글도 장시간 탐색이 가치가 낮은 상관관계로 흐를 수 있다고 밝힌다. [Kosmos](https://edisonscientific.com/news/announcing-kosmos) Sakana AI Scientist-v2 저장소는 서로 다른 탐색 방식의 성격과 한계도 설명한다. [AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)

## 4. 권장 기술 구성

이 표는 개인용 앱을 위한 설계 선택이다. 모두가 유일한 정답이거나 각 공식 문서가 추천한 전체 조합이라는 뜻은 아니다.

| 층 | 선택 | 용도 |
|---|---|---|
| 화면 | React + TypeScript + Vite | 프로젝트, 논문, 비교, 그래프, 실행 상태 |
| 화면 데이터 | TanStack Query | 검색·작업 상태와 서버 캐시 |
| API | Python 3.12 + FastAPI + Pydantic | 논문 API, 추출, 검증, 실행 관리 |
| 저장소 | PostgreSQL + pgvector + pg_trgm | 관계형 정보, 전문 검색, 의미 벡터 |
| 작업 큐 | Redis + RQ | PDF·분석·에이전트 실행을 HTTP와 분리 |
| 문서 파서 | Docling | 표·구조·OCR·페이지 출처 정보 |
| 브라우저 PDF | PDF.js | 원문을 열고 페이지 단위 근거로 이동 |
| 임베딩 | BAAI/bge-m3, dense 모드부터 | 한영 의미 검색 |
| 그래프 UI | Cytoscape.js | 논문·개념·아이디어 연결 보기 |
| AI 호출 | OpenAI·Anthropic 공식 SDK | 고정 작업, 구조화 응답, 비용 기록 |
| 연구 실행 | Codex SDK·Claude Agent SDK + Docker | 코드 작업·검토·자원 제한 실행 |
| 내보내기 | Markdown, BibTeX, JSON | 이동성·백업 |

참고: [Vite](https://vite.dev/guide/), [FastAPI 작업](https://fastapi.tiangolo.com/tutorial/background-tasks/), [RQ](https://python-rq.org/docs/), [pgvector](https://github.com/pgvector/pgvector), [Docling](https://docling-project.github.io/docling/), [PDF.js](https://mozilla.github.io/pdf.js/getting_started/), [BGE-M3](https://huggingface.co/BAAI/bge-m3), [Cytoscape.js](https://js.cytoscape.org/)

개인 앱에서 Neo4j, 전용 벡터 DB, Kubernetes는 초기에 필요하지 않다. PostgreSQL 노드·관계 테이블과 pgvector부터 사용한다. 별도 시스템은 부하·기능 요구가 실제로 생길 때 검토한다.

```mermaid
flowchart TD
  UI[React 화면] --> API[FastAPI]
  API --> DB[(PostgreSQL + pgvector)]
  API --> Q[Redis 작업 큐]
  Q --> PDF[문서 변환 작업자]
  Q --> LIT[논문 분석 작업자]
  Q --> ORCH[연구 작업 관리자]
  PDF --> DB
  LIT --> DB
  ORCH --> CODEX[Codex 어댑터]
  ORCH --> CLAUDE[Claude 어댑터]
  ORCH --> BOX[자원 제한 실험 컨테이너]
  CODEX --> ART[결과·파일·비용 기록]
  CLAUDE --> ART
  BOX --> ART
  ART --> DB
```

## 5. 외부 논문 소스

| 소스 | 용도 | 설정·한계 |
|---|---|---|
| OpenAlex | 폭넓은 논문·저자·주제·인용 정보 | API key 발급, 필요한 필드만 요청, 응답의 제한 정보 저장 |
| arXiv | CS/AI 프리프린트와 버전 정보 | Atom API 결과 파싱, arXiv 버전 ID 보존 |
| Crossref | DOI로 서지정보 확인 | REST API에 DOI 요청, 원본과 수정 이력 보존 |
| Semantic Scholar | 보조 추천·인용 자료 | 접근 키·한도 확인 후 선택적으로 추가 |
| Unpaywall | 공개 원문 위치 후보 | 현행 인증·조건 확인 후 추가, 원문 접근 보장은 없음 |
| Zotero | 사용자의 라이브러리 | 초기에는 BibTeX/CSL JSON 가져오기, 이후 Web API v3 |

OpenAlex의 현행 문서는 인증·한도와 사용량 확인 방법을 공개한다. [OpenAlex API](https://help.openalex.org/api/llm-quick-reference/) Crossref는 공개 REST API로 서지 메타데이터를 제공한다. [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) arXiv는 프로그램 접근용 Atom API를 문서화한다. [arXiv API](https://info.arxiv.org/help/api/user-manual.html) Zotero의 새 개발에는 Web API v3가 권장된다. [Zotero API](https://www.zotero.org/support/dev/web_api/v3/)

이번 조사에서 Semantic Scholar와 Unpaywall의 상세 API 본문은 충분히 확인하지 못했으므로 첫 구현의 필수 의존성으로 두지 않는다. [Semantic Scholar](https://api.semanticscholar.org/api-docs/), [Unpaywall](https://unpaywall.org/products/api)

각 논문에는 표준 ID(DOI, arXiv ID), 데이터 제공자 ID, 원 응답, 수집 날짜를 따로 둔다. API 장애가 있어도 이미 저장한 PDF·노트·그래프는 계속 사용할 수 있어야 한다.

## 6. 기능별 구현 설계

### 6.1 연구 프로젝트 공간

**구현 가능성: 높음 / 난이도: 중간.**

프로젝트에 질문, 목표, 포함·제외 범위, 현재 결정, 연결 논문, 미해결 질문을 저장한다. 논문 레코드와 프로젝트별 읽기 상태를 분리해 한 논문을 여러 프로젝트에서 재사용한다.

기본 테이블은 `projects`, `project_papers`, `decisions`, `research_questions`다. 결정에는 작성 시각과 근거 ID를 넣는다. 새 연구 작업을 만들 때 현재 질문, 최근 결정, 필요한 논문 근거만 골라 전달한다. 전체 대화를 매번 새 모델 호출에 붙이지 않는다.

완료 조건은 앱을 재시작해도 자료가 남고, 새 작업에 사용된 문맥과 근거를 확인할 수 있는 것이다.

### 6.2 논문 탐색·추천

**구현 가능성: 높음 / 난이도: 중간~높음.**

검색 흐름은 한국어 질문을 검색어·영어 동의어·제외어 후보로 확장하고, OpenAlex와 arXiv에서 메타데이터를 모은 뒤 DOI와 arXiv ID로 중복을 정리하는 방식이다. 저장 논문과 유사한 논문·인용 관계를 추천 신호로 활용한다.

초기 운영값은 검색 후보 100~200개, 화면 결과 20개, 이유 설명 10개로 둔다. 검색식, 날짜, 필터, 소스, 결과 ID를 기록한다. 추천에는 최신성·인용 수를 보조값으로 쓰고 오래된 기준 논문만 상위에 몰리지 않게 사용자가 직접 조정할 수 있도록 한다.

메타데이터만 확보한 경우 `abstract_only` 상태로 표시한다. DOI를 URL·공백에서 정규화하고, arXiv preprint와 정식 출판본은 관계를 연결하되 자동으로 같은 버전이라 가정하지 않는다. 새 논문 알림은 저장된 검색식을 재실행해 새 ID만 수집하는 방식으로 구현한다.

완료 조건은 검색 근거가 기록되고 같은 논문을 이중 등록하지 않는 것이다.

### 6.3 논문 상세 분석과 개념 설명

**구현 가능성: 조건부로 높음 / 난이도: 높음 / 핵심 품질 투자 지점.**

상세 화면은 배경 개념, 문제 설정, 방법의 입력·처리·출력, 핵심 기여, 실험 조건과 결과, 저자가 밝힌 한계, 별도 비판적 해석, 관련 논문으로 구성한다. 각 내용은 PDF 페이지나 실제 문구에 연결한다. 요약 한 문단으로만 처리하지 않고 개념→방법→실험 순으로 깊게 읽을 수 있게 한다.

처리 순서:

1. PDF 원본 SHA-256과 원문 버전을 저장한다.
2. Docling으로 구조와 페이지를 추출한다.
3. 섹션 기준으로 약 600~1,000토큰 조각을 만들고 페이지·표·그림 출처를 유지한다.
4. 조각을 색인하고 질문에 맞는 근거를 검색한다.
5. 주장과 인용 구절을 구조화한 뒤 인용이 원문에 있는지 검사한다.
6. 원문 근거를 사용해 한국어 설명을 만들고 출처 부족 필드는 미확정으로 둔다.
7. PDF.js에서 근거를 클릭하면 페이지로 이동한다. 좌표 신뢰도가 검증된 경우만 하이라이트한다.

주장 레코드에는 `paper_version_id`, `kind`, `text`, `chunk_id`, 실제 인용 구절, PDF 파일 페이지 인덱스, 인쇄된 페이지 라벨, 좌표 검증 상태를 둔다. 실제 PDF 페이지와 본문 인쇄 페이지를 구분한다.

장점·한계는 `author_claim`, `author_stated_limitation`, `evidence_based_observation`, `system_hypothesis`로 나눈다. 모델의 자신감 숫자를 사실 정확도 확률인 것처럼 사용자에게 보여주지 않는다. OCR 또는 표·수식 추출이 애매하면 원문 이미지 확인이 필요하다. [Docling](https://docling-project.github.io/docling/), [PDF.js](https://mozilla.github.io/pdf.js/getting_started/)

완료 조건은 모든 핵심 분석을 원문으로 되짚고, 초록만 처리한 논문과 전체 원문 분석을 구별하는 것이다.

### 6.4 논문 비교·연구 공백

**비교 구현: 높음 / 공백 자동 판정: 조건부 / 난이도: 높음.**

비교 레코드는 논문 버전, 태스크, 데이터셋 버전, 분할, 평가 프로토콜, 지표 정의와 단위, 모델 크기, 학습 데이터, 연산량, seed와 수치, 표·페이지 근거를 함께 저장한다. 같은 데이터셋 이름이라도 분할·전처리·학습 자료가 다르면 자동 순위를 표시하지 않는다.

비교 상태는 `comparable`, `partially_comparable`, `not_comparable`, `unknown`으로 구분한다. 논문 안에서 실제 평가한 baseline과 시스템이 추가로 추천하는 baseline을 구분한다. 우선 3~8편에서 8~15개 항목을 추출하고 추출물을 재사용한다.

공백 후보는 선택 논문들의 제한과 미검증 조건을 뽑고, 각 후보에 대해 별도 검색으로 유사·반대 연구를 확인한다. 검색어·일자·소스·유사 논문·확인되지 않은 범위를 저장한다. ‘이 선택한 문헌 범위에서는 근거를 찾지 못했다’고 쓰며 최초 연구로 단정하지 않는다.

### 6.5 아이디어 공간

**구현 가능성: 높음 / 평가 품질은 조건부 / 난이도: 중간.**

아이디어 카드는 질문, 제안, 근거, 비슷한 선행연구, 차이점, 반례, 데이터·비교군·지표, 최소 실험, 실패 판정 기준, 예상 자원, 채택·수정·보류 상태를 저장한다. 대화에서 아이디어를 추출할 때도 사용자가 수정·확정한다.

아이디어 생성과 비판적 검토는 별도 단계로 둔다. 첫 단계에서 근거를 찾고, 채택할 후보만 두 번째 단계에서 중복·측정 가능성·반례를 점검한다. 여러 모델의 동의는 과학적 검증으로 해석하지 않는다.

### 6.6 읽기 기록·지식 그래프

**구현 가능성: 높음 / 난이도: 중간~높음.**

읽기 상태(`to_read`, `reading`, `read`, `on_hold`), 중요도, 읽은 날, 개인 점수, 메모를 프로젝트별로 관리한다. 그래프 데이터는 PostgreSQL의 `entities`, `relations`, `relation_evidence`에 저장하고 Cytoscape.js로 보여준다.

노드 유형은 논문·개념·방법·데이터셋·질문·아이디어·실험이다. 관계 예시는 `cites`, `uses_method`, `evaluates_on`, `related_to`, `supports`, `contradicts`, `motivates`, `tested_by`다. 인용은 근거를 지지한다는 뜻이 아니므로 관계 의미를 분리한다.

관계에는 출처, 생성 주체, 제안/확정 상태를 기록한다. 자동 관계는 사용자가 수정·삭제할 수 있어야 한다. 첫 그래프는 현재 논문 중심 1단계, 최대 80개 노드·200개 관계를 보여주고 필요 시 확장한다. 약어, 별칭, 다의어를 문장 일치만으로 자동 병합하지 않는다.

### 6.7 Codex·Claude·실험 실행

**좁은 범위의 자동 연구는 가능 / 난이도: 매우 높음.**

앱은 작업 관리자와 제공자별 어댑터를 가진다. 공통 작업 명세에는 `task_id`, 역할, 입력 근거 ID, 대상 폴더, 허용 권한, 출력 스키마, 시간 한도, 예산 예약을 담는다. 응답에는 제공자·모델·세션 ID, 생성 파일, 질문 미해결 사항, 토큰·비용·오류·재개 정보를 기록한다.

Codex SDK는 공식 문서에서 Python/TypeScript로 로컬 Codex 에이전트를 제어하는 방법을 제공한다. 신규 통합에서 오래된 `codex mcp-server`를 기준으로 구현하지 않는다. 깊은 인증·승인·이벤트 처리가 필요하면 App Server를 검토한다. [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk), [App Server](https://learn.chatgpt.com/docs/app-server)

Claude Agent SDK는 에이전트와 서브에이전트를 지원한다. 서버 프로세스에는 API 인증 설정을 한다. Claude SDK는 `.env`를 자동으로 읽지 않으므로 프로그램 시작 때 불러오거나 환경을 명시적으로 전달한다. [SDK 시작](https://code.claude.com/docs/en/agent-sdk/quickstart), [서브에이전트](https://code.claude.com/docs/en/agent-sdk/subagents)

역할은 문헌 수집, 원문 근거 추출, 계획 작성, 코드 구현, 비판적 검토, 실행, 결과 해석으로 나눈다. 같은 내용을 두 모델에 매번 모두 보내지 않는다. 검색과 중복 제거는 일반 코드로 하고, 논문별 근거 추출은 결과를 캐시한다.

초기 정책 예시는 동시 에이전트 2개, 최대 8회 왕복, 2회 수리, 실행 20분이다. 값은 예시이지 모델별 가격·안전 보장이 아니다. 중앙 예산 원장에서 비용을 예약하고 정산한다. Claude SDK의 개별 호출 제한과 재개 세션 누적 비용은 구분하여 관리한다. [Claude 비용 추적](https://code.claude.com/docs/en/agent-sdk/cost-tracking)

실험은 Docker 컨테이너와 별도 실행 관리자가 맡는다. 컨테이너별 CPU·메모리·프로세스·시간·네트워크·파일 접근을 제한한다. API 비밀키를 모델 작성 코드 실행 프로세스에 전달하지 않는다. 실행 결과는 Git 커밋, 데이터 해시, 환경 lock, 이미지 digest, 명령, seed, 평가 분할, 원시 로그, 종료 코드와 함께 보존한다. [Docker 자원 제한](https://docs.docker.com/engine/containers/resource_constraints/)

재개 가능한 상태는 `created → planning → ready → executing → reviewing → completed`와 `failed`, `blocked`, `cancelled`, `awaiting_user`, `budget_limited`다. 단계 결과를 저장한 후 다음 단계로 이동하고, 같은 `idempotency_key` 작업을 중복 실행하지 않는다. 서브에이전트는 독립 작업의 문맥 격리와 병렬성에 유용하지만 비용 절감은 실제 사용량으로 검증한다.

### 6.8 연구 기록·내보내기

**구현 가능성: 높음 / 난이도: 낮음~중간.**

프로젝트 폴더를 Markdown·BibTeX·JSON으로 내보낸다. `manifest.json`에는 스키마 버전·생성 시각·파일 해시를 기록한다. 원문 PDF 포함 여부를 선택하고, 인용 키가 실제 BibTeX에 존재하는지 검사한다. 제안서나 related work 초안은 저장된 근거와 주장으로 작성하고 원문 링크를 유지한다.

### 6.9 신뢰성·품질

**검사와 추적은 가능 / 오류 0%는 불가 / 난이도: 중간~높음.**

기계 검사: 인용 구절 존재, DOI 형식, 페이지, 단위, JSON 스키마, 파일 해시. 의미 검토: 근거가 주장 내용을 뒷받침하는지, 논문 조건을 과장하지 않았는지, 비교가 공정한지. 사람 검토: 중요 판단과 표본을 원문과 대조한다.

사용자 수정은 모델 재생성보다 우선한다. 원문·모델·프롬프트가 달라지면 결과를 덮어쓰지 않고 새 버전을 만든다. 오류가 어느 논문 버전과 처리 단계에서 생겼는지 추적한다.

## 7. 데이터·API 기본 설계

핵심 데이터 테이블 제안:

| 테이블 | 내용 |
|---|---|
| `projects`, `project_papers` | 연구 목표, 프로젝트별 읽기 상태 |
| `papers`, `paper_sources`, `paper_versions` | 표준 논문, 제공자 응답, PDF 버전과 해시 |
| `chunks`, `chunk_embeddings` | 페이지·섹션 출처가 있는 원문 조각과 모델별 벡터 |
| `claims`, `claim_evidence` | 분석 주장과 실제 PDF 근거 |
| `notes`, `decisions`, `ideas`, `idea_versions` | 개인 지식·연구 방향·아이디어 이력 |
| `entities`, `relations`, `relation_evidence` | 개념 노드와 출처가 연결된 관계 |
| `search_runs`, `comparisons`, `result_records` | 검색 재현, 프로토콜·지표별 비교 |
| `jobs`, `job_events`, `agent_runs`, `usage_ledger` | 작업 상태·이벤트·에이전트 호출·비용 |
| `experiments`, `artifacts`, `feedback` | 코드·실험 환경·결과·사용자 평가 |

예시 API:

```text
POST /api/projects
POST /api/search-runs
POST /api/papers/import
POST /api/papers/{id}/analyses
GET  /api/evidence/{id}
POST /api/comparisons
POST /api/ideas
GET  /api/projects/{id}/graph?depth=1&limit=80
POST /api/research-runs
GET  /api/jobs/{id}
POST /api/jobs/{id}/cancel
POST /api/jobs/{id}/resume
POST /api/projects/{id}/exports
```

무거운 작업은 `202 Accepted + job_id`로 반환한다. 첫 버전에서는 주기 조회로 상태를 확인하고 나중에 SSE를 붙인다. PDF 변환과 모델 작업을 API 요청이 끝날 때까지 동기 실행하지 않는다.

## 8. 개발 환경·상세 설정

### 8.1 폴더와 기반 서비스

Windows에서 브라우저를 사용하고 작업 실행·PDF 파싱은 WSL2/Linux + Docker Desktop으로 통일하는 구성을 권장한다. 예상 시작 환경은 메모리 16GB 이상이며, OCR과 로컬 임베딩을 함께 쓰면 32GB가 더 여유롭다. 이는 검증된 최소 사양이 아니다. GPU는 초기에 API를 쓸 경우 필수가 아니다.

```text
EasyResearch/
  apps/web/
  services/api/app/{api,models,sources,ingestion,retrieval,analysis,orchestration,providers}
  services/api/migrations/
  config/
  data/{papers,parsed,artifacts,runs}/
  compose.yaml
  .env
```

개발용 Compose의 최소 예:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: research
      POSTGRES_USER: research
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set a password}
    ports: ["127.0.0.1:5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U research -d research"]
      interval: 5s
      timeout: 3s
      retries: 10
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["127.0.0.1:6379:6379"]
    volumes: ["redisdata:/data"]
volumes:
  pgdata:
  redisdata:
```

실제 환경에서는 이미지 digest를 고정하고 `.env` 값을 바꾼다. 시작 명령은:

```bash
docker compose up -d
docker compose exec db psql -U research -d research -c 'CREATE EXTENSION IF NOT EXISTS vector;'
docker compose exec db psql -U research -d research -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'
```

### 8.2 서버·화면 패키지

아래 명령은 프로젝트의 출발 절차이며, FastAPI 라우트나 DB 마이그레이션을 자동 생성해 완제품을 만들지는 않는다.

```bash
cd services/api
uv init --python 3.12
uv add fastapi 'uvicorn[standard]' pydantic-settings sqlalchemy 'psycopg[binary]' alembic
uv add pgvector httpx tenacity python-multipart redis rq feedparser rapidfuzz
uv add docling sentence-transformers openai anthropic python-dotenv pybtex
uv add openai-codex claude-agent-sdk
cd ../../apps/web
npm create vite@latest . -- --template react-ts
npm install @tanstack/react-query cytoscape pdfjs-dist react-markdown remark-gfm zod
npm install -D @types/cytoscape
```

Vite 현재 안내는 Node.js 20.19+ 또는 22.12+를 요구한다. [Vite](https://vite.dev/guide/) `uv.lock`과 `package-lock.json`을 저장하고, 재현 설치는 `uv sync --frozen`, `npm ci`로 한다. [uv 설치](https://docs.astral.sh/uv/getting-started/installation/)

서버와 작업자 실행 형태:

```bash
# services/api: 앱 구현과 Alembic 초기화 후 실행
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
uv run rq worker --url redis://127.0.0.1:6379/0 ingest analysis research

# apps/web의 별도 터미널
npm run dev -- --host 127.0.0.1
```

위 명령에서 `app.main:app`과 큐 작업 함수는 직접 구현해야 한다. API 요청에는 Vite 개발 프록시를 설정한다. 무거운 OCR·임베딩의 동시 작업은 우선 1개부터 시작해 메모리를 측정한다.

### 8.3 환경 변수

이 앱에서 읽을 설정 예시다. 모델 ID는 실제 계정에서 지원되는 이름을 설정한다.

```dotenv
POSTGRES_PASSWORD=replace_with_local_random_password
DATABASE_URL=postgresql+psycopg://research:URL_ENCODED_PASSWORD@127.0.0.1:5432/research
REDIS_URL=redis://127.0.0.1:6379/0
DATA_DIR=/absolute/path/EasyResearch/data

OPENALEX_API_KEY=
CROSSREF_MAILTO=
SEMANTIC_SCHOLAR_API_KEY=
ZOTERO_API_KEY=
ZOTERO_USER_ID=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

EXTRACTION_PROVIDER=openai
EXTRACTION_MODEL=SET_AVAILABLE_MODEL_ID
REVIEW_PROVIDER=anthropic
REVIEW_MODEL=SET_AVAILABLE_MODEL_ID
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
MAX_CONCURRENT_AGENTS=2
MONTHLY_BUDGET_USD=30
MAX_RUN_BUDGET_USD=2
EXPERIMENT_TIMEOUT_SECONDS=600
```

30달러·2달러는 지출 한도 설정 예시이지 예측 요금이 아니다. 비용은 OpenAI와 Anthropic의 현행 가격, 모델별 실제 사용량으로 계산한다. [OpenAI API 가격](https://developers.openai.com/api/docs/pricing), [Anthropic 가격](https://platform.claude.com/docs/en/about-claude/pricing)

`.env`는 루트에서 읽도록 경로를 명시한다. Claude Agent SDK는 `.env`를 자동으로 읽지 않는다. 비밀 키를 브라우저 번들이나 실험 프로세스에 전달하지 않는다.

### 8.4 검색·색인 기본값

```yaml
search:
  max_candidates: 150
  show_top: 20
  explain_top: 10
  query_expansions: 4
  cache_hours: 24
  timeout_seconds: 20
  max_retries: 3
parsing:
  preserve_provenance: true
  ocr_when_needed: true
  max_upload_mb: 100
  worker_concurrency: 1
retrieval:
  chunk_target_tokens: 800
  overlap_tokens: 120
  dense_top_k: 30
  lexical_top_k: 30
  final_evidence_k: 8
  fusion: reciprocal_rank_fusion
agents:
  max_concurrency: 2
  max_delegation_depth: 1
  max_turns: 8
  max_repair_attempts: 2
  run_timeout_seconds: 1200
```

BM25라는 명칭은 실제 BM25 구현에만 쓴다. Postgres 전문 검색은 별도 점수이므로 초기 결과는 순위 결합으로 합친다. BGE-M3는 다국어·1024차원 모델이며 처음엔 dense 검색부터 사용한다. 모델 변경 시 기존 벡터와 섞지 않고 새 모델 버전으로 재인덱싱한다. [BGE-M3](https://huggingface.co/BAAI/bge-m3)

pgvector 예:

```sql
CREATE TABLE chunk_embeddings (
  chunk_id uuid PRIMARY KEY,
  model_revision text NOT NULL,
  embedding vector(1024) NOT NULL
);

-- 데이터가 커진 뒤 지연·검색 품질을 재고 추가
CREATE INDEX chunk_embedding_hnsw
  ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);
```

마이그레이션에는 `chunks` 외래키와 생성 시각, 모델별 인덱스 분리를 추가한다. 다른 임베딩 모델의 벡터는 같은 차원이라도 직접 비교하지 않는다. [pgvector](https://github.com/pgvector/pgvector)

### 8.5 Codex·Claude 호출

Codex Python SDK의 기본 형태:

```python
from openai_codex import Codex, Sandbox

with Codex() as codex:
    thread = codex.thread_start(sandbox=Sandbox.read_only)
    result = thread.run("연구 계획을 읽고 빠진 평가 조건을 정리하라.")
    print(result.final_response)
```

공식 SDK 예시는 로컬 Codex 스레드를 열고 결과를 돌려받는 구조다. [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) 실제 구현은 안전한 Git 작업 디렉터리, 실행 위치, 권한, 이벤트 저장을 추가한다. CLI로 시작할 경우에도 인자 배열로 프로세스를 실행하고 JSONL 이벤트 및 명시적인 sandbox를 사용한다. [Codex 비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode)

Claude 코드 검토 예시:

```python
import asyncio
from dotenv import load_dotenv
from claude_agent_sdk import ClaudeAgentOptions, query

async def review(run_directory: str):
    load_dotenv("/absolute/path/EasyResearch/.env")
    options = ClaudeAgentOptions(
        cwd=run_directory,
        tools=["Read", "Glob", "Grep"],
        allowed_tools=["Read", "Glob", "Grep"],
        disallowed_tools=["Bash", "Write", "Edit", "Agent"],
        strict_mcp_config=True,
        mcp_servers={},
        setting_sources=[],
        max_turns=8,
        max_budget_usd=1.0,
    )
    async for event in query(
        prompt="근거와 계획을 읽고 비교 조건 누락을 보고하라.",
        options=options,
    ):
        print(event)  # 제품에서는 구조화·비식별 로그로 저장

# 실행 디렉터리를 준비한 앱 작업 관리자에서 호출한다.
```

Claude SDK에서 `allowed_tools`는 자동 승인 목록일 뿐 다른 도구를 제한하지 않는다. 읽기 전용 예제는 `disallowed_tools`도 지정하며 실제 읽기 범위는 OS 권한과 컨테이너 마운트로 제한한다. SDK 옵션은 버전 업데이트 때 확인한다. [Claude Python SDK](https://code.claude.com/docs/en/agent-sdk/python)

### 8.6 실험 컨테이너

네트워크 차단 CPU 실험의 예. 실행 관리자가 별도 타이머로 제한 시간을 지켜야 한다.

```bash
docker run --rm \
  --network none --cpus 2 --memory 4g --pids-limit 128 \
  --cap-drop ALL --security-opt no-new-privileges --read-only \
  --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,nosuid,size=512m \
  --mount type=bind,source=/path/run-code,target=/workspace,readonly \
  --mount type=bind,source=/path/dataset,target=/data,readonly \
  --mount type=bind,source=/path/run-output,target=/output \
  --workdir /workspace research-experiment:validated \
  python run_experiment.py --data /data --output /output
```

이미지에 의존성을 미리 설치하고 digest를 기록한다. GPU·네트워크가 필요한 실험은 별도 프로필로 접근 범위와 예산을 지정한다. Docker 제한은 위험을 낮추지만 모든 위험을 없애지는 않는다.

## 9. 저장소·단계별 개발

초기에는 논문·원문 버전·근거·관계를 분리하는 스키마로 시작한다. 같은 논문을 여러 프로젝트에서 공유하되, 분석 근거는 반드시 당시 원문 버전을 가리킨다.

| 단계 | 결과 | 계획 시간 (1인, 주 10~15시간 가정) |
|---|---|---:|
| 0 | 논문 10편에서 PDF 구조·페이지 근거 검증 | 1~2주 |
| 1 | 프로젝트·등록·읽기 상태·메모·내보내기 | 2~3주 |
| 2 | 검색·추천·원문 분석·근거 페이지 이동 | 3~5주 |
| 3 | 비교표·아이디어·개념 그래프 | 3~5주 |
| 4 | 한 제공자의 실행·작업 중단/재개·실험 기록 | 3~5주 |
| 5 | 두 번째 제공자·서브에이전트·비용 비교·알림 | 2~4주 |

전체 14~24주 또는 140~360시간은 구현 경험과 자료 형식에 크게 좌우되는 계획 범위이며 견적이 아니다. 1~2단계만으로도 개인 연구에서 사용할 수 있는 핵심 도구를 만든다. 초기에 매 주제를 모두 지원하지 말고 자신이 아는 논문으로 검색·근거의 문제를 먼저 찾는다.

## 10. 품질 확인 기준

아래는 이후 구현에서 쓸 검증 계획이며 이번 보고서 작성 시 실행한 테스트가 아니다.

| 기능 | 검증 사례 | 초기 완료 기준 |
|---|---|---|
| 등록 | DOI·arXiv·출판본 중복 | 식별자 정규화, 원문 버전 분리 |
| PDF | 2단 논문·표·스캔·부록 | 실패 감지, 원문 페이지로 이동 |
| 분석 | 사람 지정 주장 50개 | 인용 구절 존재 100%, 의미 지지율 별도 사람 평가 |
| 검색 | 알려진 질문 10개 | 상위 후보 유용성·비용·속도 기록 |
| 비교 | 지표·분할·데이터가 다른 논문 | 조건 차이 또는 비교 불가 표시 |
| 그래프 | 중복 약어·동명 엔티티 | 관계 출처 확인·취소 가능 |
| 자동화 | CPU baseline 1건 | 커밋·데이터·환경·로그·지표 보존 |
| 재개 | 프로세스 중단·API 429·시간 초과 | 마지막 완료 단계부터 이어짐 |
| 복구 | DB와 파일 백업 복원 | 프로젝트·PDF·메모·관계 연결 확인 |

기계적 스키마 통과율과 과학적 사실 정확도를 하나의 점수로 합치지 않는다. 사용자가 오류를 쉽게 찾고 수정할 수 있는지도 별도로 평가한다.

## 11. 비용과 성능 관리

월 비용은 선택 모델, 입력 PDF 길이, 이미지 분석, 재시도와 실험 횟수에 따라 달라진다. OpenAI·Anthropic의 현행 가격과 실제 토큰을 기준으로 계산한다. SDK 사용량과 총 비용에 중복 포함된 항목을 재합산하지 않는다. 불확실한 비용은 0이 아니라 미확정으로 표시한다.

비용 절감 순서:

1. 파일 해시를 이용해 PDF 파싱과 임베딩을 재사용한다.
2. 메타데이터로 후보를 줄인 뒤 선택된 논문만 상세 분석한다.
3. 비교표를 이미 추출한 값에서 생성한다.
4. 이미지 모델은 필요한 페이지에서만 실행한다.
5. 전체 대화 대신 필요한 근거와 확정 결정만 에이전트에 전달한다.
6. 에이전트는 독립 작업이 있을 때만 추가하고 사용량을 단일 실행과 비교한다.

첫 성능 병목은 OCR·로컬 임베딩·긴 모델 요청에서 생길 수 있다. 화면은 저장된 결과를 즉시 보여주고 분석은 백그라운드에서 진행한다. API 장애나 PDF 파싱 실패도 작업 상태로 남기고 재시도 횟수를 제한한다.

## 12. 최종 구현 권장

1. 개인용 로컬 웹앱으로 시작한다.
2. React/Vite + FastAPI + PostgreSQL/pgvector + Redis/RQ를 쓴다.
3. PDF 버전·근거·페이지 이동을 먼저 구현한다.
4. 논문 추천·읽기·비교·아이디어·그래프가 같은 근거 모델을 공유하게 한다.
5. Codex·Claude는 명시적인 작업 상태와 예산을 관리하는 서버 측 어댑터로 연결한다.
6. 초기 자동 연구는 작은 계산 실험의 재현성과 산출물 기록을 목표로 한다.
7. 참신성·실험 성공·환각 제거를 보장 기능으로 약속하지 않고 검증 가능한 범위와 근거를 표시한다.

## 13. 출처와 조사 한계

### 유사 서비스

- [Elicit](https://elicit.com/solutions/systematic-review)
- [SciSpace](https://scispace.com/)
- [ResearchRabbit](https://www.researchrabbit.ai/features)
- [Litmaps](https://www.litmaps.com/features)
- [Zotero](https://www.zotero.org/support/quick_start_guide)
- [Obsidian Graph](https://obsidian.md/help/plugins/graph)
- [PaperQA2](https://github.com/Future-House/paper-qa)
- [Kosmos](https://edisonscientific.com/news/announcing-kosmos)
- [AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)
- [Rosalind Workbench](https://learn.chatgpt.com/blog/rosalind-workbench)

### 자료·구현 문서

- [OpenAlex API](https://help.openalex.org/api/llm-quick-reference/)
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [arXiv API](https://info.arxiv.org/help/api/user-manual.html)
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/)
- [Unpaywall API](https://unpaywall.org/products/api)
- [Zotero Web API v3](https://www.zotero.org/support/dev/web_api/v3/)
- [Docling](https://docling-project.github.io/docling/)
- [PDF.js](https://mozilla.github.io/pdf.js/getting_started/)
- [BGE-M3](https://huggingface.co/BAAI/bge-m3)
- [pgvector](https://github.com/pgvector/pgvector)
- [Cytoscape.js](https://js.cytoscape.org/)
- [Vite](https://vite.dev/guide/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [RQ](https://python-rq.org/docs/)
- [Docker resource limits](https://docs.docker.com/engine/containers/resource_constraints/)
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Claude Agent SDK quickstart](https://code.claude.com/docs/en/agent-sdk/quickstart)
- [Claude Agent SDK Python](https://code.claude.com/docs/en/agent-sdk/python)
- [Claude subagents](https://code.claude.com/docs/en/agent-sdk/subagents)
- [Claude cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing)

조사 시 공식 페이지와 공개 저장소를 확인했으며, 제품 직접 사용, 개별 플랜 접근권, API 키·하드웨어 사양은 검증하지 않았다. 외부 원문 접근권은 각 출판사·자료 라이선스를 따라야 한다.
