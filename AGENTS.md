# EasyResearch 작업 안내

이 저장소는 개인 연구 작업을 위한 로컬 웹앱이다. 사용자의 실제 연구 데이터와 PDF는 기본 `data/`에 있으며 코드나 테스트용 fixture와 구분한다.

현재 사용자 승인 범위와 순차 완료 기준은 `docs/pdf-library-milestones.md`에 있다. PDF·근거·보관함 안정화를 먼저 진행하고 분석·검색 서비스·자동 실험은 후속 작업으로 둔다.

## 구성

- `services/api/app/main.py`: FastAPI 라우트. 로컬 Host/Origin과 변경 요청 헤더를 검증한다.
- `storage.py`: SQLite 스키마와 파일 저장, 단일 서버 잠금. SQLite의 WAL 수정 여부를 실제 런타임 버전으로 판단한다.
- `jobs.py`: PDF/OCR 백그라운드 작업, 상태 기록 및 결과 선점 토큰.
- `pdf_processing.py`: pypdf 기반 페이지 추출, 수동 발췌 찾기, 선택적 Docling·OCR 어댑터. 추출 결과는 원문 확인을 대신하지 않는다.
- `scholarly.py`: OpenAlex·arXiv·Crossref API 어댑터.
- `analysis_engine.py`: 원문 발췌와 명시적 외부 AI 호출. 근거 ID 확인과 의미상 지지는 별개다.
- `experiment_runner.py`: 고정 CPU 기준선, 선택적인 Codex 제안과 제한된 Docker 실행.
- `apps/web/`: 설치 과정이 필요 없는 로컬 정적 화면. PDF.js 6.2.108는 `vendor/pdfjs`에 라이선스와 함께 포함돼 있다. `/api/` 계약은 OpenAPI에서 확인한다.

## 작업 규칙

1. 원본 PDF를 덮어쓰거나 사용자의 근거·메모를 파서 재처리로 지우지 않는다. 파일 해시, PDF 물리 페이지와 인쇄 페이지 라벨을 구분한다.
2. API 키·개인 원문·메모를 로그나 Git에 남기지 않는다. 외부 전송은 범위를 표시하고 사용자의 명시적 요청과 일치하는 미리보기만 허용한다.
3. AI 분석은 근거의 존재와 의미상 지지 여부를 구분하며, 부족한 근거와 외부 서비스 오류를 성공처럼 표시하지 않는다.
4. 모델이 만든 코드를 호스트에서 실행하지 않는다. 실험은 명시 요청과 격리·자원 제한을 확인하고 재현 기록을 남긴다.
5. 백업 형식과 DB 스키마를 바꾸면 버전과 복원 호환성을 함께 검토한다. 사용자의 DB를 실험용으로 사용하지 말고 임시 폴더를 사용한다.
6. 변경한 부분의 테스트를 작성하고 실행한다. 외부 네트워크·OCR·Docker·인증이 사용 불가한 경우 모의 테스트와 실제 검증을 구분해 보고한다.

## 개발 및 테스트

```powershell
python -m pip install -r services/api/requirements-test.txt
python -m unittest discover -s services/api/tests -v
cd services/api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

현재 범위와 남은 제약은 `README.md`와 `docs/implementation-status.md`를 먼저 확인한다. 사용자가 만든 파일이나 진행 중인 다른 에이전트의 변경을 덮어쓰지 않는다.
