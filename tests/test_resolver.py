"""Unit tests for the pure asset resolver.

resolve() decides *what* an install should link where, without touching the
filesystem. The existing test_installer_* modules already cover the end-to-end
behavior through SymlinkManager; these tests pin the routing matrix directly —
profile fan-out, pinning, machine scoping, and `profiles:` narrowing — plus the
guarantee that resolving writes nothing.

They drive a synthetic asset tree so the rules are tested independently of which
assets actually ship in the repo."""

from pathlib import Path

from src.installer.resolver import (
    COLLECTIONS,
    DEFAULT_PROFILE,
    Profile,
    active_profiles,
    resolve,
    sources_for,
)


def _assets(tmp_path: Path) -> Path:
    """Return an empty synthetic src/assets tree."""
    assets = tmp_path / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    return assets


def _write(path: Path, text: str = "body\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _command(path: Path, profiles_line: str | None = None) -> Path:
    front = "---\ndescription: test\n"
    if profiles_line is not None:
        front += f"profiles: {profiles_line}\n"
    front += "---\n\nbody\n"
    return _write(path, front)


def _profiles(home: Path, *tokens: str) -> list[Profile]:
    roots = {"clp": ".claude", "clb": ".claude-bedrock"}
    return [Profile(token=token, root=home / roots[token]) for token in tokens]


def _dests(plan_items) -> set[Path]:
    return {item.dest for item in plan_items}


# --- active_profiles ---------------------------------------------------------


def test_default_profile_is_always_active(tmp_path):
    """The default profile is created if missing, so it is always a target."""
    home = tmp_path / "home"
    home.mkdir()
    assert [p.token for p in active_profiles(home)] == [DEFAULT_PROFILE]


def test_extra_profile_active_only_when_its_root_exists(tmp_path):
    home = tmp_path / "home"
    (home / ".claude-bedrock").mkdir(parents=True)
    assert [p.token for p in active_profiles(home)] == ["clp", "clb"]


def test_active_profiles_creates_nothing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    active_profiles(home)
    assert not (home / ".claude").exists()


# --- sources_for -------------------------------------------------------------


def _collection(group: str, subdir: str):
    return next(c for c in COLLECTIONS if c.group == group and c.subdir == subdir)


def test_missing_source_dir_contributes_nothing(tmp_path):
    """A recognized machine with nothing defined yet is a no-op, not an error."""
    assets = _assets(tmp_path)
    collection = _collection("rules", "claude/rules")
    assert sources_for(collection, assets, machine=None) == []


def test_sources_are_sorted_and_filtered_by_pattern(tmp_path):
    assets = _assets(tmp_path)
    _write(assets / "claude" / "rules" / "python.md")
    _write(assets / "claude" / "rules" / "go.md")
    _write(assets / "claude" / "rules" / "notes.txt")  # wrong extension

    collection = _collection("rules", "claude/rules")
    assert [p.name for p in sources_for(collection, assets, machine=None)] == ["go.md", "python.md"]


def test_directory_collection_yields_dirs_and_ignores_stray_files(tmp_path):
    assets = _assets(tmp_path)
    skills = assets / "claude" / "machines" / "work" / "skills"
    _write(skills / "deploy-page" / "SKILL.md")
    _write(skills / "README.md")  # stray file alongside the skill dirs

    collection = _collection("local-skills", "claude/machines/{machine}/skills")
    assert [p.name for p in sources_for(collection, assets, machine="work")] == ["deploy-page"]


def test_machine_scoped_collection_needs_a_machine(tmp_path):
    assets = _assets(tmp_path)
    _write(assets / "claude" / "machines" / "work" / "commands" / "a.md")

    collection = _collection("local-commands", "claude/machines/{machine}/commands")
    assert sources_for(collection, assets, machine=None) == []
    assert len(sources_for(collection, assets, machine="work")) == 1


# --- resolve: fan-out and pinning --------------------------------------------


def test_shared_asset_fans_out_to_every_active_profile(tmp_path):
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _write(assets / "claude" / "agents" / "reviewer.md")

    plan = resolve(assets, _profiles(home, "clp", "clb"), group="agents")
    assert _dests(plan.links) == {
        home / ".claude" / "agents" / "reviewer.md",
        home / ".claude-bedrock" / "agents" / "reviewer.md",
    }
    assert plan.prunes == ()


def test_pinned_collection_never_fans_out(tmp_path):
    """Hooks are registered by path in the default profile's settings.json, so a
    copy under another profile root would never be read."""
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _write(assets / "claude" / "hooks" / "guard.py")

    plan = resolve(assets, _profiles(home, "clp", "clb"), machine="work", group="hooks")
    assert _dests(plan.links) == {home / ".claude" / "hooks" / "guard.py"}


def test_hooks_group_merges_shared_and_machine_sources(tmp_path):
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _write(assets / "claude" / "hooks" / "shared.py")
    _write(assets / "claude" / "machines" / "work" / "hooks" / "work_only.sh")

    plan = resolve(assets, _profiles(home, "clp"), machine="work", group="hooks")
    assert _dests(plan.links) == {
        home / ".claude" / "hooks" / "shared.py",
        home / ".claude" / "hooks" / "work_only.sh",
    }


def test_a_machine_hook_overrides_a_shared_hook_of_the_same_name(tmp_path):
    """Both resolve to the same dest, so the later link wins — which makes the
    order of the two hook rows in COLLECTIONS load-bearing, not cosmetic."""
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    shared = _write(assets / "claude" / "hooks" / "guard.py")
    machine = _write(assets / "claude" / "machines" / "work" / "hooks" / "guard.py")

    plan = resolve(assets, _profiles(home, "clp"), machine="work", group="hooks")
    assert [link.source for link in plan.links] == [shared, machine]


def test_statusline_lands_in_the_profile_root_itself(tmp_path):
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _write(assets / "claude" / "statusline.sh", "#!/bin/bash\n")

    plan = resolve(assets, _profiles(home, "clp", "clb"), group="statusline")
    assert _dests(plan.links) == {
        home / ".claude" / "statusline.sh",
        home / ".claude-bedrock" / "statusline.sh",
    }


# --- resolve: narrowing and pruning ------------------------------------------


def test_profiles_frontmatter_routes_and_prunes(tmp_path):
    """An allow-list links into the named profile and prunes the omitted one."""
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    commands = assets / "claude" / "machines" / "work" / "commands"
    _command(commands / "clb_only.md", profiles_line="clb")

    plan = resolve(assets, _profiles(home, "clp", "clb"), machine="work", group="local-commands")
    assert _dests(plan.links) == {home / ".claude-bedrock" / "commands" / "clb_only.md"}
    assert _dests(plan.prunes) == {home / ".claude" / "commands" / "clb_only.md"}


def test_unrestricted_command_links_everywhere_and_prunes_nothing(tmp_path):
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _command(assets / "claude" / "machines" / "work" / "commands" / "a.md")

    plan = resolve(assets, _profiles(home, "clp", "clb"), machine="work", group="local-commands")
    assert len(plan.links) == 2
    assert plan.prunes == ()


def test_shared_commands_are_not_narrowable(tmp_path):
    """A `profiles:` line in a shared command is ignored — fanning out is the point."""
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _command(assets / "claude" / "commands" / "commit.md", profiles_line="clb")

    plan = resolve(assets, _profiles(home, "clp", "clb"), group="commands")
    assert len(plan.links) == 2
    assert plan.prunes == ()


# --- resolve: scoping and purity ---------------------------------------------


def test_group_filter_restricts_the_plan(tmp_path):
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _write(assets / "claude" / "rules" / "python.md")
    _write(assets / "claude" / "agents" / "reviewer.md")

    plan = resolve(assets, _profiles(home, "clp"), group="rules")
    assert {link.group for link in plan.links} == {"rules"}


def test_machine_scoped_assets_are_inert_on_another_machine(tmp_path):
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    _command(assets / "claude" / "machines" / "work" / "commands" / "a.md")

    plan = resolve(assets, _profiles(home, "clp"), machine="personal")
    assert plan.is_empty


def test_empty_tree_resolves_to_an_empty_plan(tmp_path):
    plan = resolve(_assets(tmp_path), _profiles(tmp_path / "home", "clp"), machine="work")
    assert plan.is_empty


def test_resolve_writes_nothing(tmp_path):
    """The purity guarantee a dry-run depends on: resolving creates no destinations."""
    assets = _assets(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    _write(assets / "claude" / "agents" / "reviewer.md")
    _write(assets / "claude" / "hooks" / "guard.py")

    plan = resolve(assets, _profiles(home, "clp", "clb"), machine="work")
    assert plan.links  # it did resolve something
    assert list(home.iterdir()) == []
