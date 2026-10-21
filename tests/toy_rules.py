"""TOY rules used only to test the verifier and harness. Not clinical content and not the project's rule set."""
import z3

from clinverify.rules.base import RuleCatalog

catalog = RuleCatalog()


@catalog.register("R-TOY-001", "every ordered lab has resulted by the discharge hour",
                  "toy rule for tests", requires=("labs", "discharge_hour"))
def toy_labs(plan):
    return z3.And([z3.IntVal(h) <= z3.IntVal(plan.discharge_hour) if h is not None else z3.BoolVal(False)
                   for h in plan.labs.values()])


@catalog.register("R-TOY-002", "no prescribed drug is on the patient's contraindicated list",
                  "toy rule for tests", requires=("medications", "contraindicated"))
def toy_meds(plan):
    return z3.And([z3.Not(z3.StringVal(m) == z3.StringVal(c)) for m in plan.medications for c in plan.contraindicated]
                  or [z3.BoolVal(True)])


@catalog.register("R-TOY-003", "the plan names at least one follow-up action", "toy rule for tests",
                  requires=("follow_up",))
def toy_followup(plan):
    return z3.BoolVal(len(plan.follow_up) > 0)
