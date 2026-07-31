---
name: paper-english
version: "0.1.0"
description: 한국어/영어 논문 원고를 해당 분야(Nature 71개 세부 분야)의 학술 영어 관행에 맞게 교정·퇴고하는 스킬. 의미·수치·고유명사·인용 100% 보존, 분야별 오버레이(용어·연어·문체 파라미터) + 코어 규칙(시제·관사·레지스터) 적용, 결정적 검증 게이트 통과 시에만 납품. 트리거 — "논문 교정", "논문 영어 다듬어줘", "학술 영어 첨삭", "paper proofreading", "논문 윤문", "영어 논문 퇴고", "Nature 투고용으로 교정", "학회지 문체로", "번역투 없애줘 (논문)", "AI가 쓴 논문 초안 교정".
---

# paper-english — 분야 맞춤 학술 영어 교정 스킬 (v0.1)

논문 원고를 Nature 계열 학술지 투고 수준의 영어로 교정한다. 분야별 관행(단어선택·밀도·호흡·전개방식)은 `references/overlays/<분야>.md`가, 분야 공통 규칙은 `references/core/`가 담당한다.

## 4대 원칙 (모든 경로 공통, 위반 시 납품 금지)

1. **의미 불변** — 내용·주장·논리 순서를 바꾸지 않는다. 문체와 표현만 고친다.
2. **근거 기반** — 모든 교정은 `references/core/` 규칙 또는 해당 분야 오버레이의 코퍼스 실측에 근거한다. 직감으로 "AI 같은" 표현을 지우지 않는다.
3. **장르 유지** — 학술 논문 레지스터를 유지한다. 구어체화·에세이화 금지. **ASD-STE100식 규칙(능동태 강제·문장 20단어 상한·-ing 금지) 적용 금지** — 게재지 실측(수동태 111-137/10K, 평균 문장 16.5-18.3단어)과 충돌한다 (`references/core/academic-en.md` 참조).
4. **과윤문 금지** — 변경률 30% 초과 시 경고, 50% 초과 시 중단하고 사용자 확인. `scripts/verify_integrity.py`가 결정적으로 판정한다.

## Phase 0: 입력 유형 판별

작업 시작 시 한 줄 출력: `paper-english v0.1 — 유형 {A|B} / 분야: {확정된 분야}`

- **유형 A (한국어 원고)** — 번역+교정 복합 경로. `references/core/korean-author-pitfalls.md`의 번역투 유발 구조("~를 통해", "~에 의해" 등)를 먼저 탐지해 직역을 차단한 뒤 번역하고, 이후 유형 B와 동일한 3층 규칙을 적용한다.
- **유형 B (영어 원고, AI 초안 포함)** — 교정 경로. AI 초안 징후가 있으면 `references/core/ai-tell-en.md` 계층을 추가 적용한다.

## Phase 1: 분야 라우팅 (3단 우선순위)

1. **사용자 명시** — 사용자가 분야를 말하면 그대로 사용.
2. **폴터명** — 원고 파일이 `papers/<분야>/` 등 분야명 폴터에 있으면 사용.
3. **자동감지** — `scripts/route_field.py <원고>` 실행, 상위 결과 사용. 상위 2개 점수가 근접하면 두 오버레이를 병합 적용.
4. **불명확 시 1회 확인** — 열린 질문 금지. "Optics and photonics로 보입니다. 맞으면 진행합니다" 형태로 추정값을 제시하고 한 번만 묻는다.

분야가 틀려도 코어 규칙은 분야 무관하게 동작하므로 안전하다. 오버레이 파일이 없는 분야면 코어 규칙만으로 진행하고 그 사실을 고지한다. 오버레이 헤더의 `Maturity:`가 `immature`면(파일 <10편 또는 <100K 단어) 그 수치는 하드 타겟이 아니라 방향 참고치로만 쓴다.

## Phase 1.5: 원고 상태 파일 (manuscript.json)

원고 폴터에 `manuscript.json`이 있으면 읽고 반영한다 — 약어 정의 목록, 확정된 용어 표기(예: bandgap), 도표 목록. 부분 윤문이나 반복 요청에서 문서 전체 일관성을 유지하는 장치다. 없으면 새로 만들지 않고 진행하되, 교정 납품 후 `scripts/manuscript_state.py learn <폴터> <교정본>`으로 그날의 결정(정의한 약어, 다수 표기)을 기록한다. 기존 값과 충돌하는 새 관측은 덮어쓰지 않고 사용자에게 보고한다.

## Phase 2: route_hint — 교정 강도 3경로

초안을 훑어 **light / standard / heavy** 중 하나로 결정하고 출력한다.

