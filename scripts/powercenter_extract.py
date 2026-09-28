#!/usr/bin/env python3
"""Parse Informatica PowerCenter XML repository exports and generate
POWERCENTER_INVENTORY.md and POWERCENTER_LINEAGE.md.

Stdlib only. Each export is a <POWERMART> document:
  REPOSITORY -> FOLDER -> SOURCE / TARGET / MAPPING / MAPPLET / WORKFLOW
Mappings carry <TRANSFORMATION> defs, <INSTANCE> nodes and <CONNECTOR> edges.
Workflows carry <SESSION>, <TASKINSTANCE> and <WORKFLOWLINK> elements.
"""

from collections import defaultdict, deque
from pathlib import Path
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
EXPORT_FILES = sorted((REPO / "XML").iterdir()) + [REPO / "Pseudossn"]
INVENTORY_MD = REPO / "POWERCENTER_INVENTORY.md"
LINEAGE_MD = REPO / "POWERCENTER_LINEAGE.md"
COMPLEXITY_MD = REPO / "POWERCENTER_COMPLEXITY.md"


def attrs(el, *names):
    return {n: el.get(n, "") for n in names}


def fields_of(el, tag):
    out = []
    for f in el.findall(tag):
        out.append(attrs(f, "NAME", "DATATYPE", "PRECISION", "SCALE",
                         "KEYTYPE", "NULLABLE", "FIELDNUMBER"))
    return out


def parse_export(path):
    tree = ET.parse(path)
    root = tree.getroot()
    repo = root.find("REPOSITORY")
    folder = root.find("REPOSITORY/FOLDER")
    exp = {
        "file": path.name,
        "rel": str(path.relative_to(REPO)),
        "repo": repo.get("NAME", ""), "repo_db": repo.get("DATABASETYPE", ""),
        "created": root.get("CREATION_DATE", ""),
        "folder": folder.get("NAME", ""), "owner": folder.get("OWNER", ""),
        "sources": [], "targets": [], "mappings": [], "mapplets": [],
        "sessions_folder": [], "workflows": [],
    }

    for child in folder:
        tag = child.tag
        if tag == "SOURCE":
            s = attrs(child, "NAME", "DATABASETYPE", "DBDNAME", "OWNERNAME",
                      "BUSINESSNAME", "DESCRIPTION")
            s["fields"] = fields_of(child, "SOURCEFIELD")
            ff = child.find("FLATFILE")
            s["flatfile"] = dict(ff.attrib) if ff is not None else None
            exp["sources"].append(s)
        elif tag == "TARGET":
            t = attrs(child, "NAME", "DATABASETYPE", "DESCRIPTION")
            t["fields"] = fields_of(child, "TARGETFIELD")
            exp["targets"].append(t)
        elif tag == "MAPPING":
            exp["mappings"].append(parse_mapping(child))
        elif tag == "MAPPLET":
            exp["mapplets"].append(parse_mapping(child, mapplet=True))
        elif tag == "SESSION":
            exp["sessions_folder"].append(parse_session(child))
        elif tag == "WORKFLOW":
            exp["workflows"].append(parse_workflow(child))
    return exp


