# English AI-Draft Tells (영어 AI 초안 탐지)

Phrases that appear in AI-drafted manuscripts but essentially never in published Nature-family papers. Detection target only: every flagged span still needs a human-style rewrite that preserves meaning, numbers, and citations.

## 0. Evidence rule (근거 기반 원칙)

A phrase is a tell ONLY if it is absent or near-absent from the published corpus. Frequencies below are measured per 10K words in the published corpus (23 papers).

- "plays a crucial role": 0.2/10K. Effective tell.
- "paves the way": 0.0/10K. Effective tell.

Caution: detection must be evidence-based. If a phrase occurs at normal rates in the published corpus, it is NOT a tell, even if it "sounds like AI". Do not flag phrases on intuition; check against the corpus first. The transition adverbs furthermore/moreover/in addition, for example, appear at 1.3-2.7/10K in published papers and must not be treated as AI markers.

## 1. Grandiose impact claims (과장된 중요성)

AI drafts inflate significance; published papers understate it.

- "plays a crucial role in" (0.2/10K) -> name the actual function: "X controls Y", "X determines the Z of...", "X is required for Y".
- "plays a pivotal/vital/key role" -> same treatment.
- "paves the way for" (0.0/10K) -> state the concrete next step: "enables", "allows", "provides a route to".
- "holds great promise for" -> replace with the specific capability: "achieves X at Y conditions".
- "is of paramount importance" -> delete and let the sentence state the fact.
- "a significant breakthrough" -> delete; significance is for reviewers to judge.

## 2. Empty framing and throat-clearing (빈 전이구)

- "In recent years, ... has attracted considerable/growing attention" -> open with the specific problem or prior result instead.
- "With the rapid development of" -> state the actual development and cite it.
- "It is well known that" -> state the fact with a citation, or delete the frame.
- "It is worth noting that" / "It should be noted that" -> delete the frame; keep the noted content.
- "In this study, we aim to" (Abstract) -> "we report", "we demonstrate" (both attested; "we demonstrate" 1.0/10K, "in this work" 1.8/10K are acceptable alternatives).

## 3. Over-hedging stacks (중첩 헤징)

AI drafts pile hedges; published papers use one calibrated hedge per claim.

- "may potentially" -> "may".
- "could possibly" -> "could" or "may".
- "it is possible that ... might" -> single modal.
- "appears to seem to" -> "appears to".
- Rule: flag any sentence with two or more hedging devices (modal + "possibly/potentially" + "suggest/appear") and reduce to one.

## 4. Formulaic summarizing (공식적 요약)

- "In conclusion" / "In summary, these findings demonstrate" -> published Discussion sections usually interpret directly; keep only if the journal section is literally "Conclusions" and the author used it once.
- "Overall, our results highlight the importance of" -> state the implication directly: "These results indicate that X limits Y."
- "Taken together" opening every Discussion paragraph -> flag if used more than once per manuscript.
- "This study not only ... but also" -> split into two factual sentences.

## 5. Decorative adverbs and intensifiers (수식 과잉)

- "remarkably", "strikingly", "notably" before every result -> flag more than one per Results section; replace with the number that makes it remarkable.
- "significantly" without a statistical test -> replace with the measured difference or add the test; reserve "significant" for p-value contexts.
- "greatly", "dramatically", "substantially enhanced" -> replace with the measured change ("increased from 62% to 85%").
- "excellent", "outstanding" describing the authors' own results -> delete; describe the metric instead.

## 6. Structural monotony signals (구조 단조로움)

These are pattern-level tells, not phrase-level:

- Every paragraph opens with a transition adverb (Moreover, Furthermore, Additionally in sequence). Published rate is 1.3-2.7/10K per adverb; flag densities above that.
- Triadic lists in every sentence ("X, Y, and Z" where items are near-synonyms) -> cut to the informative members.
- Uniform sentence length across a paragraph with no complex sentence. Published mean is 16.5-18.3 words with normal variation; flag paragraphs where all sentences fall within 10-14 words.

## 7. Non-tells: do not flag

Evidence-based detection means protecting attested usage. The following appear in the published corpus and are NOT AI tells:

- "we demonstrate", "we report", "in this work" (we: 17.6-22.5/10K).
- furthermore, moreover, in addition at moderate density.
- Passive constructions (111-137/10K are normal).
- "These results suggest/indicate that" (standard Discussion register).

When in doubt, measure the phrase against the corpus before flagging.
