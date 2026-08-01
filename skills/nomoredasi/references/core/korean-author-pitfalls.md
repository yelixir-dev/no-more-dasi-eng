# Korean-Author Pitfalls (한국어 화자 오류 사전), 초판

Status: 초판 (initial edition). This dictionary grows from accumulated user draft-vs-corrected diffs, proofreading literature, and public language-editing examples. The published corpus is a set of correct answers only; it cannot supply error distributions. Add each new entry with the same four fields: Korean pattern, wrong English, corrected pattern, before/after example.

## P1. "~를 통해(서)" -> overused "through" (경유 표현)

- Korean pattern: "실험을 통해 확인했다", "X를 통해 Y를 얻었다". Korean marks means/instrument with 를 통해, and literal translation dumps "through" everywhere.
- Wrong English: "Through the experiment, we confirmed..." / "We obtained Y through X."
- Corrected pattern: use the verb or a precise preposition. "The experiment confirmed..." / "We obtained Y by X" / "using X" / "with X". Pick by semantics: method = "by + gerund", tool = "using/with", causal route = "via" (sparingly).
- Before: "Through thermal annealing, the crystallinity was improved."
- After: "Thermal annealing improved the crystallinity." or "The crystallinity improved after thermal annealing."
- Checkable rule: flag "through" used as sentence opener or more than once per paragraph.

## P2. "~에 의해" -> stacked "by"-phrases (수동태 by 중첩)

- Korean pattern: "A는 B에 의해 영향을 받는다", "X에 의해 측정된 Y에 의해 결정된다". Korean chains 의해 freely; English cannot stack agents.
- Wrong English: "The transmittance of the thin film is greatly influenced by the deposition conditions."
- Corrected pattern: invert to active with the agent as subject, or use "depend on / correlate with / be governed by" once. Never two "by"-agents in one clause.
- Before: "The bandgap is affected by the oxygen partial pressure by changing the defect density."
- After: "The oxygen partial pressure changes the defect density and thereby shifts the bandgap." / "The bandgap depends on the oxygen partial pressure through the defect density."
- Checkable rule: flag any clause with two or more agentive "by"-phrases; flag "is influenced/affected by" when the agent is concrete (prefer active).

## P3. Topic-prominent subject drop (주어 생략)

- Korean pattern: Korean drops recoverable subjects: "측정한 결과, 증가함을 확인했다." Literal translation leaves English without a subject or with a dummy "it".
- Wrong English: "As a result of measurement, it was confirmed that the value increased." / "Was measured at room temperature."
- Corrected pattern: supply the subject. Prefer the measured entity or "we": "The value increased, as confirmed by measurement." / "We measured the films at room temperature." / "The films were measured at room temperature."
- Before: "After annealing, was confirmed by XRD."
- After: "After annealing, the crystallinity was confirmed by XRD." or "We confirmed the crystallinity by XRD after annealing."
- Checkable rule: flag finite verbs with no subject; flag "it was confirmed/found that" where the confirming agent is the authors.

## P4. Over-nominalization (명사화 과잉)

- Korean pattern: Korean noun-endings (~함, ~적, ~화) translate as heavy English nominalizations: "the improvement of the crystallinity", "the realization of high mobility".
- Wrong English: "The improvement of the crystallinity was achieved by the optimization of the annealing temperature."
- Corrected pattern: convert the key nominalization back to a verb. Keep at most one nominalization per clause.
- Before: "An enhancement of the transmittance was observed through the reduction of the surface roughness."
- After: "Reducing the surface roughness enhanced the transmittance." / "The transmittance increased as the surface roughness decreased."
- Checkable rule: flag "the X of the Y was achieved/observed/performed" frames; rewrite with X or Y as verb.

## P5. Article omission (관사 생략)

- Korean pattern: Korean has no articles, so drafts omit "a/the" before singular count nouns: "Film was deposited on glass substrate."
- Wrong English: "Film was deposited on glass substrate by sputtering method."
- Corrected pattern: every singular countable noun takes a determiner. First mention "a/an", given or uniquely specified "the": "A film was deposited on a glass substrate by sputtering." Subsequent mentions: "the film", "the substrate".
- Before: "Refractive index of film was measured by ellipsometer."
- After: "The refractive index of the film was measured by ellipsometry." (or "an ellipsometer" if the instrument matters).
- Checkable rule: scan for bare singular count nouns at subject and object positions; common victims: film, sample, substrate, layer, device, peak, spectrum, measurement.

## P6. Plural and countability transfer (복수·불가산 오류)

- Korean pattern: Korean marks plurality optionally and has no count/mass distinction, producing wrong plurals and pluralized mass nouns.
- Wrong English: "We analyzed the data and obtained many informations." / "Various equipments were used." / "The refractive indexes was measured."
- Corrected pattern: mass nouns stay singular (data is plural by convention in Nature register: "data show"; but information, equipment, research, progress, evidence never pluralize). Count nouns pluralize and agree with the verb.
- Before: "Many researches have studied the optical properties of this materials."
- After: "Many studies have examined the optical properties of this material." (or "these materials" if several).
- Checkable rule: flag plural forms of information/equipment/research/evidence/progress; flag verb agreement after "data", "indexes/indices" (pick one plural form per manuscript and keep it consistent).

## Growth protocol (성장 규칙)

Each correction session that processes a user draft should append new entries mined from the draft-vs-corrected diff, in the P-number format above, with one before/after pair each. Patterns that recur in three or more sessions are promoted to checkable rules in academic-en.md.
