# Building the main thesis progress report

`thesis_report/main.tex` is the single source of truth for the active report. It contains the title page, front matter, all six chapters, figures, tables, and bibliography. Do not create a parallel standalone report or substitute a different LaTeX template.

## Build locally

From the repository root:

```powershell
cd thesis_report
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The source uses the existing University of Dhaka report layout, A4 paper, 11-point book class, line spacing, page margins and headers, DU colour palette, and table conventions. Keep those settings unchanged when editing the report.

## Main report PDF

The compiled report is published at `output/pdf/main-thesis-report.pdf`. A GitHub Actions workflow builds the PDF when the main report source or its build workflow changes. The PDF is copied back to the same repository path after successful compilation.

## Research evidence

The RQ1 forecasting script and machine-readable development outputs are stored under `research/forecasting/`. The raw SME dataset remains in its controlled Google Drive location and is not committed to the public repository. Numerical results in Chapter 5 must be regenerated from the source panel and must not be manually typed or invented.
