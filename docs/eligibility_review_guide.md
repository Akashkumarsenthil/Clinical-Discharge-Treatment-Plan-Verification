# Eligibility review of the 73 covered test cases

**Status:** not started. Reviewer: **not assigned yet**. It has to be one of the other three members, not Akash (he wrote Model A) and not SS (rule author). Nobody has filled the sheet. The assistant must not fill it.

This is step 1 in [adjudication_labels.md](adjudication_labels.md) and a hard requirement in [metrics.md](metrics.md). It has to be finished and frozen **before** Model A generates any test plan.

## The question for each case

> Does this admission record contain enough information for a clinician to judge whether a treatment plan for the case's reference diagnosis is clinically adequate and valid?

Answer **yes** or **no**. For **no**, write a short reason in your own words (for example "no imaging result in the record", "course of treatment not documented"). No patient text in the reason.

## Conditions (the manifest says `blind_to_plans: true`, so these must hold)

- Do not look at any generated plan, any Model A output or any verifier verdict for these 73 cases.
- Do not use the case facts or the rule coverage counts to decide. Judge from the record only.
- Do not choose cases because a rule can decide them. Every one of the 73 gets an answer, including the hard ones.
- The record text stays on the authorised machine. Only IDs, yes/no and short reasons go in the sheet.

## Steps

1. Copy [eligibility_review_sheet.csv](eligibility_review_sheet.csv) to a working file outside the repo. It lists the 73 covered case IDs (40 appendicitis, 22 pancreatitis and 11 diverticulitis are covered by catalog v2.1; the 27 cholecystitis cases are out of scope).
2. Fill `eligible_yes_no` (and `reason_if_no`) for every row.
3. Build and check the manifest. It refuses a blank or unclear row and checks the 73 against the frozen selection:
   `python scripts/build_eligibility_manifest.py --sheet <filled.csv> --reviewer AS --date YYYY-MM-DD --blind-to-plans`
4. The script prints the manifest's SHA-256. Record the hash, the date, the reviewer and the eligible count **E** in [metrics.md](metrics.md) (the Open items table) before generation starts.
5. Commit the manifest (IDs, yes/no, short reasons) so it is frozen. Do not edit it afterwards.

Report **E/73** with the reasons for each excluded case. The 73-case denominator is never replaced by E.

## Independence

The reviewer did not write the rules (SS did) and has not seen any test plan, since none exists yet. He wrote Model A, so he knows the model, but the review is of records only. If the team wants a reviewer with no link to Model A, give the sheet to another member instead and change the name above.

## Plan labels come later and need a different person

After generation, each eligible plan needs an independent label (see [adjudication_labels.md](adjudication_labels.md); blank template: [plan_label_sheet_template.csv](plan_label_sheet_template.csv)). That reviewer must be someone other than the rule author (SS) and the Model A author (AS), so one of the other three members.