def parse_mapping(el, mapplet=False):
    m = attrs(el, "NAME", "DESCRIPTION", "ISVALID")
    m["mapplet"] = mapplet
    m["vars"] = [attrs(v, "NAME", "DATATYPE", "ISPARAM", "DEFAULTVALUE")
                 for v in el.findall("MAPPINGVARIABLE")]
    m["transformations"] = [attrs(t, "NAME", "TYPE", "REUSABLE")
                            for t in el.findall("TRANSFORMATION")]
    # non-empty "Sql Query" overrides on SQ transformations
    m["sql_overrides"] = []
    for t in el.findall("TRANSFORMATION"):
        for ta in t.findall("TABLEATTRIBUTE"):
            if ta.get("NAME") == "Sql Query" and ta.get("VALUE"):
                m["sql_overrides"].append(t.get("NAME"))
    instances, order = {}, []
    for i, inst in enumerate(el.findall("INSTANCE")):
        name = inst.get("NAME", "")
        assoc = inst.find("ASSOCIATED_SOURCE_INSTANCE")
        post_sql = [ta.get("VALUE") for ta in inst.findall("TABLEATTRIBUTE")
                    if ta.get("NAME") in ("Pre SQL", "Post SQL") and ta.get("VALUE")]
        instances[name] = {
            "name": name,
            "ttype": inst.get("TRANSFORMATION_TYPE", ""),
            "itype": inst.get("TYPE", ""),
            "tname": inst.get("TRANSFORMATION_NAME", ""),
            "order": i,
            "assoc_src": assoc.get("NAME") if assoc is not None else None,
            "post_sql": post_sql,
        }
        order.append(name)
    edges, preds, succs = set(), defaultdict(set), defaultdict(set)
    for c in el.findall("CONNECTOR"):
        f, t = c.get("FROMINSTANCE"), c.get("TOINSTANCE")
        if f in instances and t in instances and (f, t) not in edges:
            edges.add((f, t)); preds[t].add(f); succs[f].add(t)
    # source instances feed their SQ via ASSOCIATED_SOURCE_INSTANCE (no CONNECTOR)
    for inst in instances.values():
        if inst["assoc_src"] and inst["assoc_src"] in instances:
            s = inst["assoc_src"]
            if (s, inst["name"]) not in edges:
                edges.add((s, inst["name"]))
                preds[inst["name"]].add(s); succs[s].add(inst["name"])
    m["instances"], m["edges"] = instances, edges
    m["preds"], m["succs"] = preds, succs
    m["order"] = topo_order(order, preds, succs)
    return m


def topo_order(order, preds, succs):
    """Kahn's algorithm, ties broken by original file order."""
    pos = {n: i for i, n in enumerate(order)}
    indeg = {n: 0 for n in order}
    for n in order:
        indeg[n] = len(preds.get(n, ()))
    ready = deque(sorted((n for n in order if indeg[n] == 0), key=pos.get))
    result = []
    while ready:
        n = ready.popleft()
        result.append(n)
        for s in sorted(succs.get(n, ()), key=pos.get):
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    # any leftover (cycle) appended in file order
    result += [n for n in order if n not in result]
    return result


def parse_session(el):
    s = attrs(el, "NAME", "MAPPINGNAME", "DESCRIPTION")
    conns, files, param_file = set(), {}, ""
    for cr in el.iter("CONNECTIONREFERENCE"):
        cn = cr.get("CONNECTIONNAME") or cr.get("VARIABLE")
        if cn:
            conns.add(cn)
    for a in el.iter("ATTRIBUTE"):
        n, v = a.get("NAME"), a.get("VALUE")
        if not v:
            continue
        if n == "Parameter Filename":
            param_file = v
        elif n in ("Source filename", "Output filename", "Merge File Name",
                   "Reject filename", "Lookup table name"):
            files[n] = v
    s["conns"] = sorted(conns)
    s["files"] = files
    s["param_file"] = param_file
    s["var_assign"] = any(vp.get("NAME", "").startswith("$$")
                          for vp in el.iter("VALUEPAIR"))
    return s


def parse_workflow(el):
    w = attrs(el, "NAME", "DESCRIPTION", "SCHEDULERNAME", "SERVERNAME",
              "ISENABLED", "SUSPEND_ON_ERROR")
    si = el.find("SCHEDULER/SCHEDULEINFO")
    w["schedule"] = si.get("SCHEDULETYPE", "") if si is not None else ""
    w["sessions"] = [parse_session(s) for s in el.findall("SESSION")]
    w["tasks"] = [attrs(t, "NAME", "TASKTYPE") for t in el.findall("TASKINSTANCE")]
    links = [(l.get("FROMTASK"), l.get("TOTASK"), l.get("CONDITION", ""))
             for l in el.findall("WORKFLOWLINK")]
    w["links"] = links
    w["order"] = task_order(w["tasks"], links)
    return w


def task_order(tasks, links):
    succ = defaultdict(list)
    for f, t, _ in links:
        succ[f].append(t)
    order, seen, cur = [], set(), ["Start"]
    while cur:
        nxt = []
        for n in cur:
            if n not in seen:
                seen.add(n); order.append(n)
                nxt += succ.get(n, [])
        cur = nxt
    for t in tasks:  # unlinked tasks
        if t["NAME"] not in seen:
            order.append(t["NAME"])
    return order


