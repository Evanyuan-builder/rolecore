#!/usr/bin/env python3
"""RoleCore CLI — 岗位资产管理系统命令行入口"""

import argparse
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rolecore import create_default_engine
from rolecore.utils.schema_validator import SchemaValidator


def _engine():
    return create_default_engine()


# ─── role ──────────────────────────────────────────────────────────────────────

def cmd_role_create(args):
    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    with open(args.file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    rm, _, _ = _engine()
    role = rm.create_role(data, version=args.version or "1", author=args.author or "system")
    print(f"Created: {role.role_id} v{role.version}")


def cmd_role_get(args):
    rm, _, _ = _engine()
    role = rm.get_role(args.id, version=args.version or "latest")
    i = role.identity
    print(f"Role: {role.role_id} v{role.version}")
    print(f"  {i.name_cn} / {i.name_en}")
    print(f"  Domain: {i.domain}")
    print(f"  Status: {role.meta.status}")
    print(f"  Tags: {', '.join(role.meta.tags)}")
    if args.full:
        print("\n--- Full YAML ---")
        print(yaml.dump(role.to_dict(), allow_unicode=True, sort_keys=False))


def cmd_role_list(args):
    rm, _, _ = _engine()
    status = args.status or "live"
    roles = rm.list_roles(group=args.group, status=status)
    if not roles:
        print("No roles found.")
        return
    print(f"{'ID':<45} {'中文名':<16} {'Status':<14} {'Latest'}")
    print("-" * 90)
    for e in roles:
        print(f"{e.role_id:<45} {e.name_cn:<16} {e.meta.status:<14} v{e.latest_version}")


def cmd_role_update(args):
    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    with open(args.file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    rm, _, _ = _engine()
    role = rm.update_role(args.id, data, new_version=args.version, description=args.desc or "")
    print(f"Updated: {role.role_id} → v{role.version}")


def cmd_role_set_latest(args):
    rm, _, _ = _engine()
    rm.set_latest(args.id, args.version)
    print(f"Set latest: {args.id} → v{args.version}")


def cmd_role_promote(args):
    rm, _, _ = _engine()
    new_status = rm.promote_status(args.id, args.to)
    print(f"Promoted: {args.id} → {new_status}")


def cmd_role_gate(args):
    rm, _, _ = _engine()
    gaps = rm.check_official_gate(args.id)
    if not gaps:
        print(f"PASS — '{args.id}' meets official gate requirements")
    else:
        print(f"FAIL — {len(gaps)} gap(s) for '{args.id}':")
        for g in gaps:
            print(f"  • {g}")
        sys.exit(1)


def cmd_role_mark_enhanced(args):
    rm, _, _ = _engine()
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    rm.mark_enhanced_fields(args.id, fields)
    print(f"Marked enhanced: {args.id} → {fields}")


def cmd_role_unmark_enhanced(args):
    rm, _, _ = _engine()
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    rm.unmark_enhanced_fields(args.id, fields)
    print(f"Unmarked enhanced: {args.id} → {fields}")


def cmd_role_deprecate(args):
    rm, _, _ = _engine()
    rm.deprecate_role(args.id)
    print(f"Deprecated: {args.id}")


def cmd_role_delete(args):
    rm, _, _ = _engine()
    rm.delete_role(args.id, version=args.version)
    if args.version:
        print(f"Deleted: {args.id} v{args.version}")
    else:
        print(f"Deleted: {args.id} (all versions)")


def cmd_role_validate(args):
    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    with open(args.file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    errors = SchemaValidator().validate(data)
    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("OK — schema valid")


def cmd_role_versions(args):
    rm, _, _ = _engine()
    versions = rm.get_versions(args.id)
    print(f"{args.id} versions: {', '.join('v' + v for v in versions)}")


# ─── search ────────────────────────────────────────────────────────────────────

def cmd_search(args):
    _, se, _ = _engine()

    if args.list_groups:
        groups = se.get_all_groups()
        print("Groups: " + ", ".join(groups) if groups else "No groups.")
        return

    if args.list_tags:
        tags = se.get_all_tags()
        print("Tags: " + ", ".join(tags) if tags else "No tags.")
        return

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
    results = se.search(
        group=args.group,
        tags=tags,
        keyword=args.keyword,
        tag_match_mode=args.tag_match or "any",
        status=args.status or "active",
    )

    if not results:
        print("No results.")
        return

    print(f"Found {len(results)} role(s):")
    for e in results:
        print(f"  {e.role_id:<45} {e.name_cn:<16} tags: {', '.join(e.tags)}")


# ─── find (cross-axis fusion search) ───────────────────────────────────────────

def cmd_find(args):
    from rolecore import create_fusion_engine
    fse = create_fusion_engine()
    result = fse.find(
        query=args.query,
        top_k_per_axis=args.top_k,
        status_filter=args.status,
    )

    if args.json:
        payload = {
            "query": result["query"],
            "tokens": result["tokens"],
            "status_filter": result["status_filter"],
            "job": [h.to_dict() for h in result["job"]],
            "tech": [h.to_dict() for h in result["tech"]],
            "specialty": [h.to_dict() for h in result["specialty"]],
            "triad": {
                axis: (h.to_dict() if h else None)
                for axis, h in result["triad"].items()
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"Query: {result['query']}   tokens: {result['tokens']}   status: {result['status_filter']}")
    any_hit = False
    for axis_key, label in [("job", "岗位维度"), ("tech", "技术栈维度"), ("specialty", "专业特长维度")]:
        hits = result[axis_key]
        print(f"\n{label} ({axis_key}) — {len(hits)} hit(s)")
        if not hits:
            print("  (no match)")
            continue
        any_hit = True
        for h in hits:
            e = h.entry
            label_cn = e.name_cn or "(空)"
            print(f"  [{h.score:>5.1f}] {e.role_id:<50} {label_cn:<20} {e.name_en}")
            print(f"          matched: {', '.join(h.matched_fields)}")

    print("\nTriad — 融合三维最佳组合:")
    for axis_key, label in [("job", "岗位"), ("tech", "技术栈"), ("specialty", "专业特长")]:
        h = result["triad"].get(axis_key)
        if not h:
            print(f"  {label:<6}: —")
        else:
            e = h.entry
            print(f"  {label:<6}: {e.role_id:<50} {e.name_cn or '(空)':<20} (score {h.score:.1f})")

    if not any_hit:
        sys.exit(2)


# ─── export ────────────────────────────────────────────────────────────────────

def cmd_export(args):
    rm, se, _ = _engine()
    fmt = args.format or "prompt"

    role_ids = []
    if args.id:
        role_ids = [args.id]
    elif args.group:
        entries = se.search_by_group(args.group)
        role_ids = [e.role_id for e in entries]

    if not role_ids:
        print("Error: specify --id or --group", file=sys.stderr)
        sys.exit(1)

    from rolecore.exporters.prompt_exporter import PromptExporter
    from rolecore.exporters.json_exporter import JsonExporter
    from rolecore.exporters.markdown_exporter import MarkdownExporter

    for role_id in role_ids:
        role = rm.get_role(role_id, version=args.version or "latest")

        if fmt == "prompt":
            output = PromptExporter().export(role, task="(无任务)", goal="(无目标)")
        elif fmt == "json":
            output = JsonExporter().to_json_string(
                JsonExporter().export(role, task="", goal="")
            )
        elif fmt == "markdown":
            output = MarkdownExporter().export(role)
        else:
            print(f"Unknown format: {fmt}", file=sys.stderr)
            sys.exit(1)

        if args.output:
            out_path = args.output
            if len(role_ids) > 1:
                base, ext = os.path.splitext(args.output)
                out_path = f"{base}_{role_id.replace('.', '_')}{ext}"
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Exported: {role_id} → {out_path}")
        else:
            print(output)


# ─── assemble ──────────────────────────────────────────────────────────────────

def cmd_assemble(args):
    rm, _, _ = _engine()
    from rolecore.core.assembler import Assembler
    assembler = Assembler(rm)

    context = {}
    if args.context:
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError as e:
            print(f"Error parsing --context JSON: {e}", file=sys.stderr)
            sys.exit(1)

    ac = assembler.assemble(
        role_id=args.id,
        task=args.task,
        goal=args.goal,
        context=context,
        version=args.version or "latest",
        export_format=args.format or "prompt",
    )

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            if args.format == "json":
                f.write(ac.prompt)
            else:
                f.write(ac.prompt)
        print(f"Assembled: {args.id} v{ac.version} → {args.output}")
    else:
        print(ac.prompt)


# ─── registry ──────────────────────────────────────────────────────────────────

def cmd_registry_stats(args):
    from rolecore import create_default_engine
    _, _, _ = create_default_engine()
    from rolecore import _REGISTRY_PATH
    from rolecore.storage.registry_store import RegistryStore
    from rolecore.models.role import normalize_status
    rs = RegistryStore(_REGISTRY_PATH)
    data = rs.load()
    roles = data.get("roles", {})
    groups = data.get("groups", {})
    tags = data.get("tag_index", {})

    from collections import Counter
    status_counts = Counter(
        normalize_status(e.get("meta", {}).get("status", "raw_imported"))
        for e in roles.values()
    )

    pipeline_order = ["raw_imported", "normalized", "curated", "official", "archived"]
    total = len(roles)

    print(f"Registry stats:")
    print(f"  Total roles:  {total}")
    print()
    print(f"  Status pipeline:")
    for s in pipeline_order:
        count = status_counts.get(s, 0)
        bar = "█" * count if count <= 40 else "█" * 40 + f"…+{count - 40}"
        print(f"    {s:<16} {count:>4}  {bar}")
    print()
    print(f"  Groups:       {len(groups)}")
    print(f"  Unique tags:  {len(tags)}")


def cmd_registry_rebuild(args):
    from rolecore import _REGISTRY_PATH
    from rolecore.storage.registry_store import RegistryStore
    rs = RegistryStore(_REGISTRY_PATH)
    rs.rebuild_tag_index()
    print("Tag index rebuilt.")


def cmd_registry_dump(args):
    from rolecore import _REGISTRY_PATH
    from rolecore.storage.registry_store import RegistryStore
    rs = RegistryStore(_REGISTRY_PATH)
    data = rs.load()
    fmt = args.format or "json"
    if fmt == "yaml":
        print(yaml.dump(data, allow_unicode=True, sort_keys=False))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_registry_resync(args):
    """Re-populate denormalized registry fields (name_cn/name_en/domain/tags/status)
    from each role's YAML. Use after direct YAML edits that bypass update_role."""
    rm, _, _ = _engine()
    from rolecore import _REGISTRY_PATH
    from rolecore.storage.registry_store import RegistryStore
    rs = RegistryStore(_REGISTRY_PATH)
    data = rs.load()
    total = len(data["roles"])
    touched = 0
    fields_touched = {"name_cn": 0, "name_en": 0, "domain": 0, "tags": 0, "status": 0}
    for role_id in list(data["roles"].keys()):
        changes = rm.resync_entry_from_yaml(role_id)
        if changes:
            touched += 1
            for k in changes:
                if k in fields_touched:
                    fields_touched[k] += 1
    print(f"Resynced {touched}/{total} entries from YAML")
    for k, n in fields_touched.items():
        if n:
            print(f"  {k}: {n} updated")


def cmd_registry_verify(args):
    from rolecore import _REGISTRY_PATH
    from rolecore.storage.registry_store import RegistryStore
    rs = RegistryStore(_REGISTRY_PATH)
    data = rs.load()
    issues = []
    for role_id, entry in data["roles"].items():
        for ver, ve in entry.get("versions", {}).items():
            path = ve.get("file_path", "")
            if not os.path.exists(path):
                issues.append(f"Missing file: {role_id} v{ver} → {path}")
    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print(f"OK — registry verified ({len(data['roles'])} roles, all files present)")


# ─── review (LLM-assisted quality review) ─────────────────────────────────────

def _reviewer():
    from rolecore.core.reviewer import Reviewer
    rm, _, _ = _engine()
    return Reviewer(rm)


def cmd_review_prompt(args):
    r = _reviewer()
    prompt = r.build_prompt(args.id)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("# System\n" + prompt["system"] + "\n\n# User\n" + prompt["user"])
        print(f"Prompt written: {args.output}")
    else:
        print("=== SYSTEM ===")
        print(prompt["system"])
        print("\n=== USER ===")
        print(prompt["user"])


def cmd_review_run(args):
    from rolecore.core.reviewer import Reviewer
    rm, _, _ = _engine()

    backend = args.backend or "anthropic"
    default_model = "qwen3:8b" if backend == "ollama" else "claude-opus-4-7"
    model = args.model or default_model

    if backend == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY") and not args.force:
        print("ANTHROPIC_API_KEY not set. Use `review prompt` for offline mode,",
              file=sys.stderr)
        print("switch to --backend ollama, or pass --force to attempt anyway.",
              file=sys.stderr)
        sys.exit(2)

    r = Reviewer(rm, model=model, backend=backend,
                 ollama_url=args.ollama_url or "http://localhost:11434")
    try:
        record = r.run_live(args.id)
    except Exception as e:
        print(f"Live review failed: {e}", file=sys.stderr)
        sys.exit(1)
    r.attach_record(args.id, record)
    print(f"Reviewed: {args.id} — verdict={record.verdict} score={record.score}")
    for s in record.strengths:
        print(f"  + {s}")
    for s in record.issues:
        print(f"  - {s}")


def cmd_review_apply(args):
    """Attach a manually authored review (or one loaded from a JSON file)."""
    from rolecore.core.reviewer import Reviewer, parse_review_response
    rm, _, _ = _engine()
    r = Reviewer(rm)

    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            text = f.read()
        record = parse_review_response(text)
        record.reviewer_model = args.reviewer or record.reviewer_model or "external-llm"
        r.attach_record(args.id, record)
    else:
        if not args.verdict or args.score is None:
            print("Error: either --from-file OR both --verdict and --score required",
                  file=sys.stderr)
            sys.exit(1)
        r.attach_manual(
            role_id=args.id,
            verdict=args.verdict,
            score=args.score,
            strengths=[s for s in (args.strengths or "").split("|") if s],
            issues=[s for s in (args.issues or "").split("|") if s],
            fix_hints=[s for s in (args.fix_hints or "").split("|") if s],
            reviewer_model=args.reviewer or "human",
        )
    print(f"Review attached to '{args.id}'")


def cmd_review_batch(args):
    """Batch review with skip-if-reviewed. Idempotent + resumable."""
    import time
    from collections import Counter
    from rolecore.core.reviewer import Reviewer, get_review_record
    from rolecore import _REGISTRY_PATH, _ROLES_DIR
    from rolecore.storage.registry_store import RegistryStore
    from rolecore.storage.role_store import RoleStore
    from rolecore.utils.path_utils import role_id_to_parts

    rm, _, _ = _engine()
    backend = args.backend or "ollama"
    default_model = "qwen3:8b" if backend == "ollama" else "claude-opus-4-7"
    model = args.model or default_model

    r = Reviewer(rm, model=model, backend=backend,
                 ollama_url=args.ollama_url or "http://localhost:11434")

    rs = RegistryStore(_REGISTRY_PATH)
    role_store = RoleStore(_ROLES_DIR)
    data = rs.load()

    work = []
    already_reviewed = 0
    wrong_status = 0
    wrong_group = 0
    for role_id, entry in sorted(data["roles"].items()):
        status = entry["meta"].get("status")
        if args.status and status != args.status:
            wrong_status += 1
            continue
        group, role_name = role_id_to_parts(role_id)
        if args.group and group != args.group:
            wrong_group += 1
            continue
        role_data = role_store.read_role(group, role_name, entry["latest_version"])
        existing = get_review_record(role_data)
        if existing and not args.force_reattach:
            already_reviewed += 1
            continue
        work.append(role_id)

    total = len(work)
    filters = f"status={args.status}"
    if args.group:
        filters += f" group={args.group}"
    print(f"Batch plan: {total} role(s) to review [{filters}]")
    print(f"  already reviewed: {already_reviewed}"
          + (f" (will reattach: use --force-reattach)" if already_reviewed else ""))
    if wrong_status:
        print(f"  skipped (status filter): {wrong_status}")
    if wrong_group:
        print(f"  skipped (group filter): {wrong_group}")
    print(f"Backend: {backend} / model: {model}")
    print(flush=True)

    if not total:
        print("Nothing to do.")
        return
    if args.dry_run:
        for role_id in work[:50]:
            print(f"  [dry] {role_id}")
        if len(work) > 50:
            print(f"  ... and {len(work) - 50} more")
        return

    verdicts = Counter()
    scores = Counter()
    errors = []
    start = time.time()

    for i, role_id in enumerate(work, 1):
        t0 = time.time()
        try:
            record = r.run_live(role_id)
            r.attach_record(role_id, record)
            elapsed = time.time() - t0
            verdicts[record.verdict] += 1
            scores[record.score] += 1
            print(f"  [{i:>4}/{total}] {role_id:<55} "
                  f"{record.verdict:<11} {record.score}⭐ ({elapsed:.1f}s)",
                  flush=True)
        except Exception as e:
            elapsed = time.time() - t0
            errors.append((role_id, str(e)[:200]))
            print(f"  [{i:>4}/{total}] {role_id:<55} ERROR ({elapsed:.1f}s): {str(e)[:80]}",
                  flush=True)

    total_time = time.time() - start
    print()
    print(f"Done in {total_time/60:.1f} min ({total_time/max(total,1):.1f}s avg)")
    print(f"Verdicts:")
    for v in ("approved", "needs_work", "rejected"):
        n = verdicts.get(v, 0)
        pct = n / total * 100 if total else 0
        print(f"  {v:<11} {n:>4}  ({pct:.0f}%)")
    if scores:
        print(f"Scores:")
        for s in sorted(scores.keys(), reverse=True):
            print(f"  {s}⭐  {scores[s]}")
    if errors:
        print(f"Errors: {len(errors)}")
        for role_id, err in errors[:20]:
            print(f"  - {role_id}: {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")


def cmd_review_status(args):
    """Show review state across the registry."""
    from rolecore import _REGISTRY_PATH, _ROLES_DIR
    from rolecore.storage.registry_store import RegistryStore
    from rolecore.storage.role_store import RoleStore
    from rolecore.utils.path_utils import role_id_to_parts
    from rolecore.core.reviewer import get_review_record

    rs = RegistryStore(_REGISTRY_PATH)
    role_store = RoleStore(_ROLES_DIR)
    data = rs.load()

    from collections import Counter
    verdicts = Counter()
    scores = Counter()
    samples = {"approved": [], "needs_work": [], "rejected": []}
    total = 0
    unreviewed = []

    for role_id, entry in sorted(data["roles"].items()):
        if args.status and entry["meta"].get("status") != args.status:
            continue
        total += 1
        group, role_name = role_id_to_parts(role_id)
        role_data = role_store.read_role(group, role_name, entry["latest_version"])
        record = get_review_record(role_data)
        if not record:
            verdicts["unreviewed"] += 1
            unreviewed.append(role_id)
            continue
        verdicts[record.verdict] += 1
        scores[record.score] += 1
        if record.verdict in samples and len(samples[record.verdict]) < 3:
            samples[record.verdict].append(role_id)

    print(f"Review status across {total} role(s)"
          + (f" (status={args.status})" if args.status else ""))
    for v in ("approved", "needs_work", "rejected", "unreviewed"):
        print(f"  {v:<12} {verdicts.get(v, 0)}")
    if scores:
        print("\nScore distribution:")
        for s in sorted(scores.keys(), reverse=True):
            print(f"  {s}⭐  {scores[s]}")
    if args.show_samples:
        for v, ids in samples.items():
            if ids:
                print(f"\n{v} samples: {', '.join(ids)}")
        if args.show_samples and unreviewed[:5]:
            print(f"\nunreviewed (first 5): {', '.join(unreviewed[:5])}")


# ─── main ──────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="rolecore",
        description="RoleCore — 岗位资产管理系统",
    )
    sub = parser.add_subparsers(dest="command")

    # role
    rp = sub.add_parser("role", help="角色 CRUD")
    rsub = rp.add_subparsers(dest="subcommand")

    r_create = rsub.add_parser("create", help="创建新角色")
    r_create.add_argument("--file", required=True)
    r_create.add_argument("--version", default="1")
    r_create.add_argument("--author", default="system")

    r_get = rsub.add_parser("get", help="查看角色")
    r_get.add_argument("--id", required=True)
    r_get.add_argument("--version", default="latest")
    r_get.add_argument("--full", action="store_true")

    r_list = rsub.add_parser("list", help="列出角色")
    r_list.add_argument("--group")
    r_list.add_argument("--status", default="live",
                        help="过滤状态: raw_imported/normalized/curated/official/archived/live/all (默认: live)")

    r_update = rsub.add_parser("update", help="新增版本")
    r_update.add_argument("--id", required=True)
    r_update.add_argument("--file", required=True)
    r_update.add_argument("--version")
    r_update.add_argument("--desc", default="")

    r_setlatest = rsub.add_parser("set-latest", help="设置 latest 指针")
    r_setlatest.add_argument("--id", required=True)
    r_setlatest.add_argument("--version", required=True)

    r_promote = rsub.add_parser("promote", help="晋升角色状态 (raw_imported→normalized→curated→official)")
    r_promote.add_argument("--id", required=True)
    r_promote.add_argument("--to", required=True,
                           choices=["normalized", "curated", "official", "archived"],
                           metavar="STATUS")

    r_gate = rsub.add_parser("gate", help="检查角色是否满足 official 最低门槛")
    r_gate.add_argument("--id", required=True)

    r_mke = rsub.add_parser("mark-enhanced", help="标记字段为人工增强（保护不被 reimport 覆盖）")
    r_mke.add_argument("--id", required=True)
    r_mke.add_argument("--fields", required=True,
                       help="逗号分隔的 dot-path 列表，如 'identity.name_cn,mission.summary'")

    r_ume = rsub.add_parser("unmark-enhanced", help="取消字段的增强保护")
    r_ume.add_argument("--id", required=True)
    r_ume.add_argument("--fields", required=True)

    r_dep = rsub.add_parser("deprecate", help="废弃角色 (legacy — 请改用 promote --to archived)")
    r_dep.add_argument("--id", required=True)

    r_del = rsub.add_parser("delete", help="删除角色或版本")
    r_del.add_argument("--id", required=True)
    r_del.add_argument("--version")

    r_val = rsub.add_parser("validate", help="验证 YAML schema")
    r_val.add_argument("--file", required=True)

    r_ver = rsub.add_parser("versions", help="查看所有版本")
    r_ver.add_argument("--id", required=True)

    # search
    sp = sub.add_parser("search", help="检索角色")
    sp.add_argument("--group")
    sp.add_argument("--tags")
    sp.add_argument("--keyword")
    sp.add_argument("--tag-match", default="any")
    sp.add_argument("--status", default="active")
    sp.add_argument("--list-groups", action="store_true")
    sp.add_argument("--list-tags", action="store_true")

    # find (three-axis fusion search)
    fp = sub.add_parser("find", help="三维融合检索（岗位 × 技术栈 × 专业特长）")
    fp.add_argument("query", help="自然语言查询，如 'Python 后端 高级开发'")
    fp.add_argument("--top-k", type=int, default=5, help="每个维度返回的候选数（默认 5）")
    fp.add_argument("--status", default="official", help="状态过滤（默认 official，传 '' 取消过滤）")
    fp.add_argument("--json", action="store_true", help="以 JSON 输出")

    # export
    ep = sub.add_parser("export", help="导出角色")
    ep.add_argument("--id")
    ep.add_argument("--group")
    ep.add_argument("--version", default="latest")
    ep.add_argument("--format", choices=["prompt", "json", "markdown"], default="prompt")
    ep.add_argument("--output")

    # assemble
    ap = sub.add_parser("assemble", help="装配执行上下文")
    ap.add_argument("--id", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--goal", required=True)
    ap.add_argument("--context")
    ap.add_argument("--version", default="latest")
    ap.add_argument("--format", choices=["prompt", "json", "markdown"], default="prompt")
    ap.add_argument("--output")

    # registry
    regp = sub.add_parser("registry", help="注册表维护")
    regsub = regp.add_subparsers(dest="subcommand")
    regsub.add_parser("stats", help="统计信息")
    regsub.add_parser("rebuild-index", help="重建 tag index")
    reg_dump = regsub.add_parser("dump", help="导出注册表")
    reg_dump.add_argument("--format", choices=["json", "yaml"], default="json")
    regsub.add_parser("verify", help="校验文件一致性")
    regsub.add_parser("resync", help="从 YAML 重新同步 registry 的 name_cn/name_en/domain/tags/status")

    # review (LLM-assisted quality review)
    rvp = sub.add_parser("review", help="LLM 质量复核（curated gate）")
    rvsub = rvp.add_subparsers(dest="subcommand")

    rv_prompt = rvsub.add_parser("prompt", help="生成一个角色的复核 prompt（离线，贴到任意 LLM 用）")
    rv_prompt.add_argument("--id", required=True)
    rv_prompt.add_argument("--output", help="写入文件；否则 stdout")

    rv_run = rvsub.add_parser("run", help="跑一次 live 复核（Anthropic API 或本地 Ollama）")
    rv_run.add_argument("--id", required=True)
    rv_run.add_argument("--force", action="store_true")
    rv_run.add_argument("--backend", choices=["anthropic", "ollama"], default="anthropic",
                        help="推理后端（默认 anthropic；本地跑用 ollama）")
    rv_run.add_argument("--model", help="模型名；anthropic 默认 claude-opus-4-7，ollama 默认 qwen3:8b")
    rv_run.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama API 地址（默认 http://localhost:11434）")

    rv_apply = rvsub.add_parser("apply", help="挂一条手工或外部 LLM 的复核结果到角色 meta.review")
    rv_apply.add_argument("--id", required=True)
    rv_apply.add_argument("--from-file", help="LLM 原始响应（含 JSON verdict）")
    rv_apply.add_argument("--verdict", choices=["approved", "needs_work", "rejected"])
    rv_apply.add_argument("--score", type=int, help="1-5")
    rv_apply.add_argument("--strengths", help="| 分隔")
    rv_apply.add_argument("--issues", help="| 分隔")
    rv_apply.add_argument("--fix-hints", help="| 分隔")
    rv_apply.add_argument("--reviewer", help="标注 reviewer_model（默认 'human' 或 'external-llm'）")

    rv_batch = rvsub.add_parser("batch", help="批量复核（默认 skip 已评审；可中断续跑）")
    rv_batch.add_argument("--backend", choices=["anthropic", "ollama"], default="ollama")
    rv_batch.add_argument("--model", help="默认 qwen3:8b (ollama) / claude-opus-4-7 (anthropic)")
    rv_batch.add_argument("--ollama-url", default="http://localhost:11434")
    rv_batch.add_argument("--group", help="只跑指定 group")
    rv_batch.add_argument("--status", default="official", help="只跑指定 status (默认 official)")
    rv_batch.add_argument("--force-reattach", action="store_true", help="重评已 review 的角色")
    rv_batch.add_argument("--dry-run", action="store_true")

    rv_status = rvsub.add_parser("status", help="查看所有角色的复核状态汇总")
    rv_status.add_argument("--status", help="只看指定 status 的角色（如 official）")
    rv_status.add_argument("--show-samples", action="store_true", help="显示几个样例 role_id")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        ("role", "create"): cmd_role_create,
        ("role", "get"): cmd_role_get,
        ("role", "list"): cmd_role_list,
        ("role", "update"): cmd_role_update,
        ("role", "set-latest"): cmd_role_set_latest,
        ("role", "promote"): cmd_role_promote,
        ("role", "gate"): cmd_role_gate,
        ("role", "mark-enhanced"): cmd_role_mark_enhanced,
        ("role", "unmark-enhanced"): cmd_role_unmark_enhanced,
        ("role", "deprecate"): cmd_role_deprecate,
        ("role", "delete"): cmd_role_delete,
        ("role", "validate"): cmd_role_validate,
        ("role", "versions"): cmd_role_versions,
        ("search", None): cmd_search,
        ("find", None): cmd_find,
        ("export", None): cmd_export,
        ("assemble", None): cmd_assemble,
        ("registry", "stats"): cmd_registry_stats,
        ("registry", "rebuild-index"): cmd_registry_rebuild,
        ("registry", "dump"): cmd_registry_dump,
        ("registry", "verify"): cmd_registry_verify,
        ("registry", "resync"): cmd_registry_resync,
        ("review", "prompt"): cmd_review_prompt,
        ("review", "run"): cmd_review_run,
        ("review", "apply"): cmd_review_apply,
        ("review", "batch"): cmd_review_batch,
        ("review", "status"): cmd_review_status,
    }

    key = (args.command, getattr(args, "subcommand", None))
    fn = dispatch.get(key)
    if fn:
        try:
            fn(args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
