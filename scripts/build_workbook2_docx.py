"""Build workbook/T6.A6.docx (Workbook 2, report sections 3 and 4) from results/workbook2/.

Real data enter only as the aggregate CSVs and figures that notebooks/workbook2.ipynb writes. Record samples
come from the synthetic generator (same schema, same pipeline functions), so the document holds no MIMIC text.

    pip install python-docx        # only needed for this script
    python scripts/build_workbook2_docx.py

Re-running OVERWRITES workbook/T6.A6.docx, including any edits made in Word. Rebuild only after the notebook
has been re-run, then re-apply the team's edits (authors, ratings, wording).
"""
import re
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_COLOR_INDEX, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data.synthetic import generate  # noqa: E402
from clinverify.models import model_a as A  # noqa: E402

RES = ROOT / "results" / "workbook2"
FIG = RES / "figures"
OUT = ROOT / "workbook" / "T6.A6.docx"
NB = "notebooks/workbook2.ipynb"
SYN = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/wb2_synth")


def csv(name):
    return pd.read_csv(RES / f"{name}.csv")


# ---------------------------------------------------------------- synthetic samples
if not (SYN / "mimic-iv-ext-cdm-1.1").exists():
    generate(SYN, n_cases=20)
SYN_EXT = SYN / "mimic-iv-ext-cdm-1.1"
s_raw = E.load_tables(SYN_EXT)
s_clean, _ = E.clean_tables(s_raw)
s_tr = E.transform_tables(s_clean, SYN_EXT)
s_inputs = A.case_inputs(s_tr)

# ---------------------------------------------------------------- document helpers
doc = Document()
st = doc.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for s in doc.sections:
    s.left_margin = s.right_margin = Inches(0.9)
    s.top_margin = s.bottom_margin = Inches(0.8)


def runs(par, text, size=None):
    """Write text with **bold**, `code` and [[placeholder]] (yellow highlight) markup."""
    for part in re.split(r"(\*\*.+?\*\*|`.+?`|\[\[.+?\]\])", text):
        if not part:
            continue
        if part.startswith("**"):
            r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`"):
            r = par.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.size = Pt((size or 11) - 1.5)
        elif part.startswith("[["):
            r = par.add_run(part[2:-2]); r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        else:
            r = par.add_run(part)
        if size and not part.startswith("`"):
            r.font.size = Pt(size)
    return par


def H(text, level):
    return doc.add_heading(text, level=level)


def P(text, style=None):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(6)
    return runs(p, text)


def bullets(items):
    for it in items:
        P(it, "List Bullet")


def author(name="[[Author: team member]]"):
    p = doc.add_paragraph()
    r = runs(p, name)
    for r in p.runs:
        r.italic = True


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_fill)
    tcPr.append(sh)


