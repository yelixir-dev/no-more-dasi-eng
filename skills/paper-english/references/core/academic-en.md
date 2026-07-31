# Academic English Core Rules (분야 공통)

Field-agnostic proofreading rules for Nature-family manuscripts. Every rule here is a checkable specification, not advice. Target register is the measured published corpus, not style-blog opinion.

## 0. Measured target register (근거 수치)

From the published corpus (23 papers, optics 125,125 words / non-optics 83,161 words):

| Metric | Optics | Non-optics |
|---|---|---|
| Avg sentence length (words) | 18.3 | 16.5 |
| Passive voice per 10K words | 111.1 | 137.3 |
| First-person "we" per 10K words | 17.6 | 22.5 |
| furthermore / moreover / in addition per 10K | 2.7 / 1.7 / 1.8 | 1.3 / 1.8 / 2.0 |

Corrections must move a draft toward this register, never toward a simplified-English register.

## 1. Anti-rule: ASD-STE100 constraints MUST NOT be applied

The following simplified-English rules are forbidden in this skill:

- Do NOT force active voice. Published rate is 111-137 passives per 10K words; passive is the academic standard, especially in Methods.
- Do NOT cap sentences at 20 words. The published mean is 16.5-18.3 words, and complex sentences are normal. Flag only sentences over 45 words for a readability check.
- Do NOT ban gerunds, participial phrases, or -ing forms.
- Do NOT ban hedging modals (may, might, could, should). They are required for calibrated claims (see §6).
- Do NOT delete first-person "we". Published rate is 17.6-22.5 per 10K words; "we demonstrate/report" is accepted practice.

A draft corrected under STE100-style rules reads as non-academic to reviewers. Treat any rule that conflicts with §0 measurements as invalid.

## 2. Articles with technical nouns (관사)

Korean has no articles, so this is the highest-frequency error class.

- R2.1 A singular countable noun must not appear bare. Check every singular countable noun: it needs "a/an", "the", a possessive, or a demonstrative.
- R2.2 Use "a/an" for first mention of a non-unique instance: "A thin film was deposited." Use "the" when the referent is defined by context or a modifier: "the film deposited at 300 °C", "the transmittance of the film".
- R2.3 Named methods and instruments take "the" when used as nouns: "the XRD pattern", "the finite-difference time-domain method". Acronyms read as letters take "an" by sound: "an SEM image", "an XRD peak".
- R2.4 Uncountable technical nouns take no indefinite article: "evidence", "equipment", "information", "progress", "research". Never "an evidence" or "researches".
- R2.5 Unit symbols and symbols (n, k, λ) never take articles: "the refractive index n was 2.1", not "the n".

## 3. Tense by section (섹션별 시제)

Section-aware correction is mandatory; the tense conventions differ per section.

- R3.1 Abstract: present tense for the problem and conclusions ("X is a limiting factor"), past tense for what was done ("films were fabricated", "we measured").
- R3.2 Introduction: present tense for established knowledge and the current problem ("Perovskites exhibit..."), present perfect or past for prior specific studies ("Kim et al. reported", "has been demonstrated").
- R3.3 Methods: past tense, passive dominant. "The films were deposited by RF sputtering." Present only for standard facts ("XRD is a standard technique for...").
- R3.4 Results: past tense for observations ("The transmittance increased", "we observed a shift"). Present tense for figure references and statements about the data as presented: "Figure 2 shows", "Table 1 lists".
- R3.5 Discussion: present tense for interpretation and general claims ("These results indicate that...", "The enhancement arises from..."). Past tense only when referring back to the specific experiment.
- R3.6 Lintable check: flag any Methods sentence in present tense describing the authors' own procedure, and any Results figure-reference sentence in past tense ("Figure 2 showed" -> "Figure 2 shows").

## 4. Passive vs active balance (수동태 균형)

- R4.1 Never convert passive to active as a blanket rule. Convert only when the passive hides the agent and the agent matters ("It is believed that..." -> "We believe that..." if the authors mean it).
- R4.2 Never convert active to passive to sound "objective". First-person active is standard for claims of novelty: "we demonstrate", "we report".
- R4.3 Default pattern per section: Methods, passive past. Results, mixed. Introduction/Discussion, active present with "we" or inanimate subjects ("This result suggests...").
- R4.4 Flag stacked agentless passives in one sentence ("was measured and was found to be shown"): rewrite one clause actively.

