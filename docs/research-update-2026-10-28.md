# 구현에 직접 적용할 레퍼런스 검토

조사일: 2026-10-28. 공식 문서와 공개 저장소를 읽고 현재 구현에 대조했다. 실제 API, 파서 후보의 성능이나 악성 PDF는 이 조사에서 실행하지 않았다. 다음 판단은 비교 실험 전의 작업 우선순위다.

## 1. PDF.js 보안과 표시

후속 조치: 공식 npm 패키지 6.2.108로 교체했다. 내려받은 tarball의 SHA-256은 `b3e68d5cda70551a90b3f771419d379e20fc788ce056fa32de73608e01df47f4`다. 합성 PDF의 표시, 페이지 이동과 글 선택은 브라우저에서 확인했다. 아래 내용은 교체 전 조사 기록이다.

- 이 조사에서 확인한 번들은 `pdfjs-dist` 5.6.205이며, 공식 [GHSA-hq66-cqwq-w95j](https://github.com/advisories/GHSA-hq66-cqwq-w95j)의 영향 버전 `>=5.6.83, <6.2.108`에 포함된다. 공식 수정 버전은 6.2.108이다. [릴리스 목록](https://github.com/mozilla/pdf.js/releases)에서 6.4.299를 확인했다. 설치 전 파일 출처, 무결성, 버전, 브라우저 호환성을 검증한다.
- 패키지 버전이 영향 범위에 포함된다는 사실과 현재 앱에서 취약 경로가 실행된다는 사실은 다르다. 수정 커밋은 [XFA와 rich-text DOM 생성 제한](https://github.com/mozilla/pdf.js/commit/6c18df5768a9cf12e725ebf12fc70e32358be1fa), [PDFScriptingManager의 필드 ID 확인](https://github.com/mozilla/pdf.js/commit/4ea07c2431141fe66df3a2f53af53cc8ad854191)을 다룬다. 조사 당시 `pdf-viewer.js`는 `getDocument`, Canvas `page.render`, `TextLayer`만 사용하며 XfaLayer, AnnotationLayer, PDFScriptingManager를 호출하지 않았다. 번들에서 `enableXfa`는 명시적으로 `true`일 때만 켜진다. **악성 PDF로 재현하지 않았으므로 현재 앱의 악용 가능 여부는 확정하지 않는다.**
- 런타임의 PDF.js와 npm 캐시를 확인했으며 수정된 버전은 발견하지 못했다. 설치 가능한 수정판으로 업데이트하고 텍스트 선택, 여러 페이지, 글꼴, 수식과 스캔을 다시 확인한다. XFA와 문서 스크립트는 제품에 필요하지 않으므로 명시적으로 비활성화하고 CSP를 별도로 검토한다. CSP를 추가할 때 PDF.js 모듈, 워커, 로컬 글꼴과 WASM이 실제로 계속 동작하는지 확인한다.
- 위치 저장은 화면 픽셀이 아니라 원본 PDF 좌표와 물리 페이지, CropBox, 회전, 파일 해시를 함께 저장하는 설계로 진행한다. [PDF.js 페이지 API](https://mozilla.github.io/pdf.js/api/draft/api.js.html)는 페이지의 가시 영역과 변환에 필요한 viewport를 제공한다. 여러 줄, 확대, 회전, CropBox 차이가 있는 실제 문서에서 좌표를 왕복 검증한 뒤 하이라이트를 제공한다.

## 2. 파서 선택과 평가

- [Docling 문서 모델](https://docling-project.github.io/docling/concepts/docling_document/)은 표·문서 계층·레이아웃과 출처 정보를 표현한다. 좌표가 존재한다는 사실은 원문과 일치한다는 보장이 아니다. JSON 원본, 문서 해시, 페이지, 변환 버전과 옵션을 보존하고 기존 근거는 재처리로 변경하지 않는다.
- [고급 설정](https://docling-project.github.io/docling/usage/advanced_options/)에 따르면 모델 가중치는 최초 사용 시 내려받을 수 있고 미리 받아 오프라인에서 사용할 수 있다. 원격 모델 서비스 활성화와 가중치 다운로드는 서로 다른 문제다. 설치·다운로드 시기와 크기를 사용자에게 설명하고 모델 식별자와 라이선스를 기록한다. 표 셀 매칭과 OCR 언어, 수식 보강 설정은 동일 PDF에서 별도로 비교한다.
- [Docling 평가 도구](https://github.com/docling-project/docling-eval)는 글, 레이아웃, 읽기 순서, 표 구조의 평가 체계를 제공한다. [olmOCR-Bench](https://github.com/allenai/olmocr/blob/main/olmocr/bench/README.md)는 문구 존재, 문단 순서, 표 셀 관계, 수식을 별도 사실로 검사한다. 다만 단일 페이지 기준이므로 문서 전체 페이지 대응이나 브라우저 하이라이트를 대신 검증하지 못한다.
- [OmniDocBench](https://github.com/opendatalab/OmniDocBench)는 다양한 페이지와 레이아웃 정답 자료를 제공한다. 해당 저장소는 데이터의 연구 목적 사용과 상용 사용 금지를 명시한다. 데이터셋 및 원본 PDF의 배포·사용 조건을 별도 검토하고 앱에 함께 배포하지 않는다. README의 데이터 버전 설명이 여러 구간에서 일치하지 않아 실행 전 실제 고정 커밋과 데이터 릴리스를 확인한다.
- EasyResearch 평가셋은 사용자 연구 분야의 실제 문서도 포함해야 한다. 각 사례에 원문 해시, 접근 허용 여부, 실제 PDF 페이지, 인쇄 페이지 라벨, 확인 문구, 읽기 순서, 표의 셀 관계, 수식의 핵심 기호, 시간·메모리와 실패를 기록한다. 결과를 유형별로 보고하고 합성 테스트와 실논문 수치를 혼합하지 않는다.
- [MinerU](https://github.com/opendatalab/MinerU)는 대안 후보지만 자체 라이선스와 모델별 조건을 확인해야 한다. [Marker 모델 라이선스](https://github.com/datalab-to/marker/blob/master/MODEL_LICENSE)도 코드와 별도다. 성능 주장과 리더보드 수치를 현재 PC 또는 사용자 논문의 실측으로 취급하지 않는다.

## 3. 검색 API와 사용자 경험

- [OpenAlex 인증](https://help.openalex.org/api/authentication/)은 무키 요청과 `Authorization: Bearer`를 지원한다. 현재 코드의 Bearer 방식은 공식 방식이다. 서비스는 응답에 일일 예산과 사용량 헤더를 제공하므로 나중에 출처별 상태, 비용·제한, 재시도 가능 시각을 표시할 수 있다. 키는 서버 환경에만 보관하고 로그·검색 이력에 넣지 않는다. 공개 요금과 제한은 바뀔 수 있으므로 적용 직전에 다시 확인한다.
- [Crossref 접근 규칙](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication)은 공개 풀의 동시 요청을 1개로 명시한다. 현재 출처별 백오프와 전역 동시성 제한이 필요하다. 응답의 제한 헤더를 참고하고, 429 또는 일시 오류는 실패로 보여주며 제한된 횟수의 지수 백오프 및 캐시를 고려한다. `mailto`는 사용자가 제공한 경우에만 선택적으로 설정한다.
- [arXiv API 설명서](https://info.arxiv.org/help/api/user-manual.html)의 질의 문법과 버전 식별자를 보존한다. 현재 정확한 구절 검색은 쉬우나 복잡한 질의를 모두 표현하지 못하므로 일반 검색과 고급 검색을 구분하고 실제 결과로 품질을 비교한다. 검색 결과는 제공자의 메타데이터이며 원문 접근 가능이나 주장의 진실을 보장하지 않는다.

## 4. 근거 기반 분석과 에이전트 UX

- 현 분석은 발췌 ID가 존재하는지 확인하고 의미상 지지는 미검증으로 남긴다. 이 구분을 유지한다. 주장별로 어떤 원문을 읽었는지, 추출인지 OCR인지, 사용자 확인 여부, 근거 부족을 함께 표시한다. 직접 지정한 발췌가 관련 있다는 사실을 자동으로 가정하지 않는다.
- 평가 질문을 지원·불충분·상충 사례로 나누고, 구절 존재와 페이지 일치, 주장 지지율, 근거 부족 감지율을 각각 사람이 확인한다. 한국어 질문과 영어 발췌, 동일 구절 반복, 표와 수식, OCR 오류, 논문 내 악성 지시를 포함한다. 구조화 출력은 형식과 ID 확인에 도움을 주지만 의미 정확성을 보장하지 않는다.
- 에이전트가 읽는 프로젝트 컨텍스트는 버전과 크기 제한을 명시하고, 원문·메모가 외부로 나가는 범위는 사람이 확인할 수 있어야 한다. 사용자 지시와 논문에 포함된 내용을 구분해 처리한다. 변경 작업은 관련 API의 권한 및 데이터 계약을 따른다.

## 5. Codex와 실험

- [Codex 비대화 실행](https://learn.chatgpt.com/docs/non-interactive-mode)은 읽기 전용 sandbox, JSONL 이벤트, 구조화 출력, 타임아웃과 권한 설정을 이용하는 방향을 제공한다. 읽기 전용은 도구가 실행되지 않는다는 뜻이 아니다. 현 구현처럼 요구한 도구 제한을 확인하지 못할 때 제안 기능을 차단하는 결정을 완화하려면, 실제 CLI 버전의 기능과 OS 격리를 별도로 검증해야 한다.
- 지속적인 대화·이벤트·승인 처리가 필요하면 [Codex App Server](https://learn.chatgpt.com/docs/app-server)를 별도 후보로 비교한다. 세션 상태와 실제 실험 프로세스, 저장된 실험 결과는 분리한다. 선택한 근거만 전송하고, 생성 코드는 바로 호스트에서 실행하지 않는다.
- [OpenAI 실행 환경 보안](https://developers.openai.com/api/docs/guides/agents-api/environments/security)은 실행 환경의 파일과 자격 증명에 생성 코드가 접근할 수 있다고 명시한다. 컨테이너의 네트워크, 마운트, 권한, CPU·메모리·시간과 출력을 제한하고, 인증 정보는 실행 환경 밖에 둔다. [Docker 보안 문서](https://docs.docker.com/engine/security/)의 daemon 권한도 별도 경계다. 제약을 설정한 컨테이너를 적대적인 코드에 대한 완전한 격리로 간주하지 않는다.
- 실험 비교에는 입력과 데이터 분할 해시, 실행 코드 해시, 이미지 digest, 의존성, 시드, 평가 코드, 지표·단위, 종료 이유와 로그를 남긴다. 평가 코드와 데이터 분할은 모델이 제안한 코드와 분리한다. Docker 엔진과 실제 Codex 인증·권한이 없는 환경에서는 모의 테스트와 실환경 실행 여부를 명확히 구분한다.
