# 실제 스캔 논문과 대안 추출기 대조

평가일: 2026-10-29. 기존 [원문 대조](pdf-quality-evaluation.md), [추가 대조](pdf-quality-followup.md)에 이어 공개 원문을 임시 폴더에 받아 페이지를 렌더링하고 추출 문자열과 비교했다. 사용자 PDF와 보관함은 사용하지 않았다. 원문 PDF와 페이지 이미지는 저장소에 포함하지 않는다. 아래는 선택한 사례의 결과이며 전체 정확도나 통계적인 성능 점수가 아니다.

## 자료와 확인한 범위

| 자료 | 조건 | SHA-256, 크기, 물리 페이지 수 | 눈으로 대조한 물리 페이지 |
|---|---|---|---|
| Basu·Stewart, [The Effect of Heparin on the Plasma Cholesterol](https://pmc.ncbi.nlm.nih.gov/articles/PMC5294554/), 1950, PMC5294554.1 | [메타데이터](https://pmc-oa-opendata.s3.amazonaws.com/PMC5294554.1/PMC5294554.1.json), [PDF](https://pmc-oa-opendata.s3.amazonaws.com/PMC5294554.1/PMC5294554.1.pdf). CC BY-NC, NLM의 `is_historical_ocr=true` | `476854d97d19c7ba6697e804fc8c791e69d5f3b4554ad2f916273951d2d221a0`, 2,003,686 bytes, 4쪽 | 1쪽 본문 및 인쇄 596쪽, 2쪽 표 및 인쇄 597쪽 |
| Gould·Bowie, [The Determination of Bacterial Sensitivity to Antibiotics](https://pmc.ncbi.nlm.nih.gov/articles/PMC5274816/), 1952, PMC5274816.1 | [메타데이터](https://pmc-oa-opendata.s3.amazonaws.com/PMC5274816.1/PMC5274816.1.json), [PDF](https://pmc-oa-opendata.s3.amazonaws.com/PMC5274816.1/PMC5274816.1.pdf). CC BY-NC, `is_historical_ocr=true` | `192718925c2eb4197971364e6a2764674f7e32e30080eb911e0d965e59337691`, 10,374,569 bytes, 22쪽 | 1쪽 본문 및 인쇄 178쪽, 3쪽 표 및 인쇄 180쪽 |
| Tan·Le, [EfficientNet](https://arxiv.org/abs/1905.11946v5), v5 | arXiv 공개 열람 | `af6b1bd620f81bfaea81edf8227484588e1fcc2427d6b5020fa17454d7566c70`, 933,600 bytes, 11쪽 | 1쪽의 2단 본문과 그림 |
| Devlin 외, [BERT](https://arxiv.org/abs/1810.04805v2), v2 | arXiv 공개 열람 | `5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e`, 775,166 bytes, 16쪽 | 1쪽의 2단 본문 |
| Goodfellow 외, [Generative Adversarial Networks](https://arxiv.org/abs/1406.2661v1), v1 | arXiv 공개 열람 | `ff5819e3a7b713c3bd3107b7de3d51fe0a347aa5d8444f0efdcf2345ef0a8b63`, 530,482 bytes, 9쪽 | 3쪽 수식 (1)과 그림 |
| Longhi, [Virtual Atom-Photon Bound States and Spontaneous Emission Control](https://arxiv.org/abs/2504.21754v1), v1 | 이전 대조 자료를 동일 파일로 다시 비교 | `b441def20f2b95b2b2368b797565f743cad363bad23d69a24c74f78d9e8c0d04`, 2,802,093 bytes, 6쪽 | 2쪽의 2단·수식 |
| Meuschke 외, [A Benchmark of PDF Information Extraction Tools](https://arxiv.org/abs/2303.09957v1), v1 | 이전 대조 자료, CC BY 4.0 | `cdae51b920dbe4f4c776e586115349af318114a3ede190443a6f0a2495265eae`, 1,007,833 bytes, 23쪽 | 3쪽 Table 1 |

arXiv의 [비독점 배포 허락](https://arxiv.org/licenses/nonexclusive-distrib/1.0/)은 arXiv에 부여한 허락이며 이를 제3자 재배포 권리로 가정하지 않았다. 두 스캔의 PDF와 메타데이터는 NIH NLM NCBI PubMed Central Article Datasets의 공개 자료를 사용했다. 페이지 번호는 PDF 앞에서부터 세는 물리 페이지이며, 인쇄 페이지와 같다고 가정하지 않는다.

세 기록을 합치면 **서로 다른 연구 논문 11편을 추출**했고, 그중 **10편은 적어도 한 페이지를 원문 렌더링으로 대조**했다. U-Net은 전체 추출만 했고 개별 원문 대조는 아직 없다. 이전의 역사 학술지 소식 `Notes`는 연구 논문 수에서 제외했다. 10~20편이라는 숫자 범위에는 들어오지만 2개 스캔은 같은 저널에서 왔고, 대다수가 영어 컴퓨터 과학 논문이므로 다양한 출판사·언어를 대표하지 않는다. 각 논문의 전 페이지를 육안 확인한 것도 아니다.

## 동일 자료에서 추출과 검색 비교

`inspect_pdf`의 pypdf 5.3.1과 pdfplumber 0.11.9의 기본 `extract_text()` 결과를 각 페이지에 대해 생성한 뒤 두 결과에 같은 `locate_quote`를 적용했다. pdfplumber는 평가용으로만 사용했으며 앱 기본 추출기를 바꾸지 않았다. `candidate`는 추출 문자열의 유일한 문구 후보이고, `possible_line_hyphenation`은 줄 끝의 하이픈을 빼면 가능한 후보이므로 실제 복합어인지 원문 대조가 필요하다. 어느 결과도 원문 좌표나 의미상 검증이 아니다.

| 표본 | 확인 대상 | pypdf | pdfplumber | 원문과 비교한 관찰 |
|---|---|---|---|---|
| Basu 1쪽 | `xanthomatosis, nephrotic syndrome` | possible_line_hyphenation | possible_line_hyphenation | 인쇄 원문에서는 첫 단어가 행 끝 하이픈으로 나뉜다. |
| Basu 1쪽 | `195 ±25` | not_found | not_found | 인쇄물의 `±`가 두 추출기의 기존 OCR 텍스트에서는 `?`로 나온다. |
| Gould 1쪽 | `preliminary bacteriological reports` | possible_line_hyphenation | possible_line_hyphenation | 원문의 첫 단어가 두 줄로 나뉜다. |
| Gould 3쪽 | `37° C.` | not_found | not_found | 원문의 도 기호가 기존 OCR에서 숫자 0으로 나와 `370 C.`가 된다. |
| Longhi 1쪽 | 초록의 `photonic environment and collective atom interactions` | possible_line_hyphenation | not_found | pypdf의 `environ-` 줄바꿈을 후보로 찾았고, pdfplumber의 기본 결과는 해당 본문에서 공백이 빠진다. |
| Longhi 2쪽 | `where we have set` | candidate | not_found | pypdf에서는 왼쪽 단에 있었지만, pdfplumber 기본 결과는 공백을 생략하고 오른쪽 단과 줄 단위로 섞었다. |
| Meuschke 3쪽 | Table 1의 Mao 행 | candidate | not_found | pypdf는 검사한 한 행의 문자열을 찾았지만, pdfplumber는 줄이 바뀐 셀과 같은 행의 데이터가 다른 순서로 나온다. 어느 쪽도 표 구조 전체가 복원된 것은 아니다. |
| Meuschke 3쪽 | Table 1의 Palermo 행 | candidate | candidate | 두 추출기의 단일 행 사례에서 검색됐다. |
| EfficientNet 1쪽 | 초록에서 `resolution`이 줄 끝에서 나뉜 문구 | possible_line_hyphenation | not_found | pypdf에서 대안 후보 하나를 찾았으며 pdfplumber 기본 결과는 해당 문구를 찾지 못했다. |
| BERT 1쪽 | 초록의 양쪽 문맥을 언급하는 문구 | candidate | not_found | pdfplumber 기본 결과는 양쪽 단을 섞고 일부 단어 사이 공백을 삭제했다. |
| GAN 3쪽 | `two-player minimax game` | candidate | not_found | pdfplumber 기본 결과는 해당 문구의 단어 사이 공백을 생략했다. |

표의 줄 끝 하이픈 후보와 Longhi·Meuschke·EfficientNet·BERT·GAN의 `candidate` 표본은 pypdf의 해당 논문 전체 페이지에서 검색했을 때 표시한 물리 페이지 한 곳에서만 나왔다. 전체 페이지를 실제 원문과 대조한 것이 아니라 **선택된 문구를 전체 추출 문자열에서 검색**한 결과다.

### 스캔과 표·수식에 대한 관찰

- Basu 2쪽 Table Ia에는 다수의 숫자 셀과 열 제목이 원문에 보이지만, 두 추출기 모두 기존 OCR 층에서 표의 숫자와 관계 일부를 얻지 못했다. 이 파일의 Table Ib도 OCR 문자와 숫자가 섞였으므로 두 추출기의 문자열만으로 표 전체를 복원할 수 없었다.
- Gould 3쪽 Table II의 원문은 약물별 다섯 열과 값이 대응한다. 기존 OCR의 단위와 기호가 잘못 읽혔고, pdfplumber는 열 제목과 값을 각각 한 줄로 만들었다. 선명한 인쇄물이라도 정확한 OCR이나 행·열 관계를 보장하지 않는다.
- 이 두 결과는 **원본 PDF에 이미 포함된 OCR 텍스트를 읽은 결과**다. 이번 평가에서 OCR을 새로 수행하지 않았고, 새 OCR 엔진의 인식률을 측정하지 않았다. 이전 실험에서 확인한 Windows 영어 OCR 언어 미설치 문제도 별도의 결과다.
- GAN 3쪽 식 (1)은 원문에서 위·아래 첨자와 기대값 기호의 2차원 관계를 갖는다. 두 추출기의 선형 문자열은 그 배치 관계를 잃는다. Longhi 2쪽도 그림 설명이 본문 흐름에 들어가거나 두 단이 섞여 표시되므로 수식과 읽기 순서를 자동으로 확정하면 안 된다.
- Poppler 렌더링은 EfficientNet과 BERT에서 `Symbol`, `ArialUnicode` 대체 글꼴 부재를 알렸고, GAN에서 `No current point in closepath`를 출력했다. 화면 비교는 해당 렌더링에 한정되며 모든 기호의 모양이 정확하다는 보장은 없다.

## 전체 추출 경과 시간

각 PDF에 대해 3회 실행한 경과 시간의 중앙값이다. pypdf 쪽은 앱의 `inspect_pdf` 전체 실행으로 해시와 이미지 리소스 검사 등을 포함하고, pdfplumber는 문서를 열어 모든 페이지의 기본 텍스트를 읽는다. 서로 하는 일이 같지 않고 Python 환경도 다르므로 공정한 엔진 속도 비교가 아니다. 시간은 해당 컴퓨터의 단순 관찰치이며 메모리와 CPU 사용량은 측정하지 않았다.

| 자료 | pypdf 5.3.1 앱 경로 | pdfplumber 0.11.9 기본 텍스트 |
|---|---:|---:|
| Basu | 0.103초 | 0.265초 |
| Gould | 0.409초 | 1.274초 |
| Longhi | 0.328초 | 0.744초 |
| Meuschke | 0.434초 | 1.421초 |
| EfficientNet | 0.376초 | 1.359초 |
| BERT | 0.580초 | 1.718초 |
| GAN | 0.268초 | 1.157초 |

## 재현 방법과 남은 한계

위의 정확한 PDF 버전을 직접 확보하고 SHA-256을 확인한다. API 디렉터리를 Python 경로에 넣은 뒤 `from app.pdf_processing import inspect_pdf, locate_quote`로 앱의 검사와 페이지 문구 검색을 실행한다. 비교할 때 `pdfplumber.open(path)`의 각 `page.extract_text()` 결과에 동일한 `locate_quote`를 적용한다. 페이지 그림은 `pdftoppm -f <물리쪽> -l <물리쪽> -scale-to 1800 -png -singlefile <PDF> <출력>`으로 렌더링한다. 표본 문구와 기대 상태는 위 표를 기준으로 확인한다. 시간은 `time.perf_counter()`로 전체 파일 열기와 모든 페이지 추출을 감싸 3회 측정했다.

이번 결과만으로 추출기를 교체하지 않는다. 문서별 공백·단 순서와 OCR 품질이 다르고, 기본 텍스트 추출만으로 표 셀과 수식의 관계를 보장하지 못했다. 실제 스캔에 대한 별도 OCR 재인식, 영어 외 언어, 회전·CropBox·정확한 화면 좌표, 메모리와 독립된 성능 벤치마크, 더 넓은 출판사 표본은 남아 있다. 향후 대안 비교는 동일한 전처리와 동일 조건으로 수행하고 원본 및 사용자 기록을 보존해야 한다.
