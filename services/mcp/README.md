# EasyResearch 읽기 전용 MCP 서버

로컬에서 실행 중인 EasyResearch API(`http://127.0.0.1:8000`)를 MCP 도구로 노출합니다.
쓰기 요청(POST/PUT/PATCH/DELETE)은 보내지 않으며, PDF 본문과 발췌는 신뢰하지 않는 데이터로 감싸서 반환합니다.

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

- `list_projects`: 프로젝트 목록
- `get_project_context(project_id)`: 프로젝트 맥락 (PDF 유래 텍스트 포함)
- `search_library(project_id, query, offset)`: 보관함 검색
- `get_paper_evidence(paper_id)`: 논문 근거 목록
- `get_page_text(paper_id, page_index)`: 페이지 텍스트

모든 도구는 `readOnlyHint`를 표시하지만, 이 힌트는 신뢰할 수 있는 보장이 아닙니다. 서버 코드가 GET만 사용합니다.
