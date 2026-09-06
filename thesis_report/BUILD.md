# Building the thesis progress report

The report uses the supplied University of Dhaka `Thesis.cls` template with
completed English content and local figures.

## Tectonic (portable, recommended)

From `thesis_report/`:

```powershell
tectonic main.tex --keep-logs --keep-intermediates
```

If using the repository's portable compiler instead, run
`..\.tools\tectonic\tectonic.exe main.tex --keep-logs --keep-intermediates`.
Tectonic resolves the bibliography and repeated references automatically.

## TeX Live or MiKTeX

```powershell
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The final verified PDF is copied to
`../output/pdf/Thesis_Progress_Report_2026.pdf`.
