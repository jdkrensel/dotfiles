"""`resolve` — show which tracked asset goes into which Claude profile.

The routing matrix on its own: what this repo contains and where each piece is
destined, with one column per profile active on this machine. It deliberately
does not look at what is currently installed — that is `plan`'s job — so it
answers "what would I get here?" rather than "what is out of date?".
"""

from collections import defaultdict

from .. import resolver
from ..resolver import COLLECTIONS
from . import Context


def run(context: Context, group: str | None = None) -> int:
    """Print the routing matrix. Returns a process exit code."""
    printer = context.printer
    context.warn_if_no_machine()

    plan = context.plan(group)
    if plan.is_empty:
        printer.print_info(f"Nothing resolves for group '{group}'." if group else "No assets resolve on this machine.")
        return 0

    tokens = [profile.token for profile in context.profiles]
    destinations: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for link in plan.links:
        for profile in context.profiles:
            if link.dest.is_relative_to(profile.root):
                destinations[(link.group, str(link.source))].add(profile.token)

    rows: list[list[str]] = []
    for collection in COLLECTIONS:
        if group is not None and collection.group != group:
            continue
        for source in resolver.sources_for(collection, context.assets_dir, context.machine):
            landed = destinations.get((collection.group, str(source)), set())
            # A blank cell has two very different causes, so they get distinct
            # marks: a pinned collection was never offered to this profile, while
            # a dash means the asset was offered and its `profiles:` line said no.
            absent = "pin" if collection.pinned else "-"
            marks = ["yes" if token in landed else absent for token in tokens]
            rows.append([collection.group, context.display(source), collection.into or "(root)", *marks])

    printer.print_section_header("Resolved assets")
    printer.print_table(["group", "source", "into", *tokens], rows)
    print()
    printer.print_info(f"{len(rows)} assets → {len(plan.links)} links across {len(tokens)} profile(s): {', '.join(tokens)}")
    printer.print_info("yes = linked there, - = opted out via `profiles:`, pin = collection never fans out.")
    if plan.prunes:
        printer.print_info(f"{len(plan.prunes)} link(s) opted out via `profiles:` frontmatter and would be pruned.")
    return 0
