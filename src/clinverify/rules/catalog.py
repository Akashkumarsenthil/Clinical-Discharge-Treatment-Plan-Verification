"""The project's rule catalog (written and reviewed by the team).

Currently empty on purpose: rules are clinical content and must be authored and sourced by the team (owner: Sneha).
Add rules here with the decorator, one function per rule. Example of the pattern (do not copy as a real rule):

    from clinverify.rules.base import RuleCatalog
    catalog = RuleCatalog()

    @catalog.register("R-XXX-001", "what must hold, in one sentence", "guideline or paper that justifies it",
                      requires=("discharge_hour",))
    def r_xxx_001(plan):
        return z3.IntVal(plan.discharge_hour) >= 0      # build a z3 expression that must be satisfiable
"""
from clinverify.rules.base import RuleCatalog

catalog = RuleCatalog()