# ---------- rendering helpers ----------

def fmt_fields(fields):
    parts = []
    for f in fields:
        p, s = f["PRECISION"], f["SCALE"]
        dt = f["DATATYPE"].replace("(p,s)", "")  # exports store "number(p,s)" literally
        t = dt + (f"({p},{s})" if s not in ("", "0") else f"({p})" if p else "")
        key = f" [{f['KEYTYPE']}]" if f["KEYTYPE"] not in ("", "NOT A KEY") else ""
        parts.append(f"{f['NAME']} {t}{key}")
    return ", ".join(parts)


def inst_label(inst):
    label = f"{inst['name']} ({inst['ttype']})" if inst["ttype"] else inst["name"]
    return label


def node_chain(m):
    """Ordered transformation-chain string for a mapping."""
    parts = []
    for n in m["order"]:
        inst = m["instances"][n]
        tag = inst["itype"]
        if tag == "SOURCE":
            parts.append(f"**{inst['name']}**")
        elif tag == "TARGET":
            parts.append(f"__{inst['name']}__")
        else:
            parts.append(f"{inst['name']} <sub>{inst['ttype']}</sub>")
    return " → ".join(parts)


def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


# ---------- POWERCENTER_INVENTORY.md ----------

def build_inventory(exports):
    L = []
    a = L.append
    a("# PowerCenter Repository Inventory\n")
    a("Generated by `scripts/powercenter_extract.py` from the PowerCenter XML exports "
      "in this repo (repository format version 187.96, PowerCenter 9.6.1). "
      "Do not edit by hand — regenerate instead.\n")

    a("## Export Files\n")
    a("| File | Repository | Folder | Owner | Created |")
    a("|---|---|---|---|---|")
    for e in exports:
        a(f"| `{e['rel']}` | {e['repo']} ({e['repo_db']}) | {e['folder']} | "
          f"{e['owner']} | {e['created']} |")
    a("")
    a("> Note: `Pseudossn` (repo root) and `XML/Pseudossn` are byte-identical "
      "copies of the same `Prd_Repo_Srvc` export — the duplicate is inventoried "
      "below for completeness; totals count it twice. Also note the `CPM*` and "
      "`FDA_Leave` files are partial exports of the **same** `CPM` folder "
      "(from `Test_Repo_Srvc`), while `COMPTIME`, `LES`, `Pay_Calendar`, "
      "`Pseudossn` and `EHRP2BIIS_UPDATE` are their own folders.\n")

    a("## Object Counts by Export\n")
    a("| File | Sources | Targets | Mappings | Mapplets | Sessions | Workflows |")
    a("|---|---|---|---|---|---|---|")
    tot = defaultdict(int)
    for e in exports:
        nsess = len(e["sessions_folder"]) + sum(len(w["sessions"]) for w in e["workflows"])
        row = [e["file"], str(len(e["sources"])), str(len(e["targets"])),
               str(len(e["mappings"])), str(len(e["mapplets"])),
               str(nsess), str(len(e["workflows"]))]
        a("| " + " | ".join(row) + " |")
        for k, v in zip(("src", "tgt", "map", "mplt", "sess", "wf"), row[1:]):
            tot[k] += int(v)
    a(f"| **Total** | **{tot['src']}** | **{tot['tgt']}** | **{tot['map']}** | "
      f"**{tot['mplt']}** | **{tot['sess']}** | **{tot['wf']}** |\n")

    a("## Transformation Type Usage (all mapping instances)\n")
    a("| Type | Instances |")
    a("|---|---|")
    tc = defaultdict(int)
    for e in exports:
        for m in e["mappings"]:
            for inst in m["instances"].values():
                tc[inst["ttype"] or inst["itype"]] += 1
    for t, c in sorted(tc.items(), key=lambda x: -x[1]):
        a(f"| {t} | {c} |")
    a("")

    for e in exports:
        a(f"\n---\n\n## `{e['rel']}` — folder **{e['folder']}**\n")
        a(f"Repository: {e['repo']} ({e['repo_db']}) · exported {e['created']}\n")

        a(f"### Sources ({len(e['sources'])})\n")
        for s in e["sources"]:
            meta = ", ".join(x for x in (s["DATABASETYPE"], s["DBDNAME"],
                                         f"owner {s['OWNERNAME']}" if s["OWNERNAME"] else "")
                             if x)
            a(f"- **{s['NAME']}** — {meta} — {len(s['fields'])} fields")
            if s["flatfile"]:
                ff = s["flatfile"]
                a(f"  - Flat file: delimited={ff.get('DELIMITED')}, "
                  f"delimiters=`{ff.get('DELIMITERS')}`, "
                  f"line-sequential={ff.get('LINESEQUENTIAL')}, "
                  f"skip-rows={ff.get('SKIPROWS')}, codepage={ff.get('CODEPAGE')}")
            if s["fields"]:
                a(f"  - Fields: {fmt_fields(s['fields'])}")
        a("")

        a(f"### Targets ({len(e['targets'])})\n")
        for t in e["targets"]:
            a(f"- **{t['NAME']}** — {t['DATABASETYPE']} — {len(t['fields'])} fields")
            if t["fields"]:
                a(f"  - Fields: {fmt_fields(t['fields'])}")
        a("")

        a(f"### Mappings ({len(e['mappings'])})\n")
        a("| Mapping | Nodes | Transformation chain (topological order; "
          "**bold** = source, _italic_ = target) |")
        a("|---|---|---|")
        for m in e["mappings"]:
            flags = []
            if m["sql_overrides"]:
                flags.append("custom SQL")
            if any(v["ISPARAM"] == "YES" for v in m["vars"]):
                flags.append("$$ params")
            if any(i["post_sql"] for i in m["instances"].values()):
                flags.append("post-SQL")
            name = m["NAME"] + ("†" if flags else "")
            a(f"| `{md_escape(name)}` | {len(m['instances'])} | {node_chain(m)} |")
        a("")
        a("<sub>† = has custom SQL / parameter-file variables / post-SQL "
          "(see lineage doc)</sub>\n")

        if e["mapplets"]:
            a(f"### Mapplets ({len(e['mapplets'])})\n")
            for m in e["mapplets"]:
                a(f"- **{m['NAME']}** — {len(m['instances'])} nodes: {node_chain(m)}")
            a("")

        for w in e["workflows"]:
            a(f"### Workflow `{w['NAME']}`\n")
            a(f"- Schedule: **{w['schedule'] or 'none'}** · server: "
              f"{w['SERVERNAME']} · suspend-on-error: {w['SUSPEND_ON_ERROR']}")
            a(f"- Task order (from WORKFLOWLINKs): "
              + " → ".join(f"`{t}`" for t in w["order"]))
            nonsess = [t for t in w["tasks"] if t["TASKTYPE"] not in ("Session", "Start")]
            if nonsess:
                a("- Non-session tasks: " + ", ".join(
                    f"`{t['NAME']}` ({t['TASKTYPE']})" for t in nonsess))
            a("")
            a("| Session | Mapping | Connections | Files | Params |")
            a("|---|---|---|---|---|")
            for s in w["sessions"]:
                files = "; ".join(f"{k}={v}" for k, v in s["files"].items())
                prm = s["param_file"] or ("$$ vars" if s["var_assign"] else "")
                a(f"| `{s['NAME']}` | `{s['MAPPINGNAME']}` | "
                  f"{', '.join(s['conns']) or '—'} | {md_escape(files) or '—'} | "
                  f"{md_escape(prm) or '—'} |")
            a("")
        if e["sessions_folder"]:
            a("### Reusable / folder-level sessions\n")
            for s in e["sessions_folder"]:
                a(f"- `{s['NAME']}` → mapping `{s['MAPPINGNAME']}`")
            a("")

    a(ORCHESTRATION_MD)
    return "\n".join(L)


