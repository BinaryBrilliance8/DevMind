"""Rebuild the revised PDF from the preserved v2 PDF and recorded new results."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TITLE = "DevMind: Controller-Level Safeguards and Independent Verification for LLM Software-Engineering Agents"
ROOT = Path(__file__).resolve().parent


def replace_block(page, needle, replacement, *, rectangle=None, size=10.8, align=0):
    blocks = [b for b in page.get_text("blocks") if needle in b[4]]
    if len(blocks) != 1:
        raise ValueError(f"Expected exactly one source block: {needle}")
    block = blocks[0]
    original = fitz.Rect(block[:4])
    box = fitz.Rect(rectangle) if rectangle else original + (-1, -1, 1, 3)
    page.add_redact_annot(original + (-0.5, -0.5, 0.5, 0.5), fill=(1, 1, 1))
    page.apply_redactions(images=0, graphics=0)
    for offset in range(16):
        font_size = size - offset * 0.1
        shape = page.new_shape()
        remaining = shape.insert_textbox(
            box,
            replacement,
            fontsize=font_size,
            fontname="tiro",
            align=align,
            lineheight=1.08,
        )
        if remaining >= 0:
            shape.commit()
            return
    raise ValueError(f"Replacement does not fit: {needle}")


def supplement(path: Path):
    live = json.loads((ROOT / "results/live/summary.json").read_text())
    paths = json.loads((ROOT / "results/paths/summary.json").read_text())
    ink = colors.HexColor("#20332e")
    styles = {
        "title": ParagraphStyle(
            "title",
            fontName="Times-Bold",
            fontSize=17,
            leading=21,
            spaceAfter=15,
            textColor=ink,
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName="Times-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body", fontName="Times-Roman", fontSize=10.5, leading=14, spaceAfter=9
        ),
        "small": ParagraphStyle(
            "small", fontName="Times-Roman", fontSize=9, leading=11, spaceAfter=7
        ),
    }
    story = []

    def p(text, style="body"):
        story.append(Paragraph(text, styles[style]))

    def table(data, widths):
        rows = [
            [Paragraph(escape(str(cell)), styles["small"]) for cell in row]
            for row in data
        ]
        item = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0ed")),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.7, ink),
                    ("LINEBELOW", (0, -1), (-1, -1), 0.5, ink),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([item, Spacer(1, 10)])

    p("Supplement S. Reproducibility audit and new validation", "title")
    p("Revision dated 19 November 2026", "small")
    p("S.1 Evidence provenance", "heading")
    p(
        "The preceding main text preserves the controller study reported in the supplied v2 PDF. "
        "Its devmind_eval.py, figure-generation source and original raw results were not found in the "
        "provided workspace, Documents, Downloads, or the inspected DevMind ZIPs. The editable paper "
        "source was also unavailable. Consequently, Tables V-IX remain <b>historically reported, not "
        "independently reproduced</b> in this revision. Their internal arithmetic can be checked; "
        "their experimental provenance cannot be established from the PDF alone."
    )
    p(
        "This supplement contains new measurements with supplied scripts, raw records and checksums. "
        "It does not reconstruct missing measurements or retroactively validate the original study. "
        "The title, Section IV-D cross-reference and availability statement have been corrected. "
        "The original figures and historical numbers are retained rather than silently altered."
    )
    p("S.2 Live first-action experiment", "heading")
    p(
        "We queried Qwen2.5-Coder-1.5B-Instruct Q4_K_M through llama.cpp b12532 on CPU. Twelve "
        "issue prompts cover four themes (cache, truncation, unsigned tokens, reservation rollback), "
        "with three paraphrases per theme. Each prompt was sent once with aci-v1 and once with aci-v2; "
        "variant order alternated. Both used temperature 0, JSON-object output, a 3,000-output-token "
        "ceiling and the production Gateway/DECISION validator. The served context was 8,192 tokens. "
        "No repository code was executed and no patch was generated or graded."
    )
    rows = [["Prompt", "Requests", "Schema valid", "First plan", "Plan-gate refusal"]]
    for version, result in live["summary"].items():
        rows.append(
            [
                version,
                result["requests"],
                result["schema_valid"],
                result["first_plan"],
                result["plan_gate_refusal"],
            ]
        )
    table(rows, [88, 65, 90, 80, 145])
    p(
        "Table S1. First-action compliance on 12 paired prompts. A plan-gate refusal means a "
        "schema-valid first action other than plan, locate or read; it is calculated from the "
        "controller rule, not an executed repair-loop event.",
        "small",
    )
    p(
        "All aci-v1 responses proposed submit before a plan. All aci-v2 responses proposed a valid plan. "
        "The revised prompt contains an explicit workflow reminder and plan example. This small, "
        "paired diagnostic supports that prompt change for these inputs; it does not establish a "
        "general compliance rate, model superiority or issue-resolution performance. An earlier "
        "single live check produced a nine-step plan rejected by the eight-step schema, so "
        "the 12/12 result is not a universal-validity claim."
    )
    story.append(PageBreak())
    p("Supplement S. Validation results and limits", "title")
    p("S.3 Path-validation defect and correction", "heading")
    p(
        "The pre-revision safe_name predicate accepted the string '.'. Although downstream directory "
        "operations reject it, the snapshot/name contract should reject it directly. The code now "
        "adds an explicit name == '.' rejection. A regression test covers safe_name, snapshot "
        "validation and Computer.resolve. The pre-fix predicate is retained only in the study script."
    )
    p(
        "A new seed-20261119 corpus contains 20,000 strings, each formed by concatenating zero to six "
        "tokens from a published 20-token list. An independent string-component oracle rejects "
        "empty, dot, parent, .git, non-canonical separator, NUL and backslash forms without using "
        "pathlib. Every input and outcome is stored. This is a new corpus: its counts must not be "
        "substituted for the historical 167 false accepts or 14,329 ablation disagreements."
    )
    table(
        [
            ["Predicate", "Accepted", "False accepts", "False rejects"],
            [
                "Before fix",
                paths["before"]["accepted"],
                paths["before"]["false_accepts"],
                paths["before"]["false_rejects"],
            ],
            [
                "After fix",
                paths["after"]["accepted"],
                paths["after"]["false_accepts"],
                paths["after"]["false_rejects"],
            ],
        ],
        [138, 100, 115, 115],
    )
    p(
        "Table S2. Paired path-oracle comparison on exactly the same new corpus. Every pre-fix "
        "disagreement is '.'. Zero disagreements in this finite corpus is not a proof of path safety.",
        "small",
    )
    p("S.4 Executed code checks and blocked integration", "heading")
    p(
        "The revised project recorded <b>47 passed and 3 skipped</b> pytest cases (4.66 seconds) on "
        "Python 3.14/macOS ARM64. The added checks cover dot rejection, retention of an invalid "
        "provider response for explicit research, and refusal to start a repair when preflight "
        "dependencies fail. A non-failing Starlette/httpx deprecation warning remains."
    )
    table(
        [
            ["Gate", "Observed outcome"],
            ["Local inference", "24 real completions; all raw responses preserved"],
            ["Docker VM startup", "Blocked: macOS boot-session inspection denied"],
            [
                "PostgreSQL 17.12 initdb",
                "Blocked: shmget shared-memory creation denied",
            ],
            [
                "Production repair preflight",
                "Exit 2; Docker/image unavailable; no host fallback",
            ],
            [
                "Docker / PostgreSQL tests",
                "One Docker and two PostgreSQL tests skipped",
            ],
            ["Official SWE-bench", "Not executed; no resolution score"],
        ],
        [160, 308],
    )
    p(
        "The Docker and PostgreSQL failures were re-observed during this revision and their logs are "
        "included. They are environmental blockers, not evidence that the implementations pass. "
        "The live_repair.py launcher uses a new dedicated SQL database, the real Runner and Docker "
        "boundary, and preserves run events and patches only after preflight succeeds. Its "
        "successful execution path remains unverified here."
    )
    story.append(PageBreak())
    p("Supplement S. Reproduction and release boundary", "title")
    p("S.5 Artifact map", "heading")
    table(
        [
            ["Artifact under research/paper_revision/", "Purpose"],
            [
                "live_actions.py; results/live/",
                "Exact prompts, provider responses, counts and timings",
            ],
            [
                "path_study.py; results/paths/",
                "Seeded inputs, oracle decisions, before/after results",
            ],
            [
                "live_repair.py; tasks.example.jsonl",
                "Docker-only production-path evaluation launcher",
            ],
            [
                "results/*-attempt.log",
                "Actual Docker VM and PostgreSQL startup failures",
            ],
            [
                "results/repair-preflight/preflight.json",
                "Real dependency checks before repair execution",
            ],
            [
                "baseline-provenance.json; MANIFEST.json",
                "Source, input-paper and artifact hashes",
            ],
            [
                "source-paper-v2.pdf; build_paper.py",
                "Preserved source PDF and deterministic revision recipe",
            ],
            ["README.md", "Setup and exact reproduction commands"],
        ],
        [255, 213],
    )
    p(
        "Raw live records include prompt messages and provider output, including invalid proposals "
        "if any occur. The Gateway retains the latest response in memory but does not add it to "
        "public API responses or automatic logs. Research persistence is explicit in the study script."
    )
    p("S.6 Availability and what remains", "heading")
    p(
        "The local project archive accompanies this revision. No authenticated GitHub repository "
        "or Zenodo record was available, and <b>no public archive URL or DOI is asserted</b>. "
        "Public artifact availability remains incomplete. The historical devmind_eval.py and raw "
        "v2 data remain missing; the newly supplied scripts are not replacements for their provenance."
    )
    p(
        "For a defensible empirical submission, reproduce or replace the historical studies with "
        "fully archived inputs and outputs, run the real PostgreSQL concurrency and Docker isolation "
        "gates, and evaluate complete live-model repair trajectories on a declared dataset. "
        "Pre-register budgets and report all attempted instances, infrastructure errors and empty "
        "patches. Official SWE-bench outcomes must come from its independent harness, not local "
        "test success. Acceptance at any venue is not claimed."
    )
    p(
        "Neither first-action compliance nor finite controller tests establish production readiness. "
        "The code remains a research platform with documented deployment and evaluation gates."
    )
    p("S.7 Model and runtime provenance", "heading")
    p(
        "Model revision: f86cb2c1fa58255f8052cc32aeede1b7482d4361. Model and runtime file hashes "
        "are recorded in docs/model-provenance.json. The new script and result hashes are in "
        "MANIFEST.json; no model weights or credentials are distributed in the project archive."
    )
    p(
        '<link href="https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF">Official Qwen model repository</link>; '
        '<link href="https://github.com/ggml-org/llama.cpp/releases/tag/b12532">llama.cpp b12532 release</link>. '
        "Sources checked on 19 November 2026.",
        "small",
    )

    def footer(canvas, doc):
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(306, 39, str(12 + doc.page))
        canvas.setFont("Times-Italic", 8)
        canvas.drawString(
            72, 760, "DevMind - new validation supplement, 19 November 2026"
        )

    SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=72,
        rightMargin=72,
        topMargin=65,
        bottomMargin=65,
    ).build(story, onFirstPage=footer, onLaterPages=footer)


def build(output: Path):
    source = ROOT / "source-paper-v2.pdf"
    document = fitz.open(source)
    replace_block(
        document[0],
        "DevMind: An LLM-Based",
        TITLE,
        rectangle=(72, 66, 540, 122),
        size=16,
        align=1,
    )
    abstract = (
        "Abstract - DevMind places a typed interface, controller-owned patches, independent "
        "verification, protected paths and leased execution around a software-engineering agent. "
        "The supplied v2 manuscript reports 96 scripted runs, path and schema fuzzing, 600 "
        "random-policy runs, source-level ablations and a scaling study. Its original scripts "
        "and raw results were unavailable for this revision; the historical tables are therefore "
        "preserved as reported, not independently reproduced. We add two reproducible studies. "
        "In 24 real CPU-model completions on 12 paired issue prompts, aci-v1 produced no initial "
        "plans and aci-v2 produced 12 schema-valid initial plans. This measures first-action "
        "compliance, not repair accuracy. A new 20,000-string path corpus reproduced 151 false "
        "accepts for the name '.', and an explicit rejection eliminated disagreements on that "
        "corpus. The revised code passed 47 tests; three Docker/PostgreSQL cases remained skipped "
        "because platform restrictions prevented startup. Supplement S supplies methods, raw "
        "records, source hashes and limitations. No successful live-model repair, official "
        "SWE-bench score, container-isolation result or production-readiness claim is made."
    )
    replace_block(
        document[0], "Abstract", abstract, rectangle=(99, 259, 514, 489), size=11
    )
    block = next(b for b in document[5].get_text("blocks") if "Section F adds" in b[4])
    text = " ".join(block[4].split()).replace(
        "Section F adds", "Section IV-E and Section V-F add"
    )
    replace_block(document[5], "Section F adds", text, size=10.8)
    replace_block(
        document[1],
        "The evaluation script and its raw results accompany",
        "Historical scripts/raw results were not supplied; new artifacts accompany Supplement S.",
        rectangle=(72, 710, 540, 735),
        size=9,
    )
    lease_block = next(
        b
        for b in document[4].get_text("blocks")
        if "worker renews the lease every third" in b[4]
    )
    lease_text = " ".join(lease_block[4].split()).replace(
        "worker renews the lease every third of its length",
        "worker renews at intervals of min(1 second, one third of the lease length)",
    )
    replace_block(
        document[4], "worker renews the lease every third", lease_text, size=10.7
    )
    availability = (
        "The v2 scripts were not supplied for this revision. They import the unmodified DevMind "
        "sources for the main studies and generate temporary mutated copies for the ablations. "
        "Supplement S documents the new artifacts. No public archive URL is established."
    )
    replace_block(
        document[10],
        "They import",
        availability,
        rectangle=(72, 474, 540, 512),
        size=10,
    )
    # Clarify the scope of unchanged-code language in the historical main study.
    block = next(
        b for b in document[4].get_text("blocks") if "We run the project" in b[4]
    )
    text = " ".join(block[4].split())
    text = text.replace(
        "We run the project’s own", "For the main studies, we run the project’s own"
    )
    replace_block(document[4], "We run the project", text, size=10.7)
    for page in document:
        page.insert_textbox(
            fitz.Rect(72, 28, 540, 50),
            "REVISED DRAFT | Historical main-study results not independently reproduced; see Supplement S",
            fontsize=7,
            fontname="helv",
            color=(0.3, 0.35, 0.33),
            align=1,
        )
    with tempfile.TemporaryDirectory() as temp:
        supplemental = Path(temp) / "supplement.pdf"
        supplement(supplemental)
        with fitz.open(supplemental) as extra:
            document.insert_pdf(extra)
    document.set_metadata(
        {
            "title": TITLE,
            "subject": "Revised historical study with new reproducible validation",
            "author": "DevMind project authors",
            "keywords": "controller safeguards; reproducibility; LLM agents",
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output, garbage=4, deflate=True)
    document.close()
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)
