# Abstract

`Team6_Section22_Topic12_Abstract_ClinicalPlanVerification.pdf`: the project abstract submitted on September 5, 2026. It is the original statement of the scope, the four models, the Hager et al. (2024) baseline and the targets (plan validity >= 0.85 and escape rate <= 0.05 on a 100-case held-out split) that `docs/metrics.md` builds on.

The PDF is kept exactly as submitted. Three statements in it are out of date:

| In the abstract | Now |
|---|---|
| Repository link `.../Clinical-Discharge-TreatmentPlan-Verification` | the working link is `https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification` (hyphen in "Treatment-Plan") |
| Dataset access "pending" | MIMIC-IV v3.1 and MIMIC-IV-Ext-CDM v1.1 are downloaded and checksum-verified (see `docs/data_collection.md`) |
| Target: plan validity >= 0.85 | evaluation protocol v1.1 (October 23, 2026) removes 0.85 as an automatic acceptance target, because strict record facts make it unreachable (test-set ceiling 47/73 plain schema acceptance, 18/73 checked acceptance). 0.85 is kept as a research goal for independently human-adjudicated plans only. The escape target <= 0.05 is unchanged. See `docs/metrics.md` and `docs/evaluation_feasibility.md` |
