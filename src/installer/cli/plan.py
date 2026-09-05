"""`plan` — show what an install would change, without changing anything.

`resolve` says where each asset belongs; `plan` compares that against what is on
disk right now and classifies every link as create / replace / current. Rows that
are already current are summarized rather than listed, so the output is dominated
by what would actually change.

Scope is exactly what the resolver produces — the Claude assets. The rest of an
install (~/.zshrc, ~/.gitconfig, ~/.vimrc, ~/.config, ~/bin, the settings.json
merge) is not resolved into a plan, so `--dry-run` is the command that previews
those. Every message here says so rather than implying whole-install coverage.
"""

from .. import resolver
from ..resolver import LinkStatus, PruneStatus
from . import Context

SCOPE_NOTE = "Claude assets only — run `python3 -m src.installer --dry-run` to preview the whole install."


def run(context: Context, group: str | None = None) -> int:
    """Print the pending changes. Returns a process exit code."""
    printer = context.printer
    context.warn_if_no_machine()

    plan = context.plan(group)
    statuses = [(link, resolver.link_status(link)) for link in plan.links]
    prunes = [(prune, resolver.prune_status(prune)) for prune in plan.prunes]

    pending = [(link, status) for link, status in statuses if status is not LinkStatus.CURRENT]
    removals = [prune for prune, status in prunes if status is PruneStatus.REMOVE]
    current = len(statuses) - len(pending)

    printer.print_section_header("Pending changes")
    if not pending and not removals:
        printer.print_success(f"All Claude assets are up to date ({current} link(s) already correct).")
        printer.print_info(SCOPE_NOTE)
        return 0

    rows = [[str(status), context.display(link.dest), context.display(link.source), link.group] for link, status in pending]
    rows += [["remove", context.display(prune.dest), context.display(prune.source), prune.group] for prune in removals]
    printer.print_table(["action", "destination", "source", "group"], rows)
    print()

    created = sum(1 for _, status in pending if status is LinkStatus.CREATE)
    replaced = len(pending) - created
    printer.print_info(
        f"{created} to create, {replaced} to replace, {len(removals)} to remove, {current} already current."
    )
    if replaced:
        # The install asks per file and only writes a .bak if you say yes, so this
        # cannot promise a backup on the replacements' behalf.
        printer.print_info("Each replacement prompts before overwriting; answer 'y' there to keep a .bak.")
    printer.print_info("Apply with: python3 -m src.installer")
    printer.print_info(SCOPE_NOTE)
    return 0
