"""`doctor` — report drift the installer would not fix on its own.

An install is additive: it creates and refreshes links, but never notices what a
previous install left behind. These checks look at the installer-owned profile
subdirectories and report what does not belong there — stale links from renamed
assets, links to a missing target, and backups left inside those subdirectories.
Nothing here is repaired automatically; the point is to surface it for a
deliberate decision.

Scope is deliberately those subdirectories, so backups outside them (a
`settings.json.bak` at a profile root, a `~/.zshrc.bak` in $HOME) are not
reported. Widening the scan to the profile root or $HOME would mean reporting
everything the installer does not manage, which is most of what lives there.
"""

from dataclasses import dataclass
from pathlib import Path

from ..resolver import COLLECTIONS, Plan
from . import Context

# The profile subdirectories the installer fully owns. The profile root itself is
# deliberately excluded: it holds plenty the installer does not manage
# (settings.json, projects/, todos/), so scanning it would report noise as drift.
MANAGED_SUBDIRS = tuple(sorted({collection.into for collection in COLLECTIONS if collection.into}))


@dataclass(frozen=True)
class Finding:
    check: str
    detail: str


def _managed_dirs(context: Context) -> list[Path]:
    return [
        profile.root / subdir
        for profile in context.profiles
        for subdir in MANAGED_SUBDIRS
        if (profile.root / subdir).is_dir()
    ]


def _check_machine(context: Context) -> list[Finding]:
    if context.machine is not None:
        return []
    marker = context.home_dir / ".dotfiles-machine"
    reason = "names an unrecognized category" if marker.is_file() else "is missing"
    return [Finding("machine-marker", f"{marker} {reason}; machine-scoped assets will not install")]


def _check_managed_dirs(context: Context, expected: set[Path] | None) -> list[Finding]:
    """Flag entries in installer-owned directories that no longer belong there.

    Stale-link detection is skipped when this machine has no category, because
    resolution then omits every machine-scoped collection — so correctly installed
    local commands, skills and hooks would all look unaccounted for. It is skipped
    the same way when ``expected`` is None, meaning resolution failed outright.
    Either way the underlying cause is reported on its own instead.
    """
    repo = context.dotfiles_dir.resolve()  # resolve both sides: the repo path may itself traverse a symlink
    findings: list[Finding] = []
    for directory in _managed_dirs(context):
        try:
            entries = sorted(directory.iterdir())
        except OSError as error:
            findings.append(Finding("unreadable-directory", f"{context.display(directory)} cannot be read: {error}"))
            continue
        for entry in entries:
            if entry.name.endswith(".bak"):
                findings.append(Finding("orphaned-backup", f"{context.display(entry)} left by an earlier install"))
            elif not entry.is_symlink():
                continue  # a file the user put there themselves; not ours to report
            elif not entry.exists():
                findings.append(Finding("broken-link", f"{context.display(entry)} points at a missing target"))
            elif expected is None or context.machine is None or entry in expected:
                continue
            else:
                try:
                    inside_repo = entry.resolve().is_relative_to(repo)
                except OSError as error:
                    findings.append(Finding("unreadable-link", f"{context.display(entry)} cannot be resolved: {error}"))
                    continue
                if inside_repo:
                    findings.append(Finding("stale-link", f"{context.display(entry)} is no longer resolved by any collection"))
    return findings


def run(context: Context) -> int:
    """Print any drift found. Returns 1 when there are findings, else 0."""
    printer = context.printer

    plan: Plan | None = None
    findings = _check_machine(context)
    try:
        plan = context.plan()
    except ValueError as error:
        # doctor is the command you reach for once something is already wrong, so a
        # malformed `profiles:` allow-list is reported rather than allowed to abort the
        # run. With no resolution to compare against, the checks that need one are
        # skipped instead of guessed at — the checks that don't still report.
        findings.append(Finding("malformed-frontmatter", str(error)))

    # Prune destinations count as expected: a leftover link from a `profiles:`
    # opt-out is drift the next install *does* fix, and `plan` already lists it.
    expected = None if plan is None else {link.dest for link in plan.links} | {prune.dest for prune in plan.prunes}
    # One resolution feeds every check, so two of them can never disagree about
    # what the repo currently routes.
    findings += _check_managed_dirs(context, expected)

    printer.print_section_header("Diagnostics")
    if not findings:
        printer.print_success("No drift found.")
        return 0

    printer.print_table(["check", "detail"], [[finding.check, finding.detail] for finding in findings])
    print()
    printer.print_warning(f"{len(findings)} finding(s). None are repaired automatically — fix each deliberately.")
    return 1