ORCHESTRATION_MD = r"""
---

## Shell-Script Orchestration

The repository has no embedded scheduler — every workflow is
`SCHEDULEINFO ONDEMAND`, so orchestration is external (cron / manual) and
uses three script families:

| Script family | Files | Pattern |
|---|---|---|
| **Outbound transfer** (`Transfer Scripts/*`) | `afps_transfer`, `cdc_transfer`, `fda_transfer`, `nih_cpm_transfer`, `nih_les_transfer`, `nih_transfer_les`, `oig_transfer` | All seven are clones of one template: take a filename arg, check it exists under `/data/BIISINT/data/int/out/{CPM|LES}/`, then `sftp sa-cdirect@m1csv301.hhs.gov` and `put` it into a per-agency outbound jail dir (`/opt/app/jail/sa-afps`, `sa-cdcusr`, `sa-nihbiisu`, `sa-oigusr`, …). Success/abort is reported via `mailx` to a fixed distribution list (muthiah/knight/williams/simon/cunningham/tran @hhs.gov). Called "Manually;cron" per script headers. |
| **File housekeeping** (`Maintenance Scripts/*`) | `archive_files`, `remove_file` | `archive_files` renames every file in a dir to `name_P<pp>.txt` (pay-period stamping, takes inputdir/dest/pp args); `remove_file` deletes a named file if present. Both manual/cron. |
| **SQL pre/post-load wrappers** (repo root) | `ehrp2biis_preload`, `ehrp2biis_afterload.sql`, `actstage_load` | ksh wrappers that set up the Informatica env (`INFA_HOME=/informatica/PowerCenter9.6.1`), read credentials from dotfiles (`$HOME/.use`, `.pw`, `.use1`, `.pw1`), and run `.sql` scripts via `$ORACLE_HOME/bin/sqlplus` — EHRP staging-table housekeeping around the `m_EHRP2BIIS_UPDATE` session. `mailx` notifications on success/failure. |

**End-to-end pattern:**
`agency flat files → Informatica workflow (ONDEMAND, triggered externally) →
Oracle staging tables in ORA_BIIS → flat-file/PowerExchange extracts →
/data/BIISINT/data/int/out/* → manual/cron `*_transfer` SFTP →
m1csv301.hhs.gov agency dropboxes → mailx confirmation`. Sessions also emit
email via `email_*` workflow tasks and `mailx` in the scripts — notification
is entirely SMTP-based, there is no scheduler dependency management beyond
`WORKFLOWLINK` status conditions within each workflow.
"""