def table(df, caption=None, size=8.5, widths=None):
    if caption:
        cap = doc.add_paragraph(); runs(cap, f"**{caption}**", size=10)
        cap.paragraph_format.keep_with_next = True
    df = df.copy()
    t = doc.add_table(rows=1, cols=len(df.columns))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]
        cell.text = ""
        runs(cell.paragraphs[0], f"**{c}**", size=size)
        shade(cell, "D9E2F3")
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            is_id = "id" in str(df.columns[i]).lower().split("_") or str(df.columns[i]).lower() in ("hadm_id", "itemid")
            if isinstance(v, bool):
                pass
            elif isinstance(v, (int, float)) and not pd.isna(v) and float(v).is_integer():
                v = str(int(v)) if is_id else f"{int(v):,}"
            elif isinstance(v, float):
                v = "" if pd.isna(v) else f"{v:.3f}".rstrip("0").rstrip(".")
            runs(cells[i].paragraphs[0], str(v), size=size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


FIGN = {}


def figure(png, caption, section, width=6.3):
    num = section.split(".")[0] + "." + section.split(".")[1]
    FIGN[num] = FIGN.get(num, 0) + 1
    doc.add_picture(str(FIG / png), width=Inches(width))
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    p = doc.add_paragraph()
    runs(p, f"**Figure {num}-{FIGN[num]}.** {caption} Produced by `{NB}`, section {section}.", size=9)


def kv(rows, caption=None, widths=(2.2, 4.5)):
    table(pd.DataFrame(rows, columns=["Item", "Value"]), caption, widths=widths)


def cut(s, n=70):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- numbers
src = csv("3_2_sources"); qty = csv("3_2_quantity"); dup = csv("3_3_duplicates"); miss = csv("3_3_missing")
vfail = csv("3_3_validation_failures"); tlog = csv("3_4_transform_log"); flags = csv("3_4_lab_flags")
facts = csv("3_4_case_facts"); split = csv("3_5_split_table"); stage = csv("3_6_stage_summary")
cover = csv("3_6_rule_coverage"); env = csv("4_2_environment"); comp = csv("4_4_model_comparison")
layers = csv("4_5_layer_counts"); dq = csv("4_5_dq_checks"); hist = csv("4_5_run_history")
process = csv("3_1_process")

n_cases = int(split["cases"].sum()); raw_rows = int(stage.loc[stage.stage == "Raw", "rows"].iloc[0])
pre_rows = int(stage.loc[stage.stage == "Pre-processed", "rows"].iloc[0])
n_dups = int(dup["duplicate_rows"].sum())
ma = comp.set_index("model").filter(like="Model A", axis=0).iloc[0]
me = comp.set_index("model").filter(like="Model E", axis=0).iloc[0]
mj = comp.set_index("model").loc["Majority class"]
last_ok = hist[hist.status == "ok"].iloc[0]
fault = hist[hist.status == "failed_checks"].iloc[0]
prompt_sha = A.prompt_sha256()

# ================================================================= title block
t = doc.add_paragraph(); runs(t, "**DATA 298A Workbook 2**", size=18)
t = doc.add_paragraph(); runs(t, "Report Sections 3 and 4: Data Engineering and Model Development", size=13)
kv([
    ["Team, section and topic", "Team 6, Section 22, Topic 12: Neurosymbolic Verification of LLM-Generated Clinical Discharge and Treatment Plans"],
    ["Date", "[[November 11, 2026]]"],
    ["Assignment", "Assignment 6 (Workbook 2), file T6.A6.docx"],
    ["Evidence", f"`{NB}` (all tables and figures), `src/clinverify/warehouse.py`, `src/clinverify/models/model_a.py`, `scripts/run_pipeline.py`; repository commit [[<commit hash after the Workbook 2 code is committed>]]"],
])
P("**Team members and the sections each person wrote**")
table(pd.DataFrame({
    "Team member": ["Ritika Mukesh Neema", "Rajesh Paruchuri", "Akashkumar Senthilkumar", "Sneha Singh", "Shruthi Thirukumaran"],
    "Sections written": ["[[sections]]"] * 5,
}), widths=(2.5, 4.2))
P("**How patient data is handled in this report.** Every count, statistic, metric and figure below is computed on the real "
  "credentialed data (MIMIC-IV-Ext-CDM v1.1 and MIMIC-IV v3.1) on a team member's own approved machine. The PhysioNet "
  "data use agreement does not allow record text to be passed to anyone who has not signed it, so the **record samples** "
  "that sections 3.2 to 3.5 ask for are shown with **synthetic rows** produced by `src/clinverify/data/synthetic.py`. "
  "They have exactly the real schema and go through exactly the same pipeline functions; the real samples are in the "
  "executed notebook, which stays on the authorised machine. Model A runs on a local GPU, so no record text is sent to a hosted LLM.")

# ================================================================= 3
H("3  Data Engineering", 1)

# ---------------------------------------------------------------- 3.1
H("3.1  Data Process", 2); author()
P(f"The project's raw data are two credentialed PhysioNet datasets. MIMIC-IV-Ext-CDM v1.1 (Hager et al., 2024 [3][4]) is the "
  f"working set: {n_cases:,} curated hospital admissions with one of four abdominal pathologies, split into nine record tables "
  "(history, physical examination, labs, microbiology, radiology, ICD codes, procedures and the discharge diagnosis). MIMIC-IV v3.1 "
  "(Johnson et al., 2023 [6]) is used for one thing only: its admissions table maps each admission to a patient, so the splits "
  "can be grouped by patient.")
P("The data move through seven steps. Every step is a function in `src/clinverify/data` (or `models/model_a.py`), so the "
  "notebook that produced this report and the warehouse pipeline in section 4.5 run the same code.")
figure("3_1_data_process.png", "Data process from download to model evaluation.", "3.1")
table(process, "Table 3.1-1. Data process steps, tools and outputs.", size=8)
P("Two rules hold across the whole process. First, patient data never enter the repository: it holds code, case-ID split "
  "lists and aggregate counts only, and `.gitignore` blocks data files. Second, the answer is never shown to a model: the "
  "discharge diagnosis, ICD codes and procedures are used to build labels and case facts for scoring, but they are removed "
  "from every model input (section 3.4.4).")

# ---------------------------------------------------------------- 3.2
H("3.2  Data Collection", 2); author()
H("3.2.1  Data sources", 3)
src2 = src.copy()
src2.loc[src2.dataset == "MIMIC-IV", "files"] = 1
src2.loc[src2.dataset == "MIMIC-IV", "size_mb"] = 19.9
src2 = src2.rename(columns={"files": "files used", "size_mb": "size used (MB)"})
table(src2, "Table 3.2-1. Data sources.", size=8)
P("Both datasets are downloaded by each team member from PhysioNet with their own credentialed account after signing each "
  "dataset's data use agreement (Ext-CDM has its own agreement, separate from MIMIC-IV). The download command is "
  "`wget -r -N -c -np` against `physionet.org/files/<dataset>/<version>/`. Only `hosp/admissions.csv.gz` (19.9 MB) is needed "
  "from MIMIC-IV, so the multi-gigabyte event tables are not downloaded.")
H("3.2.2  Data parameters and quantity", 3)
P(f"Each record table is keyed by `hadm_id` (the hospital admission). `pathology_ids.json` gives the label of every case: "
  f"appendicitis 957, cholecystitis 648, pancreatitis 538, diverticulitis 257. PhysioNet ships a `SHA256SUMS.txt` with every "
  f"dataset; **all 12 Ext-CDM files match**, and all {n_cases:,} cases link to a MIMIC-IV admission, covering **2,383 patients**.")
q = qty.rename(columns={"file_mb": "MB", "cases": "cases covered", "column names": "parameters (columns)"})
table(q, f"Table 3.2-2. Quantity and parameters of the raw tables ({raw_rows:,} rows in 10 tables).", size=8,
      widths=(1.6, 0.5, 0.65, 0.55, 0.7, 2.7))
H("3.2.3  Raw data samples", 3)
P("Synthetic rows with the real schema (see the note at the start). The real first rows of each table are shown in section "
  "3.2.3 of the executed notebook.")
table(s_raw["laboratory_tests"].head(4), "Table 3.2-3. laboratory_tests, raw (synthetic sample).")
r = s_raw["radiology_reports"].head(3).copy(); r["text"] = r["text"].map(cut)
table(r, "Table 3.2-4. radiology_reports, raw (synthetic sample).")
table(s_raw["icd_procedures"].head(3), "Table 3.2-5. icd_procedures, raw (synthetic sample).")

# ---------------------------------------------------------------- 3.3
H("3.3  Data Pre-processing", 2); author()
P("Pre-processing has three parts: removing exact duplicates, deciding how each missing value is handled, and validating "
  "the cleaned tables. The tools are pandas and `ext_cdm.clean_tables` / `ext_cdm.validate_tables`.")
H("3.3.1  Cleaning: duplicates", 3)
P(f"**{n_dups} exact duplicate rows** were removed (68 in `icd_procedures`, 5 in `discharge_procedures`, 2 in `icd_diagnosis`). "
  "No case-level table had a duplicate case.")
table(dup, "Table 3.3-1. Rows before and after duplicate removal.", size=8)
H("3.3.2  Missing values", 3)
P("Only seven columns have missing values. Reference ranges are missing for 29% of lab rows; they are **kept as missing, "
  "not imputed**, because a reference range is a fact about one lab test, not a statistic that can be estimated. Those labs "
  "are flagged `unknown` in section 3.4. The single empty discharge procedure is dropped.")
table(miss, "Table 3.3-2. Missing values and how each is handled.", size=8, widths=(1.4, 1.4, 0.6, 0.7, 2.6))
H("3.3.3  Validation", 3)
P("`validate_tables` checks that labels are unique, required columns exist, case-level tables have one row per case, no "
  "`hadm_id` is empty or unknown, every case has the tables it must have, and no history note is empty. It **passes on the "
  "cleaned tables**. To show it works, the notebook also feeds it a deliberately corrupted copy (three duplicated cases, ten "
  "emptied history notes, the `hadm_id` column dropped from labs, an unknown case in microbiology, radiology removed for 1% of "
  "cases). **Every problem is caught:**")
table(vfail, "Table 3.3-3. Problems reported on the corrupted copy.")
P("The same validation is the data-quality gate of the warehouse load (section 4.5).")
H("3.3.4  Pre-processed data samples", 3)
dp = s_raw["discharge_procedures"].head(4).copy()
dp2 = s_clean["discharge_procedures"].head(3).copy()
table(dp, "Table 3.3-4. discharge_procedures before pre-processing (synthetic sample: row 1 has an empty procedure).")
table(dp2, "Table 3.3-5. discharge_procedures after pre-processing (empty row dropped).")

# ---------------------------------------------------------------- 3.4
H("3.4  Data Transformation", 2); author()
P("Transformation turns the cleaned tables into four target formats: (1) normalised tables, (2) a case table with one row per "
  "admission, (3) one model-input text per case, and (4) a TF-IDF feature matrix for the classical model. Tools: pandas "
  "(`ext_cdm.transform_tables`), regular expressions over ICD titles (`case_facts.py`), the model-input builder "
  "(`model_a.case_inputs`) and scikit-learn's `TfidfVectorizer`.")
table(tlog, "Table 3.4-1. Transformation log.", size=8, widths=(1.2, 1.2, 1.6, 1.3, 1.6))
H("3.4.1  Lab parsing and flagging", 3)
lab = s_tr["laboratory_tests"][["valuestr", "ref_range_lower", "ref_range_upper", "value", "unit", "qualifier", "flag", "label"]].head(5)
table(lab, "Table 3.4-2. Lab strings before (valuestr) and after parsing (synthetic sample).")
fl = flags.copy(); fl["rows"] = fl["rows"].map(lambda v: f"{v:,}")
table(fl, f"Table 3.4-3. Lab flags after transformation (real data, {int(flags.rows.sum()):,} rows).")
H("3.4.2  Case table and case facts", 3)
table(s_tr["cases_master"].head(4), "Table 3.4-4. cases_master, one row per case (synthetic sample).", size=8)
P("**Case facts** are the clinical facts the rules need (for example, whether appendicitis was complicated). They are derived "
  "from ICD titles and the discharge diagnosis, and are used **only by the verifier, never shown to a model**. In strict mode a "
  "fact the record does not establish stays **unknown**; it is never guessed. The table shows how many facts the real records "
  "establish:")
table(facts, "Table 3.4-5. Case facts established from the records (real data).")
H("3.4.3  Model input format", 3)
P("Each case becomes one text in a fixed section order with fixed limits: history, physical examination, labs (abnormal first, "
  "at most 40), microbiology (at most 15) and up to 3 radiology reports of at most 1,500 characters each. The discharge "
  "diagnosis, ICD codes and procedures are withheld. A test in the repository checks that no model input contains its case's "
  "discharge diagnosis. Synthetic example:")
p = doc.add_paragraph()
r = p.add_run(s_inputs[sorted(s_inputs)[0]][:900]); r.font.name = "Consolas"; r.font.size = Pt(8)
H("3.4.4  Feature matrix for the classical model", 3)
P("Model E uses a TF-IDF matrix of word 1- and 2-grams (up to 50,000 features, words only, sub-linear term frequency). The "
  "vocabulary is **fit on the training split only**, so no validation or test text leaks into the features.")

# ---------------------------------------------------------------- 3.5
H("3.5  Data Preparation", 2); author()
P("The split is fixed and versioned (`data/splits/ext_cdm_splits_v2.json`). It holds the **100-case held-out test set** named in "
  "the project abstract; 20% of the remaining cases go to validation and the rest to training. It is stratified by pathology "
  "with seed 298 and **grouped by patient**, so all admissions of one patient land in the same split. (Version 1 split by "
  "admission and let five patients cross splits; version 2 has none.) The file's SHA-256 is pinned in the evaluation protocol "
  "(`docs/evaluation_protocol.json`), and scoring refuses a changed split. The notebook re-checks both on every run: "
  "**hash matches, no case and no patient in two splits.**")
table(split, "Table 3.5-1. Train / validation / test splits (real data).")
P("Each split is exported as one table with one row per case: the case ID, the label, the model-input text and its length. "
  "Models A and E read these. The test split is not used anywhere in this report; it stays untouched until the team freezes "
  "Model A's settings.")
prep = pd.DataFrame({"hadm_id": list(s_inputs)[:3], "split": ["train", "val", "train"],
                     "pathology": s_tr["cases_master"].set_index("hadm_id").loc[list(s_inputs)[:3], "pathology"].values,
                     "model_input": [cut(s_inputs[h].replace("\n", " "), 60) for h in list(s_inputs)[:3]],
                     "input_chars": [len(s_inputs[h]) for h in list(s_inputs)[:3]]})
table(prep, "Table 3.5-2. Prepared dataset rows (synthetic sample).")

# ---------------------------------------------------------------- 3.6
H("3.6  Data Statistics", 2); author()
P(f"Table 3.6-1 follows the data through the four stages. Raw to pre-processed loses {raw_rows - pre_rows:,} rows: the "
  f"{n_dups} duplicates plus the 1,209-row lab mapping, which is joined into the lab table rather than kept as its own table. "
  "Transformation adds the case table and parsed columns; preparation produces the three splits.")
table(stage, "Table 3.6-1. Summary across raw, pre-processed, transformed and prepared data.", size=8)
figure("3_6a_class_balance_by_split.png", "Class balance by split. Stratification keeps each pathology's share the same in train, validation and test; appendicitis is 40% of cases, which is why macro-averaged metrics are reported.", "3.6.2")
figure("3_6b_missing_values.png", "Missing values by column after pre-processing (kept as missing, not imputed).", "3.6.2")
figure("3_6c_lab_flags_by_pathology.png", "Lab flags by pathology after transformation.", "3.6.2")
figure("3_6d_input_length.png", "Length of the model input by pathology (prepared data).", "3.6.2")
figure("3_6f_rows_removed.png", "Rows removed by pre-processing, by table.", "3.6.2")
figure("3_6e_rule_coverage.png", "Which of the 12 rules the record facts can test. Most facts are unknown in the records, and four rules (R-PAN-003, R-PAN-005, R-DIV-001, R-DIV-003) are never testable on these cases. This caps the verifier-based metric in section 4.4.", "3.6.2")

# ================================================================= 4
H("4  Model Development", 1)

# ---------------------------------------------------------------- 4.1
H("4.1  Model Proposals", 2); author()
P("We propose **five models** plus the reproduced published baseline. All five produce a structured plan (diagnosis, treatments, "
  "post-operative antibiotic days) that the Z3 verifier checks against the team's rule catalog (v2.1, 12 rules). Models A and E "
  "are built and evaluated in 298A (section 4.4); B, C and D are built in 298B.")
props = pd.DataFrame([
    ["A", "LLM plan generator", "An LLM writes the diagnosis and plan directly; the verifier checks it afterwards", "Decoder-only transformer: Qwen2.5-14B-Instruct, 4-bit, local; greedy decoding; output constrained to the plan JSON schema", "Model-input text", "298A (built)"],
    ["B", "LLM to formal specification", "The LLM translates the case into a formal specification; a solver does the reasoning", "LLM translation into SMT-LIB / Z3 facts + Z3 solve (Logic-LM [9], SatLM [14])", "Model-input text", "298B"],
    ["C", "Solver-in-the-loop repair (innovative)", "Model A, but every rejected plan goes back to the LLM with the broken rule's ID and message, for at most k rounds", "LLM + Z3 verifier as an external critic (LLM-Modulo [7])", "Model-input text + verifier feedback", "298B"],
    ["D", "LLM + classical planner", "The LLM maps the case to a PDDL problem; a classical planner builds a plan that satisfies the domain", "LLM translation + Fast Downward [5] on a hand-written clinical PDDL domain (LLM+P [8])", "Model-input text + domain model", "298B"],
    ["E", "Classical ML + guideline template", "A text classifier predicts the diagnosis; a fixed per-diagnosis template gives the treatment", "TF-IDF (1–2-grams) + multinomial logistic regression [10]", "TF-IDF matrix", "298A (built)"],
    ["—", "Reproduced baseline", "Hager et al. (2024) autonomous clinical decision making [3]", "OASST 70B (Llama 2 base) in the authors' framework", "Interactive information requests", "298A (needs a larger GPU)"],
], columns=["#", "Model", "Concept", "Architecture / algorithm", "Input", "Phase"])
table(props, "Table 4.1-1. Proposed models.", size=8, widths=(0.3, 1.1, 1.8, 1.9, 1.0, 0.7))
P("**Innovation (Model C).** No paper in our reviewed set closes the loop between an LLM and a formal verifier that uses "
  "team-written **clinical** rules. Model C returns the exact broken rule and its message to the LLM, which tests the "
  "LLM-Modulo claim [7] that an external, sound critic repairs plans better than self-critique (Valmeekam et al. [13] report "
  "88/100 with verifier feedback against 55/100 with self-critique on Blocksworld).")
P("**Why Model E was added.** Model E is a cheap statistical reference point. It runs in milliseconds on a CPU and produces class "
  "probabilities, so it is the only model with ROC curves and log loss. If E matches A on diagnosis, then any value the LLM adds "
  "must come from the plan, not the label. [[Team: confirm Model E as the fifth model.]]")
P("The **majority-class predictor** (always \"appendicitis\") is reported beside them as the floor every model must beat.")

# ---------------------------------------------------------------- 4.2
H("4.2  Model Supports", 2); author()
H("4.2.1  Platform, environment and tools", 3)
P("Everything that touches patient data runs on one local machine, as the data use agreement requires. The environment below was "
  "recorded by the notebook at run time.")
table(env, "Table 4.2-1. Measured environment.", widths=(1.8, 4.6))
kv([
    ["Model A serving", "Ollama 0.40.12 HTTP API on localhost; `qwen2.5:14b` Q4_K_M weights (digest 7cdf5a0187d5), 100% on the GPU, about 10 GB of 16 GB VRAM"],
    ["Model A decoding", "temperature 0, top_p 1, seed 298, at most 256 new tokens, 8,192-token context; output constrained by a JSON schema"],
    ["Model A prompt", f"fixed system + user template, SHA-256 `{prompt_sha[:16]}…` recorded with every run"],
    ["Model E training", "scikit-learn TfidfVectorizer + LogisticRegression; C chosen by 5-fold GridSearchCV on train (macro F1)"],
    ["Verifier", "Z3 SMT solver, rule catalog v2.1 (12 rules), strict mode for unknown facts"],
    ["Warehouse", "DuckDB single-file database (section 4.5)"],
    ["Quality", "pytest suite (135 tests) on every push in GitHub Actions; synthetic data only in CI"],
], "Table 4.2-2. Model configuration and supporting tools.")
H("4.2.2  Architecture and data flow", 3)
figure("4_2_platform_architecture.png", "Platform architecture. Credentialed data, models and verifier stay on the local machine; only code and aggregate results go to GitHub.", "4.2.2")
figure("4_2_ml_data_flow.png", "ML data flow for the two models built in 298A.", "4.2.3")

# ---------------------------------------------------------------- 4.3
H("4.3  Model Comparison and Justification", 2); author()
cmp = pd.DataFrame({
    "": ["Targeted problem", "Features", "Approach", "Strengths", "Limitations", "Justification"],
    "A: LLM generator": ["Can an LLM write a plan that passes the rules without help?", "Full record text", "Deep learning (transformer LLM, prompting)", "Simplest; no translation step; closest to the baseline paper", "No correction step; LLMs skip guideline treatment [3]; output can be unparseable", "The reference every other model is compared against"],
    "B: LLM → formal spec": ["Does moving reasoning into a solver make plans faithful to the case?", "Full record text", "Deep learning + symbolic (SMT)", "The explanation is the solver's proof; inconsistencies are caught", "Translation errors; the formal language must cover each disease", "Tests the Logic-LM / SatLM claim in a clinical setting"],
    "C: solver-in-the-loop": ["Can explicit rule feedback turn failing plans into passing ones?", "Record text + violated rule ID and message", "Deep learning + symbolic critic", "Uses the rule catalog directly and names the broken rule", "Repairs only what the rules cover; unknown facts give no feedback; extra generations cost time", "The project's main hypothesis (LLM-Modulo)"],
    "D: LLM + planner": ["Can plans be valid by construction?", "Record text + PDDL domain", "Deep learning + classical planning", "Planner output always satisfies the domain; auditable", "Needs a clinical PDDL domain, which does not exist; lab-conditional rules fit actions badly", "Tests LLM+P; shows where planning formalisms break"],
    "E: classical ML": ["How much does an LLM add over a cheap classifier?", "TF-IDF 1–2-grams", "Statistics / classical ML", "Fast, deterministic, calibrated probabilities and ROC; easy to explain", "Bag of words ignores negation and order; treatment is a fixed template", "A statistical floor for the LLM models"],
})
table(cmp, "Table 4.3-1. Comparison of the five models.", size=7.5)
P("All five are scored on the same fixed splits, with the same verifier and the same metrics, so only the method changes between "
  "them. The Hager et al. baseline is kept outside the five as the published reference; it measures autonomous diagnosis, a "
  "different task from plan validity.")
P(f"**What the 298A results already show.** On the validation split, Model A and Model E reach the **same diagnosis accuracy "
  f"({ma.accuracy:.3f})**, but Model E's plans pass the verifier more often (supported checked acceptance {me.supported_checked_acceptance_rate:.3f} "
  f"against {ma.supported_checked_acceptance_rate:.3f} for Model A). Model E's plan is a fixed guideline template, so it cannot omit a "
  "required treatment; Model A writes its own plan and sometimes does. This is the gap Model C is designed to close, and it "
  "supports building C rather than tuning A further.")

# ---------------------------------------------------------------- 4.4
H("4.4  Model Evaluation Methods", 2); author()
P("Metric definitions follow `docs/metrics.md` (evaluation protocol v1.1, frozen October 23, 2026). Every model is scored on the "
  "**validation split (460 cases)**. The 100-case test split is reserved for the formal test once Model A's settings are frozen.")
mt = pd.DataFrame([
    ["Diagnosis accuracy, per-pathology accuracy", "Classification", "All", "Share of cases with the right pathology"],
    ["Macro precision / recall / F1, confusion matrix", "Classification", "All", "Balanced over four classes (appendicitis is 40%)"],
    ["ROC-AUC (one-vs-rest), log loss", "Probabilistic", "E", "Ranking quality and calibration; an LLM's greedy output has no class probabilities"],
    ["Supported checked acceptance rate (primary)", "Verifier", "A–E", "Correct diagnosis + plan accepted + at least one decided blocking rule, over covered cases"],
    ["Plan status mix, violations by rule", "Verifier", "A–E", "Valid / violated / insufficient information, and which rules fail"],
    ["Unparseable / missing output rate", "Robustness", "A–D", "Outputs that cannot be scored count as failures"],
    ["Latency per case, tokens per second", "Cost", "A–E", "What a run costs"],
    ["Escape rate ≤ 0.05, adjudicated validity (goal 0.85)", "Human-labelled", "A–E", "Need independent plan labels; reported as unavailable until they exist"],
    ["Repair success rate, translation fidelity", "Secondary", "C, B", "298B"],
], columns=["Metric", "Type", "Models", "Meaning"])
table(mt, "Table 4.4-1. Evaluation metrics.", size=8)
H("4.4.1  Results on the validation split", 3)
res = comp[["model", "cases", "accuracy", "macro_f1", "macro_precision", "macro_recall", "roc_auc_macro_ovr", "log_loss",
            "supported_checked_acceptance_rate", "n_missing_outputs", "ms_per_case"]].rename(columns={
    "macro_f1": "macro F1", "macro_precision": "macro P", "macro_recall": "macro R", "roc_auc_macro_ovr": "ROC-AUC",
    "log_loss": "log loss", "supported_checked_acceptance_rate": "supported checked acceptance", "n_missing_outputs": "missing",
    "ms_per_case": "ms / case"})
res["ms / case"] = res["ms / case"].map(lambda v: "" if pd.isna(v) else f"{v:,.2f}" if v < 10 else f"{v:,.0f}")
table(res, "Table 4.4-2. Model comparison, validation split (460 cases).", size=8)
P(f"**Model E.** The regularisation strength was chosen by 5-fold cross-validation on the training split (macro F1 0.762 at C = 0.3 "
  f"rising to 0.831 at C = 30); the validation split was used once. It reaches accuracy {me.accuracy:.3f}, macro F1 {me.macro_f1:.3f}, "
  f"macro ROC-AUC {me.roc_auc_macro_ovr:.3f} and log loss {me.log_loss:.3f}, at {me.ms_per_case:.3f} ms per case.")
P(f"**Model A.** All 460 validation cases were generated in one fixed-cohort run (seed 298, 1,043 s, {ma.ms_per_case/1000:.1f} s and "
  f"about 21 output tokens/s per case on the RTX 5060 Ti). **No output was missing or unparseable**, and no case was retried. It "
  f"reaches accuracy {ma.accuracy:.3f} and macro F1 {ma.macro_f1:.3f}. Its plan file is "
  "`results/model_runs/model_a_qwen2.5_14b_val_seed298.jsonl` (case IDs and plan fields only).")
figure("4_4_accuracy_by_pathology.png", "Diagnosis accuracy by pathology, validation split.", "4.4.5")
figure("4_4_confusion_model_a.png", "Model A confusion matrix. Its most common error is predicting pancreatitis for cholecystitis (22 cases); both present with upper-abdominal pain and raised enzymes.", "4.4.4", width=4.2)
figure("4_4_confusion_model_e.png", "Model E confusion matrix.", "4.4.3", width=4.2)
figure("4_4_roc_model_e.png", "Model E ROC curves, one-vs-rest. Diverticulitis, the smallest class (49 validation cases), has the lowest AUC.", "4.4.3", width=4.5)
H("4.4.2  Verifier results for Model A", 3)
table(pd.DataFrame({"plan status": ["insufficient information", "violated", "valid"], "plans": [280, 123, 57]}),
      "Table 4.4-3. Model A plan status (460 plans).")
table(pd.DataFrame({"rule": ["R-GEN-001", "R-APP-003", "R-DIV-002", "R-APP-002", "R-PAN-002"], "violating plans": [106, 46, 14, 2, 1]}),
      "Table 4.4-4. Rules Model A's plans violate.")
P("Most plans end as **insufficient information**: the facts a rule needs are unknown in the record (Figure 3.6-6), so the "
  "verifier refuses to decide rather than guess. Among decided plans, the most common violation is R-GEN-001, followed by the "
  "complicated-appendicitis rule R-APP-003.")
H("4.4.3  Reading the numbers", 3)
bullets([
    "Diagnosis accuracy here is the **full-information** setting (the whole record at once). Hager et al.'s 54.9% for OASST 70B is the "
    "**autonomous** setting, where the model has to request each test, so the two numbers are not comparable.",
    "Supported checked acceptance has no numeric target in protocol v1.1. Even a perfect diagnosis cannot push it above roughly 23–25% on "
    "the covered cases, because most record facts are unknown. A low value is mostly a coverage limit of the records, not a model failure. "
    f"The majority-class floor is {mj.supported_checked_acceptance_rate:.3f}.",
    "Model A has no ROC curve or log loss: greedy LLM decoding returns a label without class probabilities. Model E covers those metrics.",
    "Escape rate and the 0.85 adjudicated validity need independent human plan labels. They are reported as unavailable, never estimated.",
    "Limitation: Model E's best C (30) is the largest value in the search grid, so a larger C might do slightly better. "
    "[[Widen the grid (e.g. up to 300) and rerun section 4.4.3 before the final submission.]]",
    "All numbers are from one validation run per model; the protocol's seeds 299 and 300 for Model A are planned for the formal test run.",
])

# ---------------------------------------------------------------- 4.5
H("4.5  Data Pipeline Demo: Ingestion, Transformation, Warehouse, Monitoring", 2); author()
P("The section 3 functions are packaged as one pipeline (`src/clinverify/warehouse.py`) that loads a local **DuckDB** warehouse "
  "(`MIMIC_DIR/warehouse/clinverify.duckdb`). DuckDB is a single-file analytical database [12]: it needs no server, and the data "
  "stays on the authorised machine. A command-line entry point (`scripts/run_pipeline.py`) runs the same function for scheduling.")
table(pd.DataFrame([
    ["raw", "Downloaded tables as read: 9 Ext-CDM tables, lab mapping, pathology labels, MIMIC-IV admission → patient map", "ingest"],
    ["staging", "Cleaned and transformed tables (deduplicated, normalised text, parsed and flagged labs)", "stage"],
    ["mart", "cases (one row per case, with split and patient), case_facts, model_inputs", "mart"],
    ["ops", "pipeline_runs, step_log, dq_results: counts only, no patient text", "every run"],
], columns=["Layer", "Contents", "Written by"]), "Table 4.5-1. Warehouse layers.")
figure("4_5_warehouse_lineage.png", "Warehouse lineage from source files through raw, staging and mart.", "4.5.2")
H("4.5.1  Ingestion and transformation", 3)
P(f"One run ingests {int(layers.loc[layers.layer == 'raw', 'rows'].sum()):,} raw rows (including 546,028 MIMIC-IV admissions for "
  "the patient map), stages and transforms them, builds the mart, and runs 14 data-quality checks, in about 5 seconds. Row counts "
  "reconcile across layers: for example `discharge_procedures` goes from 2,122 raw rows to 2,116 staged rows (5 duplicates and 1 "
  "empty procedure removed, as in section 3.3).")
lc = layers[layers.layer != "ops"].copy()
table(lc, "Table 4.5-2. Tables and rows per layer after the last run.", size=8)
H("4.5.2  Data-quality checks", 3)
table(dq, f"Table 4.5-3. Data-quality checks of the last clean run (run `{last_ok.run_id}`): 14 of 14 pass.", size=8)
P("**Quality gate.** The raw checks run in memory **before anything is written**. If one fails, nothing is published, the last good "
  "warehouse stays as it was, and the run is still logged.")
H("4.5.3  Monitoring and management", 3)
P(f"To demonstrate the gate, the notebook feeds the pipeline the corrupted copy from section 3.3.3. Run `{fault.run_id}` is caught by the "
  "gate in under a second, logged as `failed_checks`, and publishes nothing; the clean run that follows passes all checks. The run "
  "history in `ops.pipeline_runs` is what an alert or dashboard reads.")
h = hist.drop(columns=["finished_at"]).copy(); h["started_at"] = h["started_at"].str.slice(0, 19)
table(h, "Table 4.5-4. Run history (ops.pipeline_runs).", size=8)
figure("4_5_monitoring.png", "Pipeline monitoring: run duration and status (left), checks passed and failed per run (right). Runs 3 and 7 are the deliberate fault-injection runs.", "4.5.3")
H("4.5.4  Scheduling and alerting", 3)
P("`scripts/run_pipeline.py` exits with 0 when the run is ok, 1 when a check fails and 2 on an error, so any scheduler can alert on "
  "a non-zero exit. Nightly at 02:00 with cron on Linux / WSL:")
p = doc.add_paragraph(); r = p.add_run("0 2 * * * cd <repo> && MIMIC_DIR=$HOME/data/mimic .venv/bin/python scripts/run_pipeline.py --trigger cron >> $HOME/data/mimic/warehouse/cron.log 2>&1")
r.font.name = "Consolas"; r.font.size = Pt(8)
P("On Windows, Task Scheduler runs the same command through `wsl.exe`. `python scripts/run_pipeline.py --history` prints the run "
  "log at any time. A step-by-step live demo script is in `workbook/T6.A6_pipeline_demo.md`.")

# ================================================================= references
H("References", 1)
refs = [
    "de Moura, L., & Bjørner, N. (2008). Z3: An efficient SMT solver. Tools and Algorithms for the Construction and Analysis of Systems (TACAS), LNCS 4963, 337–340. https://doi.org/10.1007/978-3-540-78800-3_24",
    "Goldberger, A. L., Amaral, L. A. N., Glass, L., Hausdorff, J. M., Ivanov, P. C., Mark, R. G., Mietus, J. E., Moody, G. B., Peng, C.-K., & Stanley, H. E. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23), e215–e220.",
    "Hager, P., Jungmann, F., Holland, R., Bhagat, K., Hubrecht, I., Knauer, M., Vielhauer, J., Makowski, M., Braren, R., Kaissis, G., & Rueckert, D. (2024). Evaluation and mitigation of the limitations of large language models in clinical decision-making. Nature Medicine, 30, 2613–2622. https://doi.org/10.1038/s41591-024-03097-1",
    "[[Hager, P., et al. (2024). MIMIC-IV-Ext Clinical Decision Making (MIMIC-IV-Ext-CDM), version 1.1. PhysioNet. https://physionet.org/content/mimic-iv-ext-cdm/1.1/ — verify authors and title on the PhysioNet page.]]",
    "Helmert, M. (2006). The Fast Downward planning system. Journal of Artificial Intelligence Research, 26, 191–246.",
    "Johnson, A. E. W., Bulgarelli, L., Shen, L., et al. (2023). MIMIC-IV, a freely accessible electronic health record dataset. Scientific Data, 10, 1. https://doi.org/10.1038/s41597-022-01899-x",
    "Kambhampati, S., Valmeekam, K., Guan, L., Verma, M., Stechly, K., Bhambri, S., Saldyt, L. P., & Murthy, A. B. (2024). Position: LLMs can't plan, but can help planning in LLM-Modulo frameworks. ICML 2024, PMLR 235, 22895–22907.",
    "Liu, B., Jiang, Y., Zhang, X., Liu, Q., Zhang, S., Biswas, J., & Stone, P. (2023). LLM+P: Empowering large language models with optimal planning proficiency. arXiv:2304.11477.",
    "Pan, L., Albalak, A., Wang, X., & Wang, W. Y. (2023). Logic-LM: Empowering large language models with symbolic solvers for faithful logical reasoning. Findings of EMNLP 2023, 3806–3824.",
    "Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830.",
    "Qwen Team (2024). Qwen2.5 technical report. arXiv:2412.15115.",
    "Raasveldt, M., & Mühleisen, H. (2019). DuckDB: An embeddable analytical database. Proceedings of SIGMOD 2019, 1981–1984.",
    "Valmeekam, K., Marquez, M., & Kambhampati, S. (2023a). Can large language models really improve by self-critiquing their own plans? arXiv:2310.08118.",
    "Ye, X., Chen, Q., Dillig, I., & Durrett, G. (2023). SatLM: Satisfiability-aided language models using declarative prompting. NeurIPS 36. arXiv:2305.09656.",
]
for i, ref in enumerate(refs, 1):
    p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.35); p.paragraph_format.first_line_indent = Inches(-0.35)
    runs(p, f"[{i}]  {ref}", size=9.5)

