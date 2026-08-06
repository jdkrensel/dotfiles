"""Pure resolution of tracked Claude assets into the links an install should create.

``resolve()`` answers *what should be linked where* without touching the filesystem
and without printing: it reads the tracked asset tree and returns a :class:`Plan`.
``SymlinkManager`` consumes that plan and executes it.

Splitting the decision from the execution collapses seven near-identical ``setup_*``
methods (glob a directory, iterate profiles, skip absent roots, mkdir, link) into the
single :data:`COLLECTIONS` table below, so the fan-out rules are stated once instead
of re-implemented per asset type.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Maps a profile token (as written in a command's `profiles:` frontmatter, and
# matching the clp/clb shell aliases on the work machine) to that profile's root
# dir under $HOME. The tokens are stable identifiers; the shell alias that reaches
# a profile is a machine-local detail and may differ (the personal machine reaches
# the default profile as `cl`, and never has a bedrock profile at all).
CLAUDE_PROFILES: dict[str, str] = {
    "clp": ".claude",          # default profile (~/.claude)
    "clb": ".claude-bedrock",  # Bedrock profile used for PHI work
}

# The profile that always exists. It is created if missing; every other profile is
# populated only when its root dir is already present on the machine.
DEFAULT_PROFILE = "clp"


@dataclass(frozen=True)
class Profile:
    """A Claude profile this machine should install into."""

    token: str
    root: Path


@dataclass(frozen=True)
class Link:
    """A symlink that should exist once the install has run."""

    source: Path
    dest: Path
    group: str


@dataclass(frozen=True)
class Prune:
    """A link to remove because its source opted out of that profile.

    Only ever acted on when ``dest`` is a symlink resolving to ``source`` — see
    ``SymlinkManager._prune_stale_link``.
    """

    source: Path
    dest: Path
    group: str


@dataclass(frozen=True)
class Plan:
    """Everything an install would do to the Claude profiles."""

    links: tuple[Link, ...]
    prunes: tuple[Prune, ...]

    @property
    def is_empty(self) -> bool:
        return not self.links and not self.prunes


@dataclass(frozen=True)
class Collection:
    """One tracked directory of assets and the rule for fanning it out.

    ``group`` names the install step that owns the collection, so a caller can
    resolve one step at a time (``resolve(..., group="rules")``) or the whole
    tree at once.
    """

    group: str
    subdir: str               # under src/assets; "{machine}" marks it machine-scoped
    into: str | None          # subdir of the profile root; None → the root itself
    pattern: str = "*.md"
    directories: bool = False  # match directories rather than files
    narrowable: bool = False   # honour a `profiles:` frontmatter allow-list
    pinned: bool = False       # always the default profile; never fans out

    @property
    def machine_scoped(self) -> bool:
        return "{machine}" in self.subdir


# Declared once here instead of re-implemented in seven setup_* methods.
#
# Machine-scoped collections ("{machine}") live under machines/<category>/ and are
# tracked in git, split by machine category rather than gitignored; the category
# comes from the ~/.dotfiles-machine marker.
#
# `pinned` collections deliberately bypass profile fan-out: hooks are registered by
# path in the default profile's settings.json, so a second copy under another
# profile root would never be read.
COLLECTIONS: tuple[Collection, ...] = (
    # Path-scoped rule files, injected by the harness when a matching file is in play.
    Collection("rules", "claude/rules", into="rules"),
    # Named stateless subagents (e.g. the `reviewer` used by /commit).
    Collection("agents", "claude/agents", into="agents"),
    # Machine-agnostic slash-commands. Deliberately not narrowable — fanning out to
    # every existing profile is the whole point of a shared command.
    Collection("commands", "claude/commands", into="commands"),
    # A single required script rather than a collection; the shared settings fragment
    # points every profile at it, so a missing file is an error the caller reports.
    Collection("statusline", "claude", into=None, pattern="statusline.sh"),
    # Shared hooks, then this machine's hooks — both into the default profile only.
    Collection("hooks", "claude/hooks", into="hooks", pattern="*", pinned=True),
    Collection("hooks", "claude/machines/{machine}/hooks", into="hooks", pattern="*", pinned=True),
    # Machine-local commands and skills are narrowable: a `profiles:` line restricts
    # one to a subset of profiles, and any stale link is pruned.
    Collection("local-commands", "claude/machines/{machine}/commands", into="commands", narrowable=True),
    # Each skill is a directory holding SKILL.md plus bundled resources, linked whole
    # so the bundled files travel with it. Narrowable because a skill that reaches PHI,
    # clinical databases, or production hosts must be able to stay in the BAA-covered
    # Bedrock profile instead of fanning out to the default one.
    Collection(
        "local-skills",
        "claude/machines/{machine}/skills",
        into="skills",
        pattern="*",
        directories=True,
        narrowable=True,
    ),
)


def active_profiles(home_dir: Path) -> list[Profile]:
    """Return the profiles an install should target on this machine.

    The default profile is always included (it is created if missing). Every other
    profile is included only when its root dir already exists — a machine that has
    never set up the Bedrock profile does not get one created for it.
    """
    profiles: list[Profile] = []
    for token, root_name in CLAUDE_PROFILES.items():
        root = home_dir / root_name
        if token != DEFAULT_PROFILE and not root.is_dir():
            continue
        profiles.append(Profile(token=token, root=root))
    return profiles


def allowed_profiles(source: Path) -> set[str]:
    """Return the profile tokens an asset opts into.

    An asset may declare `profiles: clp, clb` in its YAML frontmatter to restrict
    which profiles it installs into. The line is parsed textually (no YAML
    dependency); only tokens in :data:`CLAUDE_PROFILES` are kept. No such line → all
    known profiles, preserving the default of installing everywhere.

    A directory-based asset (a skill) carries its frontmatter in the SKILL.md inside
    it, so that is what gets read. A readable skill directory that genuinely has no
    SKILL.md keeps the install-everywhere default.

    Raises :class:`ValueError` when an asset *tries* to state a preference but the
    result can't be trusted — an unreadable file or directory, or a `profiles:` line
    naming no recognized token (a typo like `profiles: bedrock`). Every one of those
    would otherwise fall back to installing everywhere, and since narrowing is what
    keeps a PHI-touching asset out of the non-BAA profile, widening is the one failure
    direction worth refusing. A loud error is trivially fixable; a silent fan-out is
    invisible. Note this applies to the whole asset, not just its SKILL.md: a skill's
    bundled scripts/ and references/ travel with the link.
    """
    all_profiles = set(CLAUDE_PROFILES)
    if source.is_dir():
        # listdir rather than SKILL.md.exists(): exists() follows symlinks and
        # swallows permission errors, so a dangling link or an unreadable directory
        # would silently read as "no SKILL.md" and fan the whole payload out.
        try:
            entries = set(os.listdir(source))
        except OSError as error:
            raise ValueError(f"Cannot read skill directory {source}: {error}") from error
        if "SKILL.md" not in entries:
            return all_profiles  # nothing here to state a preference with
        source = source / "SKILL.md"
    try:
        lines = source.read_text().splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"Cannot read frontmatter from {source}: {error}") from error
    if not lines or lines[0].strip() != "---":
        return all_profiles  # no frontmatter → default to every profile
    for line in lines[1:]:
        if line.strip() == "---":
            break  # end of frontmatter; `profiles:` only counts in the header
        # Deliberately the raw line, not a stripped one: top-level frontmatter keys are
        # unindented, so this ignores continuation lines inside a folded `description: >`
        # block that happen to start with the word "profiles:".
        if line.startswith("profiles:"):
            tokens = line.split(":", 1)[1].replace(",", " ").split()
            requested = {token for token in tokens if token in all_profiles}
            if not requested:
                raise ValueError(
                    f"{source} has a `profiles:` line naming no known profile "
                    f"({line.strip()!r}); use the inline form with tokens from "
                    f"{sorted(all_profiles)}, e.g. `profiles: clp, clb`."
                )
            return requested
    return all_profiles


def sources_for(collection: Collection, assets_dir: Path, machine: str | None) -> list[Path]:
    """Return the tracked files (or directories) a collection contributes, sorted.

    A collection whose directory does not exist contributes nothing — a recognized
    machine with no commands defined yet is a legitimate no-op, not an error.
    """
    if collection.machine_scoped:
        if machine is None:
            return []
        subdir = collection.subdir.format(machine=machine)
    else:
        subdir = collection.subdir

    source_dir = assets_dir / subdir
    if not source_dir.is_dir():
        return []

    matches = source_dir.glob(collection.pattern)
    if collection.directories:
        return sorted(path for path in matches if path.is_dir())
    return sorted(path for path in matches if path.is_file())


def resolve(
    assets_dir: Path,
    profiles: list[Profile],
    machine: str | None = None,
    group: str | None = None,
) -> Plan:
    """Resolve tracked assets into the links and prunes an install should perform.

    Pure: reads the asset tree to enumerate sources and frontmatter, but writes
    nothing and prints nothing. Pass ``group`` to resolve a single install step,
    or omit it for the whole tree. Machine-scoped collections are skipped entirely
    when ``machine`` is None.

    Propagates :class:`ValueError` from :func:`allowed_profiles` when a narrowable
    asset states an untrustworthy preference, so a typo'd allow-list aborts the step
    instead of silently installing everywhere.
    """
    default = next((profile for profile in profiles if profile.token == DEFAULT_PROFILE), None)
    links: list[Link] = []
    prunes: list[Prune] = []

    for collection in COLLECTIONS:
        if group is not None and collection.group != group:
            continue

        targets = [default] if collection.pinned else profiles
        sources = sources_for(collection, assets_dir, machine)

        for profile in targets:
            if profile is None:
                continue  # pinned collection on a machine with no default profile
            dest_dir = profile.root / collection.into if collection.into else profile.root
            for source in sources:
                dest = dest_dir / source.name
                denied = collection.narrowable and profile.token not in allowed_profiles(source)
                if denied:
                    prunes.append(Prune(source=source, dest=dest, group=collection.group))
                else:
                    links.append(Link(source=source, dest=dest, group=collection.group))

    return Plan(links=tuple(links), prunes=tuple(prunes))
