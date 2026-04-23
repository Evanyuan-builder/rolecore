"""Quick tour: load the registry, run a three-axis fusion search, assemble a role.

Run from the showcase root:
    python examples/load_and_find.py
"""

from rolecore import create_default_engine, create_fusion_engine


def main():
    # ─── standard engine: role manager + keyword search + assembler ────────
    role_manager, search_engine, assembler = create_default_engine()
    entries = role_manager.registry_store.list_all_entries()
    print(f"Registry loaded: {len(entries)} roles")
    print()

    # ─── fusion search: three axes = job × tech × specialty ────────────────
    fusion = create_fusion_engine()
    query = "backend python api"
    result = fusion.find(query, top_k_per_axis=3)

    print(f"Fusion search for: {query!r}")
    for axis in ("job", "tech", "specialty"):
        hits = result.get(axis, [])
        print(f"  {axis} axis ({len(hits)} hits):")
        for hit in hits[:3]:
            print(f"    {hit.entry.role_id:<50} score={hit.score:.2f}")
    print()

    triad = result.get("triad", {})
    if triad:
        print("Triad recommendation (best combo across axes):")
        for axis, hit in triad.items():
            if hit:
                print(f"  {axis:<10} → {hit.entry.role_id}")
    print()

    # ─── assemble: render a role as a ready-to-use prompt ──────────────────
    if entries:
        sample_id = entries[0]["role_id"]
        ctx = assembler.assemble(
            role_id=sample_id,
            task="review the API design",
            goal="identify reliability risks before launch",
        )
        prompt = ctx.prompt
        print(f"Assembled prompt for {sample_id} (first 400 chars):")
        print("─" * 70)
        print(prompt[:400] + ("..." if len(prompt) > 400 else ""))
        print("─" * 70)


if __name__ == "__main__":
    main()
