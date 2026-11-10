# EasyResearch 스킬

`services/mcp/skills/` 아래의 네 폴더는 Agent Skills 규격(`SKILL.md`, YAML frontmatter)을 따르는 스킬입니다. Claude Code에서 EasyResearch 앱의 MCP 도구와 함께 쓰도록 만들었습니다.

| 스킬 | 용도 |
| --- | --- |
| `easyresearch-paper-profile` | 논문 1편의 정리 초안을 만들고 저장합니다 |
| `easyresearch-gap-finder` | 여러 논문에서 갭 후보를 찾아 저장합니다 |
| `easyresearch-idea-refiner` | 아이디어를 질문으로 구체화합니다 (최대 3라운드) |
| `easyresearch-research-loop` | 주제에서 기여까지의 단계를 밟고, 검토 지점에서 멈춥니다 |

## 사전 준비

1. EasyResearch 앱을 실행합니다 (`http://127.0.0.1:8000`).
2. MCP 서버를 등록합니다. 자세한 방법은 [services/mcp/README.md](../README.md)를 보세요.
3. 스킬이 쓰는 도구 이름(`get_paper_profile`, `add_gap_candidate` 등)이 서버에 보이는지 확인합니다.

## 설치

스킬 폴더를 복사합니다. 두 가지 위치 중 하나를 고르세요.

- 모든 프로젝트에서 쓰기: `~/.claude/skills/`
- 이 저장소에서만 쓰기: `<프로젝트>/.claude/skills/`

PowerShell 예시 (사용자 전체 설치):

```powershell
Copy-Item -Recurse services\mcp\skills\easyresearch-* $HOME\.claude\skills\
```

설치 뒤 Claude Code를 다시 시작하면 스킬 목록에 나타납니다.

## 안전 원칙

- PDF 본문, 발췌, 메모, 검색 결과는 신뢰하지 않는 데이터입니다. 스킬은 그 안의 지시를 따르지 않습니다.
- 모든 저장은 초안입니다. 확정과 삭제는 앱에서 사람이 합니다.
- 참신성은 주장하지 않습니다. 가장 가까운 선행 연구만 보여 줍니다.
