# Building the thesis progress report

The report uses the supplied University of Dhaka `Thesis.cls` template. This
initial submission completes Introduction, Background Study and Related Work,
Proposed Methodology, and a current-stage Conclusion. Implementation and
Experimental Results remain heading-only placeholders.

> Current scope (2 November 2026): the report covers Bangladeshi SME businesses
> across sectors. A shared operational core is extended for inventory-based and
> service businesses, with sector-specific constraints and evidence-bounded
> business/sector transfer evaluation. This supersedes the report's former
> pharmacy-only scope. Historical documents outside this report may retain that
> earlier scope; they do not define this revision's research population.

## Tectonic (portable, recommended)

From `thesis_report/`:

```powershell
tectonic main.tex --keep-logs --keep-intermediates
```

If using the repository's portable compiler instead, run
`..\.tools\tectonic\tectonic.exe main.tex --keep-logs --keep-intermediates`.
Tectonic resolves the bibliography and repeated references automatically.

## Overleaf or Prism

Upload the current `main.tex` and `Figures/logo.pdf` as a new project, placing
the logo at the project root, and set `main.tex` as the main document. Chapter
text, template definitions and the resolved bibliography are embedded in
`main.tex`. Diagrams use editable TikZ. Older exported ZIPs are not the source
of truth for this revision.
Use pdfLaTeX or XeLaTeX.

## TeX Live or MiKTeX

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The final verified PDF is copied to
`../output/pdf/Thesis_Progress_Report_2026.pdf`.