# ---------- POWERCENTER_COMPLEXITY.md ----------

# Advanced-feature weights (points added per instance, on top of the node itself)
ADV_WEIGHTS = {"Lookup Procedure": 1, "Joiner": 3, "Aggregator": 2}

TIERS = ((40, "High"), (20, "Medium"), (0, "Low"))


def score_mapping(m, exp):
    """Migration-complexity score for one mapping.

    score = #transformation nodes  (TYPE=TRANSFORMATION or MAPPLET instances)
          + 2 × #source instances
          + feature points: 1×lookups, 3×joiners, 2×aggregators
    Flags below are reported but do not affect the score.
    """
    src_defs = {s["NAME"]: s for s in exp["sources"]}
    tgt_defs = {t["NAME"]: t for t in exp["targets"]}
    nodes, srcs, tgts = [], [], []
    tcount = defaultdict(int)
    for i in m["instances"].values():
        if i["itype"] == "SOURCE":
            srcs.append(i)
        elif i["itype"] == "TARGET":
            tgts.append(i)
        else:
            nodes.append(i)
            tcount[i["ttype"]] += 1
    score = (len(nodes) + 2 * len(srcs)
             + sum(w * tcount[k] for k, w in ADV_WEIGHTS.items()))
    flags = []
    if m["sql_overrides"]:
        flags.append("custom-SQL")
    if any(i["post_sql"] for i in m["instances"].values()):
        flags.append("post-SQL")
    if any(v["ISPARAM"] == "YES" for v in m["vars"]):
        flags.append("$$param")
    if mplt := tcount.get("Mapplet"):
        flags.append(f"mapplet×{mplt}")
    for t in ("Update Strategy", "Sequence", "Router", "Sorter", "Normalizer"):
        if tcount.get(t):
            flags.append(f"{t.split()[0].lower()}×{tcount[t]}")
    if any((src_defs.get(i["tname"] or i["name"]) or {}).get("DATABASETYPE")
           == "VSAM" for i in srcs):
        flags.append("VSAM-src")
    if any((tgt_defs.get(i["tname"] or i["name"]) or {}).get("DATABASETYPE")
           == "PWX_SEQ_NRDB2" for i in tgts):
        flags.append("PWX-tgt")
    tier = next(t for cut, t in TIERS if score >= cut)
    return {"score": score, "tier": tier, "trans": len(nodes),
            "src": len(srcs), "tgt": len(tgts),
            "lkp": tcount["Lookup Procedure"], "jnr": tcount["Joiner"],
            "agg": tcount["Aggregator"], "flags": flags}


