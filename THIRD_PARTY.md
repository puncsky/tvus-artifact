# Third-party material

## AgentDojo

`external/agentdojo/cases/` contains task prompts and record excerpts rendered from AgentDojo 0.1.35, benchmark v1.2.2. The upstream MIT copyright and license are preserved in `external/agentdojo/LICENSE-agentdojo`. The port and sink integration are authored for this study. No installed AgentDojo package or model weights are vendored. See `external/agentdojo/README.md` and `requirements.lock`.

## Defense papers

B1/PACT-style, B2/CXI-style and B5/CausalArmor-style implementations are paper-derived ports. The official defense repositories are not bundled. Bibliographic attribution appears in `paper/workshop/refs.bib`, `artifacts.md` and `baseline-matrix.md`.

## Paper template and fonts

The paper follows the AAAI-27 Author Kit. The compiled PDF includes embedded fonts, but this repository does not redistribute the template style files or a TeX installation. Obtain the unmodified style files from the official author kit to rebuild. `paper/workshop/main.tex` and the vector figure are the author's work.

## Runtime dependencies and checkpoints

Python packages are installed separately. Analysis pins are in `requirements.txt`; historical backend/provider versions are recorded in `configs/` and run manifests. Checkpoints listed in `configs/models.json` are downloaded separately from their publishers and remain subject to their respective licenses and access terms.
