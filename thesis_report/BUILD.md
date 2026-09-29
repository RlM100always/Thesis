# Building the thesis progress report

The report uses the supplied University of Dhaka `Thesis.cls` template. This
initial submission completes Introduction, Background Study and Related Work,
Proposed Methodology, and a current-stage Conclusion. Implementation and
Experimental Results remain heading-only placeholders.

> Scope note dated 8 September 2026: the report now uses Bangladeshi retail
> pharmacies as its initial empirical vertical and incorporates the
> supervisor-guided, shop-constraint-aware architecture recorded in
> `../docs/PHARMACY_VERTICAL_SCOPE_AND_SUPERVISOR_GUIDELINE.md`.

## Tectonic (portable, recommended)

From `thesis_report/`:

```powershell
tectonic main.tex --keep-logs --keep-intermediates
```

If using the repository's portable compiler instead, run
`..\.tools\tectonic\tectonic.exe main.tex --keep-logs --keep-intermediates`.
Tectonic resolves the bibliography and repeated references automatically.

## Overleaf or Prism

Upload `../Thesis_LaTeX_Minimal_Overleaf.zip` as a new project and set
`main.tex` as the main document. The minimal archive contains only the complete,
self-contained `main.tex` and the required `logo.pdf`; chapter text, template
definitions and the resolved bibliography are already embedded in `main.tex`.
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
