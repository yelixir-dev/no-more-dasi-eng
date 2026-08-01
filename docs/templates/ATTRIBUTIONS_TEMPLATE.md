<!--
MAINTAINER NOTE
1. Replace every [BRACKETED PLACEHOLDER].
2. Delete this comment and the "template notice" before public release.
3. Add one detailed entry for every article actually used.
4. Verify the license on the publisher's article page, PDF, or JATS/XML record.
5. Do not classify an article as CC BY 4.0 solely because of the journal name.
-->

# Third-Party Scientific Article Attributions  
## 제3자 학술논문 출처 및 라이선스

**Project:** [PROJECT NAME]  
**Repository:** [REPOSITORY URL]  
**Registry version:** 1.0  
**Last updated:** [YYYY-MM-DD]  
**Maintainer contact:** [EMAIL OR ISSUE URL]

> **Template notice:** This file is an example. All bracketed values must be replaced, and unused sections must be deleted before publication.

This registry identifies scholarly articles whose CC BY 4.0–licensed material was used in this project. It is intended to provide a durable, human-readable attribution record and to document how each article was processed.

---

## 1. Separation of licenses

The licenses applying to this repository are separated as follows:

- **Software source code:** [MIT / Apache-2.0 / GPL-3.0 / OTHER], as stated in [`LICENSE`](./LICENSE).
- **Project-authored documentation:** [DOCUMENTATION LICENSE OR “same as software”].
- **Third-party article material:** remains copyrighted by the respective authors or other identified rightsholders and is used under the **Creative Commons Attribution 4.0 International License (CC BY 4.0)** identified for each article below.
- **Model weights, indexes, embeddings, or generated assets:** [STATE THE APPLICABLE PROJECT LICENSE OR DISTRIBUTION TERMS].

The repository's software license does **not** replace, narrow, or relicense the CC BY 4.0 terms applying to the source articles.

No author, journal, publisher, or affiliated institution listed here endorses this project unless an explicit written statement says otherwise.

---

## 2. Scope of reuse

### Material that may be included

Select and edit this list to match the project:

- [ ] Full article text
- [ ] Abstracts
- [ ] Titles and bibliographic metadata
- [ ] Section headings
- [ ] Sentence or paragraph excerpts
- [ ] Tables or captions separately verified as covered by CC BY 4.0
- [ ] Supplementary material separately verified as covered by CC BY 4.0
- [ ] Derived linguistic features or writing-style statistics
- [ ] Embeddings or retrieval indexes
- [ ] Fine-tuning or evaluation examples
- [ ] Human-authored writing rules distilled from corpus analysis

### Standard processing and modifications

Select only the operations actually performed:

- [ ] HTML, PDF, or JATS/XML converted to plain text
- [ ] References, acknowledgements, author information, or boilerplate removed
- [ ] Figures, tables, equations, or captions removed
- [ ] Unicode, whitespace, punctuation, or hyphenation normalized
- [ ] Text segmented into sections, paragraphs, or sentences
- [ ] Text tagged, classified, scored, or annotated
- [ ] Text translated, summarized, paraphrased, or otherwise rewritten
- [ ] Errors inserted to create correction or evaluation pairs
- [ ] Embeddings, statistics, or model-training records generated
- [ ] Other: [DESCRIBE]

### Excluded by default

Unless separately verified and recorded, this project excludes:

- figures, photographs, maps, diagrams, or tables carrying a separate credit line;
- third-party quotations or excerpts that the article itself uses under permission or a legal exception;
- supplementary files whose license is not expressly verified;
- articles whose license is missing, ambiguous, or not exactly CC BY 4.0;
- retracted or withdrawn material, unless retained for a documented research purpose.

---

## 3. Attribution format used by this project

For every article, this registry records:

1. **Title**
2. **Author or other designated attribution party**
3. **Source**, preferably the DOI and the publisher's article page
4. **License**, including a link to CC BY 4.0
5. **Modification statement**, explaining whether and how the material was changed
6. **Project use**, such as style analysis, RAG, evaluation, examples, or fine-tuning
7. **License verification evidence and date**
8. **Third-party-material exclusions**, where relevant

A compact attribution may use this form:

> **“[ARTICLE TITLE]”** by **[FULL AUTHOR LIST OR PUBLISHER-SUPPLIED ATTRIBUTION]**, *[JOURNAL]* ([YEAR]), [DOI LINK]. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Used for [PROJECT PURPOSE]. Changes: [MODIFICATIONS, OR “none”].

For modified text shown to users, use an explicit form such as:

> Adapted from **“[ARTICLE TITLE]”** by **[AUTHORS]**, *[JOURNAL]* ([YEAR]), [DOI LINK], under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changes: [e.g., shortened, punctuation normalized, and intentionally edited to demonstrate a correction]. The original authors and publisher do not endorse this adaptation.

---

## 4. Article summary register

> Replace the template row below. For a large corpus, keep this summary compact and link each ID to a detailed entry or a machine-readable manifest.

| Record ID | Article | Journal / year | DOI or canonical source | License | Project use | License verified |
|---|---|---|---|---|---|---|
| `ART-0001` | [ARTICLE TITLE] | [JOURNAL], [YEAR] | [DOI OR PUBLISHER URL] | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | [STYLE ANALYSIS / RAG / TRAINING / EVALUATION / EXAMPLE] | [YYYY-MM-DD] |

