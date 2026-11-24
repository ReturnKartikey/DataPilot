# Report accuracy and visualization fixes

- EDA now stores target-class counts and percentages computed from the uploaded DataFrame.
- Report generation adds a deterministic direct answer for recognized class-prevalence questions, including UCI mushroom labels `p` (poisonous) and `e` (edible).
- Report payload now includes chart-ready target distribution, categorical summaries, and feature importance.
- Audit report UI renders Markdown as formatted headings/lists rather than showing raw Markdown source.
- Audit report UI renders data-driven bar charts and a direct-answer metric panel.
- PDF report export includes bar charts in the Visual analysis section.
- Added a regression test for the mushroom poisonous-percentage question.
