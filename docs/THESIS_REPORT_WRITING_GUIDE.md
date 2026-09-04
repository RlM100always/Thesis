# Thesis report writing guide — LaTeX template + supervisor requirements

This file exists so the actual thesis-report writing (LaTeX prose) can be
picked up later without re-deriving these rules. It captures the mechanics
of the given DU LaTeX template and the supervisor's exact structural
requirements — it does **not** duplicate chapter *content* planning, which
already lives in [THESIS_PRODUCT_MASTER_PLAN.md](THESIS_PRODUCT_MASTER_PLAN.md).
Read that file for what goes in each chapter; read this file for how it maps
onto the LaTeX template and what format rules the supervisor imposed.

**The LaTeX template itself (main.tex, preamble.tex, Chapters/*.tex, etc.)
is not stored in this software repository** — it lives in a separate
LaTeX/Overleaf project. This guide only records the requirements so the
report can be written correctly whenever that's picked up.

## Execution order (stated by the user, keep this rule)

Write no thesis prose until the dynamic software and its real experiments
are in place. The Experimental Results chapter depends on numbers the
software must actually produce — writing it first would mean rewriting it
later or, worse, being tempted to fill it with placeholder numbers. Current
software status: see [CLAUDE.md](../CLAUDE.md) and
[FEATURE_STATUS.md](FEATURE_STATUS.md).

## 1. Template file map (from the template's own `help.txt`)

| Do this | In this file |
|---|---|
| Set the thesis title | `title.tex` |
| Comment out unused preamble packages/sections | `preamble.tex` |
| Fill declaration, funny quote, abstract, acknowledgement, abbreviations, physical constants, symbols, dedication | `Chapters/declaration.tex`, `Chapters/abstract.tex`, `Chapters/acknowledgement.tex`, and the corresponding blocks inside `preamble.tex` |
| Write the 6 main chapters | `Chapters/introduction.tex`, `Chapters/artoftheworks.tex`, `Chapters/proposedMethod.tex`, `Chapters/implementations.tex`, `Chapters/experimentalResults.tex`, `Chapters/conclusions.tex` |
| Add appendices | uncomment the `\appendix` block and `\input{Appendices/AppendixX}` lines in `main.tex`; each appendix is its own file |
| Add references | `Bibliography.bib` (BibTeX), cited via `\cite{}`, rendered with the `acm` bibliography style |
| Add figures | `Figures/` folder only, referenced via `\includegraphics{./Figures/...}` |

Package notes already in the template's `preamble.tex`: `algorithm2e` +
`algorithmicx` for pseudocode, `longtable`/`multirow` for wide tables,
`natbib` with `[square, numbers, comma, sort&compress]` for citations,
`hyperref` with `colorlinks=true`.

## 2. Chapter structure — reconciled with the template's actual files

The template's chapter files use these exact titles (do not rename them):

1. **Introduction** (`introduction.tex`) — 1.1 Motivations, 1.2 Objectives,
   1.3 Contributions, 1.4 Challenges, 1.5 Organization.
2. **Related Works** (`artoftheworks.tex`) — the template ships only one
   subsection, "2.1 Problem of Existing Systems", but the supervisor's own
   notes (see below) put three things inside this one chapter, in this
   order:
   - **Background study** — definitions and theory the reader needs (SME/
     CMSME, BI, RFM/CLV, forecasting, churn, segmentation, etc. — full list
     in `THESIS_PRODUCT_MASTER_PLAN.md` §6).
   - **Literature review** — minimum 20 papers now, 40+ in the final
     thesis; 3–4 lines per paper (problem, dataset/context, method, main
     result, limitation/relevance); distribution table and literature
     matrix as specified in `THESIS_PRODUCT_MASTER_PLAN.md` §6.
   - **2.1 Problem of Existing Systems** — the existing-system limitation
     table (already drafted in `THESIS_PRODUCT_MASTER_PLAN.md` §6).

   This supersedes an earlier draft of `THESIS_PRODUCT_MASTER_PLAN.md` that
   called this "Chapter 2 — Background and Related Work" as if separate from
   "existing-system limitations" — they are the same chapter, in the
   template's own naming ("Related Works"), just multiple subsections deep.
3. **Proposed Methodologies** (`proposedMethod.tex`) — research questions,
   data acquisition/ethics, database schema, preprocessing, model
   definitions, the B-SMART algorithm (pseudocode + complexity + worked
   example), architecture/data-flow/sequence diagrams, evaluation protocol.
4. **Implementation** (`implementations.tex`).
5. **Experimental Results** (`experimentalResults.tex`) — 5.1 Results
   Analysis, 5.2 Summary of the Experimental Results.
6. **Conclusions** (`conclusions.tex`) — 6.1 Research Summary, 6.2 Future
   Work Plan.

Front matter (already scaffolded by the template, fill in when ready):
Declaration → funny quote (optional) → Abstract → Acknowledgements →
List of Figures/Tables/Algorithms → Abbreviations → Physical Constants →
Symbols → Dedication.

## 3. Citation rules

- `\cite{paper_key}` for every citation, ACM numeric style (the template's
  `\bibliographystyle{acm}` / `natbib` with `[square, numbers, comma,
  sort&compress]`).
- `\ref{}` is reserved for figures, tables, sections, and equations —
  **never** use it for a citation.
- No sentence copied from a source; read, understand, then write an
  original synthesis (see academic-integrity rules already in
  `THESIS_PRODUCT_MASTER_PLAN.md` §10 — not repeated here).

## 4. Presentation / defence slide order

From the supervisor's handwritten planning notes, the slide sequence is:

1. Title page
2. Table of contents
3. **Result / system overview diagram** (comes right after ToC, before any
   motivation slide — earlier than where a typical proposal would put it)
4. Introduction: motivation → contribution → challenge
5. Background study
6. Literature review and its drawbacks
7. Proposed problem formulation / methodology
8. Next work
9. Publication reference

This is close to, but not identical in ordering to, the presentation
structure already drafted in `THESIS_PRODUCT_MASTER_PLAN.md` §8 (which puts
the system overview diagram later, after motivation/objectives/
contributions). **Follow the order above for the actual slide deck** — it's
the more recent, supervisor-specific instruction. Update
`THESIS_PRODUCT_MASTER_PLAN.md` §8 to match this before the next defence
prep if it hasn't been reconciled yet.

## 5. Scalability experiment — required table and graph format

The template's own `Appendices/appendices.tex` already ships a sample table
with exactly these columns:

| min-sup | lattice-time | rulegen-time |
|---|---|---|

and the handwritten notes specify the required graph: **x-axis = minimum
support** (test at 0.01, 0.02, 0.05, 0.10 per
`THESIS_PRODUCT_MASTER_PLAN.md` §7), **y-axis = runtime / memory / generated
rule count** (one curve per metric, or one graph per metric — report
whatever the experiment actually produces, never a pre-written expected
trend).

**Blocking dependency, flagged here on purpose:** this table and graph
describe a market-basket / association-rule mining algorithm (Apriori/
FP-Growth-family — "lattice-time" and "rulegen-time" are classic
association-rule-mining stage names). No such algorithm exists anywhere in
this codebase yet (confirmed by search — nothing under `ml/`, `api/`, or the
numbered pipeline implements market-basket analysis). **Do not write this
part of the Experimental Results chapter until that algorithm is built and
actually run** — there is nothing to report yet, and this table must never
be filled with placeholder or assumed numbers.

## 6. Plagiarism / AI-use thresholds

Similarity ≤ 20%, AI-related score ≤ 10% — identical to the rules already
recorded in `THESIS_PRODUCT_MASTER_PLAN.md` §10. That section is the source
of truth for the full workflow (Zotero/BibTeX library, Turnitin audit,
no AI-generated text pasted directly, no detector-evasion). Not repeated
here to avoid the two files drifting out of sync.

## 7. Open / uncertain items from the handwritten notes

- One note appears to name a candidate algorithm — the handwriting is not
  clearly legible (reads roughly like "BT-RUB"). This is **not** treated as
  a confirmed name. The framework name already agreed and used throughout
  the codebase and `THESIS_PRODUCT_MASTER_PLAN.md` is **B-SMART**; keep
  using that until the user explicitly confirms a different final name
  after the literature search (the master plan already notes the name
  should only be frozen once no conflict with an existing published
  framework is confirmed).
