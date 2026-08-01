# paper-english 프로젝트 지침

프로젝트명은 paper-english, 스킬명은 **nomoredasi** (디렉터리 `skills/nomoredasi/`, 트리거 별칭 `nmd`). senpi 등록: `~/.agents/skills/nomoredasi` 심링크 — 레포가 SSOT이므로 스킬 갱신은 레포 커밋만으로 등록본에 자동 반영된다 (cycle_delta.sh Step 0가 링크를 점검·복구).

Nature 71개 세부 분야 논문 원고를 해당 분야 학술 영어 관행에 맞게 교정하는 Agent Skill을 만드는 프로젝트.

## 핵심 참조 문서

- `work_log.html` — 워크로그 인덱스 (최신순). 프로젝트 목표·설계 결정·다음 작업은 최신 일자 로그 참조.
- `work_logs/YYYY-MM-DD.html` — 일자별 워크로그.
- `paper-english-skill-analysis.html` — 실측 근거 분석 보고서.
- 코퍼스: `~/Documents/papers/<분야>/` (71개 분야 폴터, 매일 11:00-15:00 KST 업데이트).

## 워크로그 규칙

작업한 날은 `work_logs/YYYY-MM-DD.html`을 작성하고 `work_log.html` 인덱스 맨 위에 1-2줄 요약 + 링크를 추가한다 (최신순). 문서는 HTML 기본, 지침 파일만 Markdown.

## 라이선스 정책

스킬 업데이트(채굴·오버레이·레지스트리·골든 테스트)에는 **CC BY 4.0 라이선스 논문만** 사용한다. CC BY-NC 계열(NC·NC-ND·NC-SA)은 수집단에서 배제하며, 코퍼스에서 발견될 경우 **`build_attributions.py --quarantine`이 원본을 `~/Documents/papers-quarantine/`으로 격리**하고 status를 quarantined로 기록한다. 2026-08-01에 NC-ND 103편을 제거해 현재 코퍼스는 전부 CC BY 4.0이다. 논문별 출처·라이선스 레지스트리는 `docs/attributions.json`(SSOT) + `docs/ATTRIBUTIONS.md`(공개용) + `docs/attributions.html`(뷰)로 관리하며, `build_attributions.py`가 매 사이클 자동 재생성한다(템플릿 원본은 `docs/templates/`).

## 성숙도 점수 (readiness)

`scripts/readiness.py`가 분야별 준비도 점수(0-100: 편수·단어수·연어 깊이·섹션 커버리지·용어 안정성 가중합)를 계산해 `logs/readiness.jsonl` 시계열로 기록한다. 매 사이클 Step 4에서 실행되며, 점수-편수 곡선으로 "몇 편이면 쓸만한가"를 실측 분석하는 데 쓴다 (향후 다른 언어·분야 스킬에도 재사용).

## 주 2회 델타 분석 사이클 (1차 목표)

매주 월·목 16:00 KST에 `bash scripts/cycle_delta.sh`로 다음 7단계를 실행한다.

0. 프리플라이트: `.venv` Python과 코퍼스 읽기 권한을 확인하고 세션 재시작 후 스케줄러 재무장을 안내한다.
1. 델타 인벤토리: 코퍼스 매니페스트 diff를 `logs/cycle/<date>-delta.txt`에 기록한다.
2. 채굴: 전체 코퍼스에서 오버레이와 약어 레지스트리를 재생성한다.
3. 검증: unittest와 golden runner가 모두 통과해야 다음 단계로 진행한다.
4. diff 검토: references diff 통계와 레지스트리 상태 수를 `logs/cycle/<date>-diff.txt`에 기록한다.
5. 정책 커밋: 검증 및 데이터 안전 조건이 충족되고 실제 데이터 diff가 있을 때만 허용 경로를 자동 커밋한다. diff가 없으면 no-op으로 끝낸다.
6. 워크로그: `work_logs/<date>.html` 작성 여부를 확인하고 누락 시 작성을 안내한다.

## 작업 방식

- 서브에이전트 병렬 활용을 적극 권장. 단순·저비중 작업은 저렴한 모델(quick 카테고리 = luna)로 라우팅.
- 코퍼스 텍스트 추출에는 `pdftotext`(poppler) 필요 — 미설치 시 `brew install poppler`.

## 버전 관리

로컬 git 레포 사용. 사이클 자동커밋은 데이터 경로(`skills/nomoredasi/references/overlays/`, `skills/nomoredasi/references/abbrev-registry.json`, `skills/nomoredasi/references/abbrev-registry.html`, `docs/ATTRIBUTIONS.md`, `docs/attributions.json`, `docs/attributions.html`, `logs/`)에 한정하며 diff가 있을 때만 수행한다. 규칙 파일(`SKILL.md`, `references/core/`, `tests/golden/`, `AGENTS.md`)은 사람만 커밋한다. GitHub 원격은 추후 연결 예정.
