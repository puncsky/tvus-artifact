export TEXINPUTS := .:./aaai//:
export BSTINPUTS := .:./aaai//:

.PHONY: all
all:
	 pdflatex -interaction=nonstopmode -halt-on-error main.tex
	 bibtex main
	 pdflatex -interaction=nonstopmode -halt-on-error main.tex
	 pdflatex -interaction=nonstopmode -halt-on-error main.tex