- **light (1패스)** — 이미 잘 쓴 원고(게재 수준 문체, 산발적 문법 오류만). 코어 규칙 위반만 고치고 끝. 변경률 하한.
- **standard (2패스)** — 일반적 케이스. 1패스: 코어 3층 규칙(① 일반 학술 영어 — 시제·관사·수 일치 ② 분야 용어 표기 통일 — 오버레이 Notation watch ③ 저널 레지스터). 2패스: 자체 검토 + 검증 스크립트.
- **heavy (3패스+)** — 번역투/AI-tell 다수, 구조적 어색함. 패스1: 유형별 전처리(pitfalls 또는 ai-tell). 패스2: 코어 3층 규칙. 패스3: 문단 흐름·전개 다듬기. 그 후 검증.

## Phase 3: 섹션 인식 교정

원고를 `scripts/section_split.py`로 나눠 인식한다 (IMRaD + Results and Discussion 병합, Experimental Section 등 변형 대응). 학회·논문집마다 구조는 다르지만 거시 구조는 요약/서론/본론/결과/결론의 선택이며, 병합형(Results+Discussion, 본론+결과)은 오류가 아니니 교정으로 "정규화"하지 않는다. 섹션별 시제·수동태 규칙과 전개·호흡 규칙은 `references/core/academic-en.md` §3·§8을 따른다.

- Methods = 과거·수동 우세 유지 (억지 능동화 금지)
- Results = 과거 중심, 도표 지시 현재. 해석 문장을 Results에 넣지 않는다
- Discussion/Conclusion = 해석은 현재 시제
- Abstract = 섹션 축약형, 시제 혼용 규칙 적용
- Introduction에는 결론 구조를 만들지 않는다 (§8 교차 오염 검사) — 서론에 "in conclusion" 류를 추가하는 것은 의미 불변 위반

### 부분 윤문 요청 ("서론만", "본론만")

사용자가 특정 섹션만 요청하면 **범위 잠금**: 요청한 구간만 고치고 다른 섹션은 건드리지 않는다. 그 섹션의 역할(§8)을 유지하고, 없는 섹션의 규칙은 적용하지 않으며, 교차 참조(“Section 3”, “Figure 4”)는 편집하지 않고 끊긴 참조만 노트로 보고한다. 검증 게이트도 그 구간 기준으로 실행한다 (`academic-en.md` §9).

## Phase 4: 검증 (코드 게이트 — LLM 자기판정 금지)

납품 전에 반드시 아래를 실행하고 결과를 보고한다:

1. `scripts/verify_integrity.py <원고> <교정본>` — 수치·단위·화학식·인용 보존 + 변경률 게이트. **exit 1이면 납품 금지**, 해당 위반을 수정하고 재실행.
2. `scripts/check_terms.py <교정본>` — 용어 표기 일관성 (bandgap/band gap 등). exit 1이면 다수형으로 통일 후 재실행.
3. `scripts/check_abbrev.py <교정본> [--state <폴터>]` — 미정의 약어 탐지. exit 1이면 최초 사용 시 정의를 추가하거나 manuscript.json과 대조. 미검증 약어(전개형을 모르는 약어)는 `scripts/abbrev_registry.py references/abbrev-registry.json record <ABBR> --field <분야> --context <문장>`으로 레지스트리에 기록한다. 이후 같은 분야 텍스트에서 같은 약어의 전개형이 관측되면(`scan`) 맥락 문장과 함께 verified로 갱신되고, 다른 전개형이 관측되면 conflict로 표시된다 — conflict는 사용자에게 확인을 요청한다. 사람용 뷰는 `references/abbrev-registry.html`(자동 재생성, 편집 금지; SSOT는 json).
4. 부분 윤문이면 위 검사들을 해당 구간 기준으로 실행한다.

## 품질 측정 (스킬 자체 개선용)

`scripts/bench_edit.py <원고> <교정본>` — 교정 전후 위반/100단어(AI-tell·중첩 헤징·과장 수식·도표 시제·장문·전이부사 과밀·표기 불일치)를 비교한다. 납품 게이트가 아니라 스킬 성능 측정 장치: 월/목 델타 사이클에서 golden 케이스와 실제 교정 로그에 적용해 위반율이 회귀(exit 1)하면 오버레이/규칙 변경을 되돌아본다.

## 참조 파일

- `references/core/academic-en.md` — 시제·관사·수동태 균형·전이부사·헤징 (분야 공통)
- `references/core/ai-tell-en.md` — 영어 AI 초안 탐지 패턴 (게재지 비출현 근거 포함)
- `references/core/korean-author-pitfalls.md` — 한국어 화자 오류 사전 (초판, diff 축적으로 성장)
- `references/overlays/<분야>.md` — 분야별 실측: 문체 지표·상위 용어·phrase bank·표기 감시 목록. `scripts/mine_corpus.py`가 `~/Documents/papers/<분야>/`에서 자동 생성, 주 2회 갱신.

## 하지 않는 것

- 내용 추가·삭제·재구성 (의미 불변 위반)
- ASD-STE100·Plain English 등 비학술 간소화 규칙 적용
- 분야를 모른 채 열린 질문으로 사용자에게 떠넘기기
- 검증 스크립트 없이 "확인했습니다"라고만 보고하기
