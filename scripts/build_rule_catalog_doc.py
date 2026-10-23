"""Generate docs/rule_catalog.md from src/clinverify/rules/catalog.py so the document can never drift from the code.

Run from the repository root:  python scripts/build_rule_catalog_doc.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.rules.catalog import CATALOG_VERSION, catalog  # noqa: E402

HEADER = f"""# Rule catalog v{CATALOG_VERSION}

Code: `src/clinverify/rules/catalog.py` (the single source of truth; this page is generated from it by
`scripts/build_rule_catalog_doc.py` and a test fails if the two differ).

**Status: version {CATALOG_VERSION} for team sign-off.** Each rule below was written from a statement in a guideline or systematic review published in 2025-2026
(the course asks for sources no older than 3-4 years), and is covered by tests. The source column says whether the full text or only the abstract was read. It is **not clinically validated**: no clinician has reviewed it.

**Provenance.** The first draft was prepared with an AI coding assistant. A rule becomes the team's rule through the sign-off in `docs/rule_signoff.md`.
The model that generates plans never writes or sees the rules, so a plan is not graded against constraints it invented.

## What the rules check

The rules check an LLM-generated plan for appendicitis, pancreatitis and diverticulitis against guideline
recommendations that can be tested from a structured plan plus facts from the patient record:

- **Plan content** comes from the model: diagnosis, treatments (canonical concepts), antibiotic course in days.
- **Case facts** come from the record, never from the model: for example whether the disease is complicated, or whether the patient is suitable for surgery (`CASE_FACTS` in `plan.py`).
- A rule **applies** only under its condition. If an applicable rule needs a plan field or case fact that is missing, the result is **insufficient information**, and the plan does not pass.
- A violated rule returns its **violation message**, which is also the feedback for the repair loop (Model C).

## The rules

| ID | Name | Applies when | Needs | Source and location | Strength as stated by the source |
|---|---|---|---|---|---|
"""

FOOTER = """
Details per rule (recommendation paraphrase, violation message, valid and invalid synthetic example) are in the code.

## Sources (all 2025-2026)

| Short name | Reference | Read |
|---|---|---|
| SWE | Salö M. et al. (2025). Antibiotic prophylaxis and postoperative antibiotics in appendicitis: systematic review and guideline. BJS Open 9:zrae165 | full text |
| WSES25 | Podda M. et al. (2026). Acute appendicitis guideline update (WSES). JAMA Surg 161:283-295 | abstract only |
| ILATAM | Cárdenas-Jaén K. et al. (2026). Acute pancreatitis guideline (iLATAM). United European Gastroenterol J 14:e70190 | full text |
| ACG26 | Peery A.F. et al. (2026). ACG clinical guideline: diverticulitis. Am J Gastroenterol 121:1549-1561 | abstract only |
| KASID26 | Lee K.-M. et al. (2026). KASID guideline on diverticular disease. Intest Res 24:428-463 | full text |

Rules that rest on an abstract are weaker: read the full text before ticking them.

## Version 2.1 changes

- A rule whose condition fact is known to be false is "not applicable", not a pass (R-APP-002, R-APP-003, R-PAN-002 to R-PAN-004, R-DIV-001 to R-DIV-003).
- R-APP-003 applies only when an appendectomy is planned and checks only the upper bound of 3 days (zero days passes).
- R-DIV-003 no longer needs screening history when alarm symptoms are known.\n- R-PAN-004 is decided as soon as one positive indication (cholangitis or bile-duct obstruction) is known.
- Advisory violations are reported but do not make a plan invalid.

## Why version 1.0 was replaced

Version 1.0 (14 rules) used WSES guidelines from 2019-2020. The course asks for sources no older than 3-4 years, so version 2.0 uses only 2025-2026 sources.
Rules whose newer source could not be read were not carried over:

| Dropped from v1.0 | Reason |
|---|---|
| Cholecystitis rules (R-CHO-001, R-CHO-002), `cholecystitis` as a covered diagnosis | no recent guideline with readable full text; cholecystitis plans now return R-GEN-001 |
| Appendectomy within 24 hours (R-APP-004) | no readable recent source for the timing threshold |
| Old R-DIV-002 (about 4 days of postoperative antibiotics) | replaced by the ACG 2026 / KASID 2026 rules R-DIV-001 to R-DIV-003 |

## Not covered, and why

| Candidate | Reason |
|---|---|
| Newest full-text guidelines (IAP 2025, WSES 2025 full text, ACG 2026 full text, ASCRS 2026, ACP 2022) | paywalled; not read |
| Severity-dependent surgery (colectomy for perforation, necrosectomy, interval appendectomy) | needs severity details the plan and record facts do not yet carry |
| Discharge before required labs resulted; contraindicated medication (the abstract's examples) | need a clinical source and medication data (MIMIC-IV `prescriptions`, `pharmacy`) |
| Children, pregnancy, special populations | separate, mostly weaker statements |

## Limits the team should state in the report

- Sources date from 2025-2026; two were read as abstracts only.
- Mapping free-text plans to the canonical treatment concepts is the plan parser's job, and a mapping error there is a translation-fidelity error.
- Rules marked advisory (R-APP-003, R-PAN-004, R-DIV-001, R-DIV-003) rest on weaker or conditional statements; their violations print '(advisory)' and are not blocking.
- No clinician has reviewed the set.

## Sign-off

Sign-off is recorded in **[docs/rule_signoff.md](rule_signoff.md)** (a separate page that people edit by hand; this page is generated and must not be edited).
Tick a rule only after reading its cited statement in the source itself; if you cannot tick it, write the reason in the Notes column.

## Run and test

```bash
python -m pytest tests/test_catalog.py
python scripts/make_catalog_labeled_plans.py        # regenerates the labeled synthetic plans (a test checks they are current)
python scripts/run_eval.py --plans tests/data/catalog_labeled_plans.json --rules clinverify.rules.catalog
python scripts/build_rule_catalog_doc.py            # regenerates this page
```
"""


def build() -> str:
    rows = []
    for r in catalog:
        needs = ", ".join(f"`{n}`" for n in r.requires) or "none"
        rows.append(f"| `{r.id}` | {r.name} | {r.applies_when} | {needs} | {r.source} | {r.strength} |")
    return HEADER + "\n".join(rows) + "\n" + FOOTER


if __name__ == "__main__":
    (ROOT / "docs" / "rule_catalog.md").write_text(build())
    print("wrote docs/rule_catalog.md with", len(catalog), "rules")