---

## 5. Detailed article entries

### ART-0001 — [ARTICLE TITLE]

- **Authors / designated attribution parties:** [FULL AUTHOR LIST AS SUPPLIED]
- **Journal:** [JOURNAL]
- **Publication year:** [YEAR]
- **Volume, issue, article number, or pages:** [BIBLIOGRAPHIC DETAILS]
- **DOI:** [DOI]
- **Canonical source:** [PUBLISHER ARTICLE URL]
- **License:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- **Copyright notice supplied with the article:** [COPY EXACTLY, OR “No separate notice recorded”]
- **Publisher disclaimer or license notice:** [LINK OR SHORT IDENTIFIER]
- **License evidence:** [PUBLISHER HTML / PDF PAGE / JATS XML FIELD / OTHER]
- **License verified on:** [YYYY-MM-DD]
- **Material retrieved on:** [YYYY-MM-DD]
- **Project role:** [STYLE ANALYSIS / RAG / FINE-TUNING / EVALUATION / DOCUMENTATION EXAMPLE / OTHER]
- **Material used:** [FULL TEXT / SPECIFIC SECTIONS / SENTENCE EXCERPTS / METADATA / OTHER]
- **Modifications and processing:** [DETAILED DESCRIPTION]
- **User-visible exposure:** [NONE / SOURCE PASSAGES DISPLAYED WITH CITATION / MODIFIED EXAMPLES DISPLAYED / OTHER]
- **Excluded third-party material:** [FIGURES 1–3 / TABLE 2 / ALL IMAGES / NONE IDENTIFIED / OTHER]
- **Local corpus or manifest record:** [PATH, HASH, OR DATABASE ID]
- **Removal or correction status:** [ACTIVE / REMOVED / CORRECTED; DATE AND REASON]
- **Notes:** [OPTIONAL]

**Copy-ready attribution**

> **“[ARTICLE TITLE]”** by **[AUTHORS]**, *[JOURNAL]* ([YEAR]), [DOI LINK]. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Used in [PROJECT NAME] for [PURPOSE]. Changes: [MODIFICATIONS]. [THIRD-PARTY MATERIAL EXCLUSION, IF NEEDED]. No endorsement is implied.

---

<!-- Duplicate the detailed-entry block above for ART-0002, ART-0003, and so on. -->

## 6. Attribution at the point of output

This repository-level registry is the central record. Where the software returns a recognizable source passage, substantial excerpt, or article-specific adaptation, the user interface should also provide a nearby attribution or source link.

Recommended compact output label:

> Source: [FIRST AUTHOR et al., “SHORT TITLE,” JOURNAL, YEAR, DOI] — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — [modified / unmodified].

For article-specific RAG output, link the displayed source to the corresponding record ID in this registry whenever practical.

---

## 7. Machine-readable manifest recommendation

For tens or hundreds of articles, maintain a canonical CSV, JSON, JSONL, or database table in addition to this human-readable file. Suggested fields:

```json
{
  "record_id": "ART-0001",
  "title": "[ARTICLE TITLE]",
  "authors": ["[AUTHOR 1]", "[AUTHOR 2]"],
  "journal": "[JOURNAL]",
  "publication_year": 2025,
  "doi": "[DOI]",
  "canonical_url": "[PUBLISHER URL]",
  "license_name": "CC BY 4.0",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "copyright_notice": "[NOTICE IF SUPPLIED]",
  "license_evidence_url": "[URL]",
  "license_verified_at": "2026-08-01",
  "retrieved_at": "2026-08-01",
  "project_uses": ["style-analysis", "evaluation"],
  "material_used": ["body-text"],
  "transformations": [
    "jats-to-text",
    "reference-removal",
    "unicode-normalization",
    "sentence-segmentation"
  ],
  "user_visible_exposure": "none",
  "excluded_material": ["all separately credited third-party material"],
  "source_hash": "[SHA-256 OR OTHER CONTENT HASH]",
  "status": "active"
}
```

The machine-readable manifest should be version-controlled. Any license correction, article withdrawal, or corpus removal should be recorded rather than silently overwritten.

---

## 8. Corrections and takedown requests

To report an incorrect attribution, license mismatch, author-name error, or third-party-rights concern, open an issue at [ISSUE URL] or contact [EMAIL].

When a record is corrected or removed, preserve a dated changelog entry showing:

- the affected record ID;
- the previous and corrected information;
- the reason for the change;
- whether related corpus files, indexes, examples, or model artifacts were also updated.

---

## 9. Reference guidance

This template follows the Creative Commons attribution practice commonly summarized as **TASL**—Title, Author, Source, and License—plus the CC BY 4.0 requirement to indicate modifications when material has been changed.

- CC BY 4.0 license summary: <https://creativecommons.org/licenses/by/4.0/>
- CC BY 4.0 legal code: <https://creativecommons.org/licenses/by/4.0/legalcode>
- Creative Commons recommended attribution practices: <https://wiki.creativecommons.org/wiki/Recommended_practices_for_attribution>

This registry is an operational attribution record, not legal advice.