def build_complexity(exports):
    rows = []
    for e in exports:
        for m in e["mappings"]:
            s = score_mapping(m, e)
            s.update({"mapping": m["NAME"], "export": e["file"]})
            rows.append(s)
    rows.sort(key=lambda r: (-r["score"], r["export"], r["mapping"]))

    L = []
    a = L.append
    a("# PowerCenter Migration Complexity Matrix\n")
    a("Generated by `scripts/powercenter_extract.py` — do not edit by hand.\n")
    a("## Scoring\n")
    a("```")
    a("score = #transformation nodes (incl. SQ, lookups, mapplet calls)")
    a("      + 2 × #source instances")
    a("      + 1 × lookups + 3 × joiners + 2 × aggregators")
    a("```")
    a("Transformation count is the dominant factor; each extra source adds "
      "integration surface (connection, reader, field mapping); lookups, "
      "joiners and aggregators carry extra weight because they need "
      "condition/group-by/sort logic that does not translate 1:1 in most "
      "target platforms. The Flags column reports additional migration "
      "hazards (custom SQL, post-SQL, external $$ params, VSAM/PWX endpoints, "
      "Update Strategy, Sequence Generator, mapplets) that do not affect the "
      "score.\n")
    a("## Tiers\n")
    a("| Tier | Score | Mappings |")
    a("|---|---|---|")
    for cut, t in TIERS:
        hi = f"≥ {cut}" if t == "High" else (
            f"{cut}–39" if t == "Medium" else "< 20")
        n = sum(1 for r in rows if r["tier"] == t)
        a(f"| **{t}** | {hi} | {n} |")
    a("")
    a(f"## All {len(rows)} mappings (sorted by score)\n")
    a("| # | Score | Tier | Mapping | Export | Trans | Src | Tgt | "
      "Lkp | Jnr | Agg | Flags |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        a(f"| {i} | {r['score']} | {r['tier']} | `{r['mapping']}` | "
          f"{r['export']} | {r['trans']} | {r['src']} | {r['tgt']} | "
          f"{r['lkp']} | {r['jnr']} | {r['agg']} | "
          f"{', '.join(r['flags']) or '—'} |")
    a("")
    return "\n".join(L)


# ---------- POWERCENTER_LINEAGE.md ----------

