# Building the thesis progress report

The report uses the supplied University of Dhaka `Thesis.cls` template. This
initial submission completes Introduction, Background Study and Related Work,
Proposed Methodology, and a current-stage Conclusion. Implementation and
Experimental Results remain heading-only placeholders.

## Tectonic (portable, recommended)

From `thesis_report/`:

```powershell
tectonic main.tex --keep-logs --keep-intermediates
```

If using the repository's portable compiler instead, run
`..\.tools\tectonic\tectonic.exe main.tex --keep-logs --keep-intermediates`.
Tectonic resolves the bibliography and repeated references automatically.

## Overleaf or Prism

Upload the supplied source ZIP as a new project. Set `main.tex` as the main
document and use pdfLaTeX or XeLaTeX. The archive contains the class file,
bibliography, chapter sources and the required logo; generated auxiliary files
and unused experimental images are intentionally excluded.

## TeX Live or MiKTeX

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The final verified PDF is copied to
`../output/pdf/Thesis_Progress_Report_2026.pdf`.
