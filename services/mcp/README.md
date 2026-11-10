# EasyResearch MCP 서버 (읽기 도구 + 초안 쓰기 도구)

로컬에서 실행 중인 EasyResearch API(`http://127.0.0.1:8000`)를 MCP 도구로 노출합니다.
읽기 도구는 GET만 보냅니다. 쓰기 도구는 POST만 보내며, 세 가지 초안만 만듭니다: 논문 정리(profile), 논문 연결(suggested), 갭 후보(candidate). 모든 쓰기는 `origin: "agent"`로 저장되고, 확정과 삭제는 앱에서 사람이 합니다. PDF 본문과 발췌는 신뢰하지 않는 데이터로 감싸서 반환합니다.
삭제, 확정, 상태 변경, 연구 루프 실행은 MCP로 노출하지 않습니다.

## 설치

`mcp` 패키지는 앱이 쓰는 FastAPI와 다른 `starlette` 버전을 요구할 수 있습니다. 앱 환경을 깨지 않도록 **별도 가상환경**에 설치하세요. MCP 서버는 표준 라이브러리 HTTP로 앱에 접속하므로 앱 패키지가 필요 없습니다.

```powershell
python -m venv services\mcp\.venv
services\mcp\.venv\Scripts\python -m pip install -r services\mcp\requirements.txt
```

`mcp` 패키지가 없으면 서버는 설치 안내를 표준 오류로 출력하고 종료합니다.

## Claude Code에 등록

EasyResearch 앱을 먼저 실행한 뒤 다음 명령을 실행합니다.

```
claude mcp add easyresearch -- C:\Users\user\Desktop\EasyResearch\services\mcp\.venv\Scripts\python.exe C:\Users\user\Desktop\EasyResearch\services\mcp\easyresearch_mcp.py
```

JSON 설정 파일을 직접 쓰는 경우:

```json
{
  "mcpServers": {
    "easyresearch": {
      "command": "C:\\Users\\user\\Desktop\\EasyResearch\\services\\mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\user\\Desktop\\EasyResearch\\services\\mcp\\easyresearch_mcp.py"]
    }
  }
}
```

## 제공 도구

읽기 도구 (GET, `readOnlyHint: true`)

- `list_projects`: 프로젝트 목록
- `get_project_context(project_id)`: 프로젝트 맥락 (PDF 유래 텍스트 포함, 신뢰하지 않는 데이터로 감쌈)
- `search_library(project_id, query, offset)`: 보관함 검색 (감쌈)
- `get_paper_evidence(paper_id)`: 논문 근거 목록 (감쌈)
- `get_page_text(paper_id, page_index)`: 페이지 텍스트, `page_index`는 0부터 (감쌈)
- `list_library_papers(status=None, q=None)`: 보관함 논문 목록 (`GET /api/library/papers`)
- `get_paper_profile(paper_id)`: 최신 논문 정리와 이력 (감쌈)
- `get_library_graph()`: 논문 연결 그래프 (노드와 간선)
- `list_gaps(project_id=None, paper_id=None)`: 갭 후보 목록 (감쌈)
- `list_research_runs()`: 연구 루프 실행 목록
- `get_research_run(run_id)`: 실행의 단계와 현재 결과 (감쌈)

초안 쓰기 도구 (POST, `X-EasyResearch: 1` 헤더, `origin: "agent"`, `readOnlyHint: false`, `destructiveHint: false`)

- `save_paper_profile(paper_id, profile, model="")`: 논문 정리 초안을 `POST /api/papers/{id}/profile`로 저장합니다. `profile`은 `summary`, `facets`(고정된 키), `keywords`를 따릅니다. 인용 구절은 API가 저장된 페이지 텍스트와 다시 대조합니다. 응답은 감쌉니다.
- `suggest_paper_link(source_paper_id, target_paper_id, relation, note="")`: `POST /api/paper-links`로 연결을 `suggested` 상태로 만듭니다. 확정은 앱에서 합니다.
- `add_gap_candidate(paper_ids, title, description, gap_type="other", evidence=None, project_id=None)`: `POST /api/gaps`로 갭 후보를 `candidate` 상태로 만듭니다. `evidence`는 `[{paper_id, quote, page?, facet?}]` 목록입니다. 응답은 감쌉니다.

API가 오류를 반환하면 도구는 API의 `detail` 메시지를 담아 오류를 냅니다. 앱에 연결할 수 없으면 실행 안내를 냅니다.

읽기 도구 힌트는 신뢰할 수 있는 보장이 아닙니다. 읽기 도구 코드는 GET만 쓰고, 쓰기 도구는 위 세 경로의 POST만 씁니다. 테스트(`tests/test_easyresearch_mcp.py`)가 이 경로와 헤더를 확인합니다.

## 스킬

`skills/` 폴더에 Agent Skills 규격의 스킬 4종이 있습니다: `easyresearch-paper-profile`, `easyresearch-gap-finder`, `easyresearch-idea-refiner`, `easyresearch-research-loop`. 이 스킬들은 위 도구를 사용합니다. 설치 방법은 [skills/README.md](skills/README.md)를 보세요. 스킬을 쓰려면 이 MCP 서버가 먼저 등록되어 있어야 합니다.
