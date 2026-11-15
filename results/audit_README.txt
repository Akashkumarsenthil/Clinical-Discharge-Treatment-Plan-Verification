PRELIMINARY LOCAL AI REVIEW -- NOT HUMAN OR CLINICAL VALIDATION

Input: results/audit_sample.csv (credentialed patient evidence; keep local).
Output: results/audit_preliminary.csv (keep local; reasons may contain sensitive information).
Reviewer model: llama3.1:8b via Ollama at 127.0.0.1:11434.
Model ID reported by local Ollama: 46e0c10c039e.
Temperature: 0. Seed: 298.

The model sees the pathology, requested fact, ICD titles, and discharge diagnosis.
It does NOT see the extraction's derived value before making its own judgment.
Its supported value is then compared with the extraction's value by the script.
Low-confidence judgments are marked unsure regardless of value matching.

ai_suggestion=yes: the AI-supported value matches the extraction (not proof of correctness).
ai_suggestion=no: the values differ; a human should inspect the original evidence.
ai_suggestion=unsure: low-confidence AI judgment; a human should inspect the evidence.

The original reviewer_agrees (yes/no/unsure) column is NOT modified.
Do not copy AI suggestions into that column and call them manual review.
No patient text was sent to a hosted model. Only the local Ollama service was used.
The evidence is limited to titles and discharge diagnoses, not a full chart review.
The generic local model is not a qualified clinical adjudicator and can make mistakes.
An agreement percentage with this model is NOT sensitivity, specificity, accuracy,
or clinical validation. Use disagreements as triage for independent human review.

The execution script is saved at:
/Users/snehasingh/Documents/Codex/2026-10-18/da/local_ai_audit.py
