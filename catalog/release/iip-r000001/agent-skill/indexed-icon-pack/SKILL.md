---
name: indexed-icon-pack
description: Search a neighboring Indexed Icon Pack, inspect exact renditions, and select or materialize an icon without copying the whole catalog into a project.
---

# Indexed Icon Pack consumer

Find the package through `INDEXED_ICON_PACK_HOME`, an explicitly supplied path,
or a sibling `IndexedIconPack_v1` directory. Do not persist that machine path in
the consuming project. Use the package's `iconctl.py` for queries; do not parse
its database independently from this skill.

1. Run `iconctl.py version --json`. Refuse selection from an unpublished or
   incompatible catalog; report the release ID and catalog revision you saw.
2. Search with the target object's visual role and constraints using
   `iconctl.py search "..." --json`. Inspect candidates with `show ICON_ID
   --json`; a title or collection name alone is not proof of what is pictured.
   Read the literal `description` together with `keywords` entries in
   `reviewed_term`, `inferred_use`, and `uncertainty`. Alternative names are
   retrieval hypotheses: abstract art can support more than one reading.
   Do not discard a suitable icon solely because its literal caption uses a
   different noun. Inspect the thumbnail when a required visual detail matters.
   Use `--require subject=shield` only for a genuine hard metadata constraint;
   values are OR within a field and AND across fields. Use `--like ICON_ID`
   for a soft example, and repeat `--except ICON_ID` for already-used logical
   icons. Exclusion covers every rendition. Read `shortfall` and diagnostics;
   never silently relax constraints. Ranking scores are not confidence.
3. Return `{catalog_id, icon_id}` for a floating visual choice. Add
   `rendition_sha256` when the owning record must reproduce exact pixels.
4. Only when the user requested a local copy, run `materialize ICON_ID --to
   <explicit-destination>` (and `--sha256` for a pin). Respect the no-overwrite
   default and keep the receipt. Never copy the entire icon catalog into the
   consumer repository.

The consuming product owns assignment, approval, and publication of its own
records. A catalog search result never authorizes changing a Skill, Equipment,
action, or other versioned definition. The catalog is read-only at runtime.

See the package-root `USAGE.md` for the full command and reference contract.
For field feedback record the request, returned/chosen IDs, reason, release ID,
and search-profile hash. Search does not reserve an icon; the consumer owns its
used-icon set and concurrent assignment.
