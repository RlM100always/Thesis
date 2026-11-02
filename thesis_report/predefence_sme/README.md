# Pre-defence thesis report upgrade — SME scope

This report is an upgrade of the user's uploaded pre-defence LaTeX report. It preserves the original thesis title, University of Dhaka report style, six-chapter sequence and research direction while replacing the pharmacy-only framing with a multi-sector Bangladeshi SME framework.

## Included work
- Scope: Bangladeshi SMEs across sectors, using a shared operational core and optional sector-specific extensions.
- Chapter 4: implementation of the React/FastAPI SME platform, operational modules, permissions, analytics and recommendation workflow.
- Chapter 5: executed RQ1–RQ4 results, tables, charts and limitations.
- Appendices: source-version audit, selected unflagged export checksums, model configurations and aggregate outputs.
- Diagrams: pharmacy-specific diagrams have been replaced by editable TikZ diagrams for multi-sector SMEs.

## Evidence boundary
The current 32-shop empirical dataset is classified as grocery/FMCG retail. It does not establish multi-sector validation. RQ1 is shop-category-day forecasting, RQ2 uses the supplied 90-day inactivity target, RQ3 is a scenario/oracle comparison, and RQ4 is a structured explanation-case audit rather than a human usability study. Merchant provenance and consent have not been independently verified.

The later duplicate exports that add a `synthetic_flag` field are excluded; the selected source exports are the earlier unflagged versions. The original user-uploaded pre-defence ZIP is preserved unchanged outside this upgraded report.

## Build
After restoring the source bundle, run `pdflatex main.tex` three times in the restored source directory. The report uses the original A4/11pt book-style layout, one-sided pagination and the existing University logo.

## Privacy
Raw business exports, row-level customer predictions and trained model files are not committed to this public repository. Only report source, aggregate metrics and source checksums should be published.