# ================================================================= checklist
doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
P("**Submission checklist (not part of the report)**")
table(pd.DataFrame([
    ["Every section is written as report prose, not as notes", "Yes"],
    ["Every number comes from the run recorded in the notebook (run IDs, model digest, plan file named)", "Yes"],
    ["Every figure names the notebook section that produced it", "Yes"],
    ["No record text from MIMIC appears in this document (samples are synthetic)", "Yes"],
    ["Each section names the team member who wrote it", "[[No: fill the author lines]]"],
    ["Repository commit recorded on the title page", "[[No: commit the Workbook 2 code first]]"],
], columns=["Check", "Yes / No"]), widths=(5.2, 1.4))
P("**Self-assessment and gap register**")
table(pd.DataFrame([
    ["3.1–3.6 Data engineering", "[[rating]]", "", "", ""],
    ["4.1 Model proposals", "[[rating]]", "Team sign-off on Model E as the fifth model", "[[owner]]", "[[date]]"],
    ["4.2–4.3 Supports and comparison", "[[rating]]", "", "", ""],
    ["4.4 Evaluation", "[[rating]]", "Widen Model E's C grid; Model A seeds 299/300; human plan labels for escape rate", "[[owner]]", "[[date]]"],
    ["4.5 Pipeline demo", "[[rating]]", "Live demo rehearsal (workbook/T6.A6_pipeline_demo.md)", "[[owner]]", "[[date]]"],
], columns=["Report section", "Our rating", "If below good: what is missing", "Owner", "Lands by"]), size=8.5)

OUT.parent.mkdir(exist_ok=True)
doc.save(OUT)
print("wrote", OUT, f"({OUT.stat().st_size/1e6:.1f} MB)")
