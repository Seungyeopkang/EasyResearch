# EasyResearch

개인용 연구 작업 공간입니다. 논문 탐색과 검토, 읽기 기록, 아이디어·지식 연결, 재현 가능한 연구 실행을 목표로 합니다.

## 실행

Windows에서는 프로젝트 폴더의 `EasyResearch 시작.cmd`를 실행합니다. 앱이 준비되면 기본 브라우저가 열립니다. 실행 창을 열어 두고, 종료하려면 해당 창에서 `Ctrl+C`를 누르세요. Python이나 필수 패키지가 없으면 실행 창에 설치 안내가 표시됩니다. 브라우저가 자동으로 열리지 않으면 `http://127.0.0.1:8000`에 직접 접속합니다.

PowerShell에서 직접 실행할 수도 있습니다.

```powershell
cd C:\Users\user\Desktop\EasyResearch
python -m pip install -r services/api/requirements.txt
cd services/api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

서버를 중지하려면 실행 중인 터미널에서 `Ctrl+C`를 누릅니다. 사용자 데이터는 기본적으로 프로젝트의 `data/`에 저장되며 Git에 포함되지 않습니다. 다른 위치를 사용하려면 서버를 시작하기 전에 `EASYRESEARCH_DATA_DIR` 환경 변수를 지정합니다. 한 데이터 폴더는 한 서버만 사용할 수 있습니다.

현재 앱은 PDF 등록·중복 감지, 프로젝트와 읽기 상태, 페이지 메모 및 발췌, 출처별 검색, 근거 발췌 분석·비교, 아이디어, 고정 CPU 기준 실험, 내보내기와 백업·별도 폴더 복원을 제공합니다. PDF.js 뷰어에서 현재 표시된 페이지의 글을 선택하면 발췌와 파일 페이지가 입력됩니다. 이미지 페이지에서는 페이지 메모 또는 OCR을 사용할 수 있습니다. 저장한 근거의 정밀 하이라이트는 아직 제공하지 않습니다.

프로젝트별 메모는 해당 프로젝트에만 저장되며, 발췌와 발췌에 붙인 메모는 같은 논문을 연결한 프로젝트 사이에서 공유됩니다. 프로젝트·논문·근거는 휴지통에서 복구할 수 있습니다. 메모와 발췌의 임시 기록은 현재 브라우저에만 있으며 백업에 포함되지 않으므로 보관하려면 저장해야 합니다. 여러 창의 프로젝트 메모가 충돌하면 최신 내용과 입력을 비교한 뒤 저장할 수 있습니다.

PDF 없이 제목·저자·연도·DOI를 직접 입력해 먼저 보관할 수 있으며 PDF는 나중에 연결할 수 있습니다. PDF 본문과 로컬 메모·발췌를 보관함에서 검색하고, 서지정보를 수정하거나 같은 논문의 추가 PDF를 보관할 수 있습니다. 추가 버전의 이름 수정과 휴지통 복구는 논문 화면의 ‘다른 PDF 버전’에서 할 수 있습니다. 추가 버전은 별도 파일로 열리며 발췌와 읽기 기록은 기본 PDF에 연결됩니다. 텍스트 추출, OCR, 표와 수식은 원문 대조가 필요하며, PDF에서 선택한 문구의 앞뒤 문맥은 위치 후보를 찾는 단서입니다.

검색은 인터넷 연결이 필요합니다. 외부 AI 분석은 서버에 `OPENAI_API_KEY`가 설정되고 사용자가 전송 내용을 확인한 경우에만 호출합니다. 키 없이도 원문 발췌 검색과 비교를 사용할 수 있으며 이 결과는 AI가 생성한 답변이 아닙니다. Windows OCR과 Poppler가 사용 가능한 환경에서는 설치된 언어를 선택해 한 페이지씩 OCR을 요청할 수 있습니다. OCR 결과는 원문과 대조해야 합니다. Docling은 선택 의존성이며 현재 기본 PDF 추출 경로는 pypdf입니다. Codex 제안과 모델 생성 코드 실행은 실행 환경의 기능 제한과 Docker 사용 가능 여부가 확인되지 않으면 차단됩니다.

백업 화면에서 ZIP 내용을 확인한 뒤 복원하면 기존 보관함을 덮어쓰지 않고 별도 폴더에 검증된 사본이 만들어집니다. 복원본을 사용하려면 현재 앱을 종료하고 프로젝트 폴더의 `복원 보관함 열기.cmd`를 실행한 뒤 목록에서 복원 번호를 선택합니다. 도구는 복원본의 데이터베이스와 PDF를 다시 검사합니다. 복원본에 새로 저장한 내용은 기존 보관함과 별도로 보존됩니다. 원래 보관함으로 돌아가려면 복원본 실행 창을 닫고 `EasyResearch 시작.cmd`를 실행하세요.

## 테스트

```powershell
python -m pip install -r services/api/requirements-test.txt
python -m unittest discover -s services/api/tests -v
```

합성 PDF와 모의 API 응답을 사용하는 자동 테스트입니다. 실제 논문 표본의 표·수식 정확도, OCR 품질과 외부 서비스 연결은 별도로 검증해야 합니다.

## 문서

- [현재 작업 범위와 단계별 완료 기준](docs/pdf-library-milestones.md) — PDF·근거·개인 보관함 안정화.
- [공개 논문과 스캔 PDF 품질 평가](docs/pdf-quality-scan-and-parser-comparison.md) — 원문 대조와 추출기 비교, 아직 확인하지 못한 항목.
- [기능 평가와 구현 설계](docs/research-assistant-feasibility-and-implementation.md)
- [구현 우선순위와 최신 레퍼런스 조사](docs/implementation-decisions-and-reference-review.md) — 2026-10-28 기준 후속 결정. 첫 버전의 기술 구성과 작업 순서는 이 문서를 따른다.
- [PDF 읽기와 원문 근거 상세 설계](docs/pdf-reading-and-evidence-design.md) — 첫 기능의 화면, 저장 구조, 작업 처리와 평가 기준.
- [구현 현황과 다음 작업](docs/implementation-status.md) — 현재 동작, 검증 범위와 남은 작업.

API 명세는 앱 실행 중 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다. 에이전트는 프로젝트의 `/api/projects/{id}/context`에서 논문·근거·아이디어를 구조화된 JSON으로 읽을 수 있습니다. 변경 요청에는 `X-EasyResearch: 1` 헤더가 필요합니다.
