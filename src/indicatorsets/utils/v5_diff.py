"""Comparing the portal's indicator catalogue against Epidata v5's.

A plain set difference over signal names is mostly noise: v5 renamed some
signals and turned others into a key column, so the same series appears under
two names and a subtraction reports it as both missing and new. These helpers
classify each difference instead, so the only things left unexplained are the
ones a human needs to look at.

Pure functions over plain dicts and sets -- the ORM query and the API fetch
live in the ``diff_v5_indicators`` management command.
"""

from dataclasses import dataclass, field

from indicatorsets.utils.constants import MIGRATED_DATASOURCES, V5_NATIVE_ENDPOINTS

# v4 spelled the fill method into the signal name; v5 made it the `fill_method`
# key column, so these suffixes are a dimension of one signal rather than
# signals of their own. Verified on beta_nssp, where every `_fa`/`_fz` name
# collapses onto a base signal v5 still carries.
FILL_METHOD_SUFFIXES = {"_fa": "fill_ave", "_fz": "fill_zero"}

# Signals v5 renamed rather than dropped, keyed by v5 source name. Deciding
# that `total_a` means `positive_a` takes domain knowledge no heuristic has, so
# this map is curated by hand; anything absent from it is reported unclassified
# rather than guessed at.
SIGNAL_RENAMES = {
    "fluview_resp_lab_clinical": {
        "percent_positive": "pct_positive",
        "percent_a": "pct_positive_a",
        "percent_b": "pct_positive_b",
        "total_a": "positive_a",
        "total_b": "positive_b",
    },
}


@dataclass
class SourceDiff:
    """How one portal source's signals line up with its v5 counterpart."""

    portal_source: str
    v5_source: str
    matched: list = field(default_factory=list)
    renamed: list = field(default_factory=list)
    fill_variants: list = field(default_factory=list)
    missing_from_v5: list = field(default_factory=list)
    missing_from_portal: list = field(default_factory=list)

    @property
    def has_gaps(self):
        """True when something is unexplained on either side."""
        return bool(self.missing_from_v5 or self.missing_from_portal)


def resolve_portal_signal(signal, v5_source, v5_signals):
    """Map one portal signal onto the v5 signal carrying the same series.

    Returns ``(v5_name, kind)`` where ``kind`` is ``"exact"``, ``"renamed"`` or
    the fill method the suffix stood for, and ``(None, None)`` when v5 has
    nothing corresponding.

    A fill-method suffix only resolves when its base signal is actually in v5.
    Stripping unconditionally would hide a signal v5 genuinely lacks.
    """
    if signal in v5_signals:
        return signal, "exact"
    renames = SIGNAL_RENAMES.get(v5_source, {})
    renamed = renames.get(signal)
    if renamed and renamed in v5_signals:
        return renamed, "renamed"
    for suffix, fill_method in FILL_METHOD_SUFFIXES.items():
        if signal.endswith(suffix):
            base = signal[: -len(suffix)]
            base = renames.get(base, base)
            if base in v5_signals:
                return base, fill_method
    return None, None


def diff_source(portal_source, v5_source, portal_signals, v5_signals):
    """Classify every signal on both sides of one mapped source pair."""
    diff = SourceDiff(portal_source, v5_source)
    covered = set()
    for signal in sorted(portal_signals):
        v5_name, kind = resolve_portal_signal(signal, v5_source, v5_signals)
        if v5_name is None:
            diff.missing_from_v5.append(signal)
            continue
        covered.add(v5_name)
        if kind == "exact":
            diff.matched.append(signal)
        elif kind == "renamed":
            diff.renamed.append((signal, v5_name))
        else:
            diff.fill_variants.append((signal, v5_name, kind))
    diff.missing_from_portal = sorted(set(v5_signals) - covered)
    return diff


def diff_catalogue(portal_signals_by_source, v5_metadata, source_map=None):
    """Diff every source the app already knows how to route to v5.

    Returns ``(diffs, unmapped_v5_sources, unmapped_portal_sources)``. Anything
    outside ``source_map`` cannot be compared, and is listed by name rather
    than silently dropped.

    ``source_map`` defaults to ``MIGRATED_DATASOURCES``, which keys on
    ``data_source``. Callers that can also resolve a source by its indicator
    set's ``_endpoint`` -- which is how nwss and pophive reach v5 -- pass a
    merged map, otherwise those read as v4-only.
    """
    source_map = MIGRATED_DATASOURCES if source_map is None else source_map
    v5_signals_by_source = {
        source: set(meta.get("signals", [])) for source, meta in v5_metadata.items()
    }
    diffs = []
    # nwss and pophive are served from v5 with no v4 name to migrate, so they
    # are mapped even though they never appear in MIGRATED_DATASOURCES.
    mapped_v5 = set(V5_NATIVE_ENDPOINTS)
    for portal_source in sorted(s for s in portal_signals_by_source if s):
        v5_source = source_map.get(portal_source)
        if not v5_source:
            continue
        mapped_v5.add(v5_source)
        diffs.append(
            diff_source(
                portal_source,
                v5_source,
                portal_signals_by_source[portal_source],
                v5_signals_by_source.get(v5_source, set()),
            )
        )
    unmapped_v5 = sorted(set(v5_signals_by_source) - mapped_v5)
    unmapped_portal = sorted(
        s for s in portal_signals_by_source if s and s not in source_map
    )
    return diffs, unmapped_v5, unmapped_portal


def find_unresolvable_sources(v5_metadata):
    """Return migrated v5 source names that v5 metadata no longer lists.

    ``get_v5_source()`` fails closed, so a source Epidata has renamed stops
    routing to v5 without raising anything -- every user quietly drops back to
    v4. This is the check that notices.
    """
    return sorted(
        {v5 for v5 in MIGRATED_DATASOURCES.values() if v5 not in v5_metadata}
    )