def build_lineage(exports):
    L = []
    a = L.append
    a("# PowerCenter Source → Target Lineage\n")
    a("Generated by `scripts/powercenter_extract.py`. For every mapping, source "
      "instances are listed with their connector-graph flow (topological order) "
      "to target instances. `<-` shows a node's direct upstream nodes, including "
      "connected lookups (inbound connectors carry lookup condition fields).\n")

    # cross-export object usage matrix (keyed by export file, not folder —
    # several files are partial exports of the same CPM folder)
    use_src, use_tgt = defaultdict(set), defaultdict(set)
    for e in exports:
        for m in e["mappings"]:
            for inst in m["instances"].values():
                if inst["itype"] == "SOURCE":
                    use_src[inst["tname"] or inst["name"]].add(e["file"])
                elif inst["itype"] == "TARGET":
                    use_tgt[inst["tname"] or inst["name"]].add(e["file"])
    shared = sorted(set(use_src) | set(use_tgt))
    a("## Object Reuse Matrix (table/file → export files using it)\n")
    a("| Object | Source in | Target in |")
    a("|---|---|---|")
    for name in shared:
        s, t = use_src.get(name, set()), use_tgt.get(name, set())
        if len(s | t) > 1 or (s and t):  # shared across files or read+written
            a(f"| `{name}` | {', '.join(sorted(s)) or '—'} | "
              f"{', '.join(sorted(t)) or '—'} |")
    a("")
    a("*Single-file, single-role objects omitted — see per-file sections.*")

    for e in exports:
        a(f"\n---\n\n## `{e['rel']}` — folder **{e['folder']}**\n")
        src_meta = {s["NAME"]: s for s in e["sources"]}
        tgt_meta = {t["NAME"]: t for t in e["targets"]}

        for m in e["mappings"]:
            insts = m["instances"]
            srcs = [i for i in insts.values() if i["itype"] == "SOURCE"]
            tgts = [i for i in insts.values() if i["itype"] == "TARGET"]
            a(f"\n### `{m['NAME']}` — {len(insts)} nodes "
              f"({len(srcs)} src / {len(tgts)} tgt)\n")
            if m["DESCRIPTION"]:
                a(f"{md_escape(m['DESCRIPTION'])}\n")

            def meta(n, meta_map):
                d = meta_map.get(n)
                if not d:
                    return ""
                bits = [d.get("DATABASETYPE", "")]
                if d.get("DBDNAME"):
                    bits.append(d["DBDNAME"])
                if d.get("OWNERNAME"):
                    bits.append(f"owner {d['OWNERNAME']}")
                return " — " + ", ".join(b for b in bits if b)

            a("- **Sources**: " + "; ".join(
                f"`{s['name']}`{meta(s['tname'] or s['name'], src_meta)}"
                for s in srcs))
            a("- **Targets**: " + "; ".join(
                f"`{t['name']}`{meta(t['tname'] or t['name'], tgt_meta)}"
                for t in tgts))
            flags = []
            if m["sql_overrides"]:
                flags.append("custom SQ SQL: " + ", ".join(
                    f"`{n}`" for n in m["sql_overrides"]))
            for inst in insts.values():
                if inst["ttype"] == "Update Strategy":
                    flags.append(f"Update Strategy `{inst['name']}`")
                if inst["post_sql"]:
                    flags.append(f"instance Pre/Post-SQL on `{inst['name']}`")
            for v in m["vars"]:
                if v["ISPARAM"] == "YES":
                    flags.append(f"external param `{v['NAME']}`")
            if any(i["itype"] == "MAPPLET" for i in insts.values()):
                flags.append("uses mapplet `" +
                             next(i["tname"] for i in insts.values()
                                  if i["itype"] == "MAPPLET") + "`")
            if flags:
                a("- **Flags**: " + " · ".join(flags))
            a("")
            a("```")
            for n in m["order"]:
                inst = insts[n]
                ups = sorted(m["preds"].get(n, ()),
                             key=lambda x: m["order"].index(x))
                arrow = f" <- {'|'.join(ups)}" if ups else ""
                a(f"{inst['ttype'] or inst['itype']:>20}  {n}{arrow}")
            a("```")
        a("")

    return "\n".join(L)


def main():
    exports = [parse_export(p) for p in EXPORT_FILES]
    INVENTORY_MD.write_text(build_inventory(exports), encoding="utf-8")
    LINEAGE_MD.write_text(build_lineage(exports), encoding="utf-8")
    COMPLEXITY_MD.write_text(build_complexity(exports), encoding="utf-8")

    nm = sum(len(e["mappings"]) for e in exports)
    ns = sum(len(e["sources"]) for e in exports)
    nt = sum(len(e["targets"]) for e in exports)
    nsess = sum(len(e["sessions_folder"]) + sum(len(w["sessions"]) for w in e["workflows"])
                for e in exports)
    nwf = sum(len(e["workflows"]) for e in exports)
    print(f"parsed {len(exports)} exports: {ns} sources, {nt} targets, "
          f"{nm} mappings, {nsess} sessions, {nwf} workflows")
    print(f"wrote {INVENTORY_MD.name}, {LINEAGE_MD.name} and {COMPLEXITY_MD.name}")


if __name__ == "__main__":
    main()