## 5. Subject-verb agreement (수 일치)

- R5.1 The verb agrees with the head noun, not the nearest noun: "The range of wavelengths is", "A series of measurements was".
- R5.2 "Data" takes plural in Nature-family register ("data show", "data were collected"). "None" may take either; keep the author's choice consistent within the manuscript.
- R5.3 Mass nouns are singular: "equipment is", "information is", "research shows".
- R5.4 Quantities take singular verbs: "5 mM was added", "200 nm was sufficient". Percents follow the noun: "50% of the films were", "50% of the film was".

## 6. Transition adverbs and hedging (전이부사와 헤징)

- R6.1 Do not delete furthermore/moreover/in addition on sight. Published rates are 1.3-2.7 per 10K words each; removal below that range is overcorrection. Flag only clusters: more than one per paragraph, or two sentences in a row opening with a transition adverb.
- R6.2 Hedge calibration: claims about mechanism or causation must carry a hedge ("suggests", "indicates", "is attributed to", "may arise from"). Reserve "demonstrates" and "proves" for direct measurements. Flag "This proves that" outside mathematics.
- R6.3 Do not stack hedges: "may possibly suggest" -> pick one.
- R6.4 "However" mid-sentence is fine; do not relocate it to sentence start mechanically.

## 8. Macro-structure and per-section rhetoric (구조와 전개)

Journals vary, but the macro-structure is always a selection from: Abstract / Introduction / Body(Methods) / Results / Conclusion. Merged variants are normal: Results+Discussion (Nat. Commun. style), Body+Results, Conclusion+Outlook. Never treat a merged or reordered structure as an error, and never "normalize" it to textbook IMRaD.

Per-section role and pacing (호흡):

- R8.1 Abstract: one-paragraph arc — problem, gap, what was done, key result with numbers, implication. No citations, no unexplained acronyms.
- R8.2 Introduction: funnel — field context -> specific problem -> gap -> what this work does ("Here, we..."). Ends with the contribution, optionally a one-line result preview. It must NOT contain a full conclusion: no outcome evaluation, no "in conclusion", no summary of implications beyond the preview line.
- R8.3 Methods: chronological/procedural blocks with topic sentences per technique. No results, no justification rhetoric beyond one clause ("to minimize scattering").
- R8.4 Results: evidence blocks ordered by question, figure-anchored ("Figure 2 shows..."). Reports what the data show, not why it matters — interpretation belongs to Discussion.
- R8.5 Discussion: claim-evidence-limitation arc. Interprets, compares with literature, states limitations. Must not introduce new measurements.
- R8.6 Conclusion: restates the advance and its significance, forward-looking. Must not cite new evidence or repeat Results numbers beyond the headline one.
- R8.7 Merged sections: in Results+Discussion, each evidence block carries its own local interpretation; do not split it into two sections, and do not force global interpretation paragraphs into a Results-only manuscript.

Cross-section contamination checks (lintable): flag conclusion markers ("in conclusion", "in summary", "these findings demonstrate the potential") inside Introduction; flag literature-comparison and hedged interpretation sentences ("this may indicate") inside Results; flag new quantitative results first appearing inside Conclusion.

## 9. Partial-section requests (부분 윤문)

When the user asks to correct only one section (e.g., "서론만", "Methods만"):

- R9.1 Scope lock: edit only the requested span. Do not touch, restructure, or "fix cross-references" in other sections.
- R9.2 Preserve the section's role per §8. An Introduction stays an Introduction: never append concluding sentences, a mini-abstract, or a roadmap paragraph the author did not write. A Methods section must not gain results.
- R9.3 Keep forward/backward references intact ("as shown in Section 3", "Figure 4"): do not renumber or delete them, but flag dangling ones to the user as a note, not an edit.
- R9.4 Apply only the rules valid for that section (tense table §3, role rules §8) plus the field overlay. Rules tied to absent sections do not apply.
- R9.5 Run the same verification gates on the edited span: verify_integrity.py against the original span, check_terms.py on the output span.

## 10. Change discipline

All corrections preserve numbers, units, error ranges, chemical formulas, symbols, and citations token-for-token. Detected spans only are edited; undetected paragraphs stay unchanged. Change rate above 30% of tokens triggers a warning; above 50% the run stops.
