# paper-english 프로젝트 지침

Nature 71개 세부 분야 논문 원고를 해당 분야 학술 영어 관행에 맞게 교정하는 Agent Skill을 만드는 프로젝트.

## 핵심 참조 문서

- `work_log.html` — 워크로그 인덱스 (최신순). 프로젝트 목표·설계 결정·다음 작업은 최신 일자 로그 참조.
- `work_logs/YYYY-MM-DD.html` — 일자별 워크로그.
- `paper-english-skill-analysis.html` — 실측 근거 분석 보고서.
- 코퍼스: `~/Documents/papers/<분야>/` (71개 분야 폴터, 매일 11:00-15:00 KST 업데이트).

## 워크로그 규칙

작업한 날은 `work_logs/YYYY-MM-DD.html`을 작성하고 `work_log.html` 인덱스 맨 위에 1-2줄 요약 + 링크를 추가한다 (최신순). 문서는 HTML 기본, 지침 파일만 Markdown.

## 주 2회 델타 분석 사이클 (1차 목표)

매주 월·목 15:30 KST에 신규 PDF 델타 분석 → 오버레이/코어 개선 → git 커밋을 수행한다.

- 이 세션(상시 가동)에 인-세션 스케줄러를 monitor로 띄워 둔다.
- **세션 재시작 등으로 스케줄러가 없으면, 이 지침을 읽은 세션이 즉시 재무장한다.** 명령은 work_logs/ 최신 로그의 "결정 6" 또는 사용자에게 문의.
- 실행 내용: 전 주기 이후 `~/Documents/papers/`에 추가된 PDF를 분야별로 분석해 용어·연어·문체 지표를 갱신하고, 스킬 오버레이를 개선한 뒤 커밋.

## 작업 방식

- 서브에이전트 병렬 활용을 적극 권장. 단순·저비중 작업은 저렴한 모델(quick 카테고리 = luna)로 라우팅.
- 코퍼스 텍스트 추출에는 `pdftotext`(poppler) 필요 — 미설치 시 `brew install poppler`.

## 버전 관리

로컬 git 레포 사용. 커밋은 사용자가 명시 요청한 경우에만. GitHub 원격은 추후 연결 예정.
