"""Draft Gantt and PERT/dependency charts for Workbook 1 section 2.4.
Dates: official course dates + proposed task windows (PROPOSED, align with Linear cycles).
Run: python scripts/build_schedule_charts.py <output_dir>
"""
import sys, datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

out = sys.argv[1] if len(sys.argv) > 1 else "."
D = lambda m, d: dt.date(2026, m, d)

tasks = [  # name, owner, start, end
    ("Data access, manifest, ingestion", "Akash", D(9,10), D(10,8)),
    ("Metrics, fixed splits, leakage checks", "Rajesh", D(9,29), D(10,8)),
    ("Rule catalog + synthetic cases", "Sneha", D(9,25), D(10,22)),
    ("Environment, CI, pinned run commands", "Shruthi", D(9,25), D(10,22)),
    ("Verifier (Z3 encoding) + unit tests", "Sneha/Shruthi (proposed)", D(10,9), D(11,5)),
    ("Evaluation harness", "Rajesh (proposed)", D(10,9), D(11,5)),
    ("Model A implementation", "Ritika", D(10,9), D(11,5)),
    ("Baseline reproduction (Hager)", "Rajesh/Ritika (proposed)", D(10,23), D(11,26)),
    ("Benchmark runs + failure study", "Team", D(11,6), D(12,1)),
    ("Final report", "Team", D(11,13), D(12,7)),
]
milestones = [(D(10,7),"WB1"),(D(10,8),"TM1"),(D(10,22),"PR2"),(D(11,11),"WB2"),(D(11,12),"TM2"),(D(12,7),"Final"),(D(12,8),"Pres")]
cycles = [(D(9,10),D(9,24)),(D(9,25),D(10,8)),(D(10,9),D(10,22)),(D(10,23),D(11,5)),(D(11,6),D(11,12)),(D(11,13),D(11,26)),(D(11,27),D(12,7))]

fig, ax = plt.subplots(figsize=(11, 5.6))
for i,(a,b) in enumerate(cycles):
    if i % 2 == 0:
        ax.axvspan(a, b + dt.timedelta(days=1), color="#eef2f7", zorder=0)
for i,(name,owner,s,e) in enumerate(tasks):
    y = len(tasks)-1-i
    ax.barh(y, (e-s).days+1, left=s, height=0.55, color="#4472c4", zorder=2)
    ax.text(s + dt.timedelta(days=1), y, owner, va="center", ha="left", color="white", fontsize=7)
ax.set_yticks(range(len(tasks)))
ax.set_yticklabels([t[0] for t in tasks][::-1], fontsize=8)
for d,l in milestones:
    ax.axvline(d, color="#c00000", lw=0.9, ls="--", zorder=3)
    ax.text(d, len(tasks)-0.35, l, rotation=90, ha="right", va="bottom", fontsize=7, color="#c00000")
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
plt.setp(ax.get_xticklabels(), fontsize=8)
ax.set_xlim(D(9,8), D(12,10)); ax.set_ylim(-0.7, len(tasks)+0.6)
ax.set_title("DATA 298A Gantt (proposed windows; shaded bands = two-week Linear cycles; dashed = course milestones)", fontsize=9)
plt.tight_layout(); plt.savefig(f"{out}/gantt.png", dpi=200); plt.close()

# PERT / dependency view
nodes = {
 "data":("Data access\n(approved copies)",0.0,2.0),
 "manifest":("Manifest +\ningestion",1.6,2.0),
 "splits":("Fixed splits\n+ metrics (10/8)",3.2,2.0),
 "rules":("Rule catalog",0.0,0.6),
 "verifier":("Verifier\n(Z3)",1.6,0.6),
 "harness":("Evaluation\nharness",3.2,0.6),
 "modelA":("Model A",4.8,1.3),
 "bench":("Benchmark +\nfailure study",6.4,1.3),
 "gpu":("GPU access",3.2,-0.8),
 "baseline":("Hager baseline\nreproduction",4.8,-0.8),
 "report":("Final report\n(12/7)",8.0,1.3),
}
edges=[("data","manifest"),("manifest","splits"),("splits","harness"),("rules","verifier"),("verifier","harness"),
       ("harness","modelA"),("modelA","bench"),("gpu","baseline"),("baseline","bench"),("bench","report")]
fig, ax = plt.subplots(figsize=(11, 4.8))
w,h=1.25,0.7
for k,(label,x,y) in nodes.items():
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle="round,pad=0.03",fc="#dae3f3",ec="#4472c4"))
    ax.text(x,y,label,ha="center",va="center",fontsize=8)
for a,b in edges:
    xa,ya=nodes[a][1],nodes[a][2]; xb,yb=nodes[b][1],nodes[b][2]
    if abs(xa-xb) < 1e-9:      # vertical link: bottom/top edges
        start, end = (xa, ya-h/2), (xb, yb+h/2)
    else:                       # horizontal/diagonal link: right/left edges
        start, end = (xa+w/2, ya), (xb-w/2, yb)
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10, color="#444"))
ax.set_xlim(-1,8.9); ax.set_ylim(-1.6,2.8); ax.axis("off")
ax.set_title("Dependency (PERT-style) view: critical path = data -> manifest -> splits -> harness -> Model A -> benchmark -> report", fontsize=9)
plt.tight_layout(); plt.savefig(f"{out}/pert.png", dpi=200); plt.close()
print("ok")
