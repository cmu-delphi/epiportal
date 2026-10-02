"""Compare the portal's indicator catalogue against Epidata v5's.

Run it to answer "what has v5 got that we don't list, and what do we list that
v5 has dropped?" -- deliberately, when curating the catalogue, rather than as a
test: v5 gaining a signal is normal and should not turn a suite red.

The one genuine error it does raise is a migrated source vanishing from v5
metadata, because ``get_v5_source()`` fails closed and every user would quietly
drop back to v4 with nothing logged.
"""

import json
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from indicators.models import Indicator
from indicatorsets.utils.constants import MIGRATED_DATASOURCES, V5_NATIVE_ENDPOINTS
from indicatorsets.utils.epidata import get_v5_metadata
from indicatorsets.utils.v5_diff import diff_catalogue, find_unresolvable_sources


# Generated output, kept out of docs/ so it is never confused with the
# hand-written prose there. BASE_DIR is the src/ package, so the directory
# sits one level up beside it.
DEFAULT_MARKDOWN_PATH = Path(settings.BASE_DIR).parent / "reports" / (
    "v4-to-v5-catalogue-diff.md"
)


def portal_signals_by_source():
    """Bucket every indicator name under its source name.

    Sourceless rows are kept out: without a source there is nothing to compare
    them against. The command reports how many were skipped.
    """
    grouped = defaultdict(set)
    for source_name, name in Indicator.objects.values_list("source__name", "name"):
        if source_name:
            grouped[source_name].add(name)
    return grouped


def source_map():
    """Portal source name -> v5 source name, by both routes the app uses.

    MIGRATED_DATASOURCES keys on ``data_source``; nwss and pophive instead
    reach v5 through their indicator set's ``_endpoint``, so their portal
    source names (``beta_nwss``, ``beta_cosmos_pophive``) never appear there.
    Without them the diff would report 39 indicators as v4-only that v5 serves
    today.
    """
    native = {
        source_name: endpoint
        for endpoint, source_name in Indicator.objects.filter(
            source__isnull=False, indicator_set__epidata_endpoint__in=V5_NATIVE_ENDPOINTS
        )
        .values_list("indicator_set__epidata_endpoint", "source__name")
        .distinct()
    }
    return {**MIGRATED_DATASOURCES, **native}


def v4_only_summary(diffs, unmapped_portal, portal):
    """Indicators the portal holds that v5 cannot serve, and why.

    Two separate causes: a signal missing from a source that has otherwise
    migrated, and every signal of a source v5 has no counterpart for at all.
    The second dwarfs the first, so reporting only the first is misleading.
    """
    inside_migrated = sum(len(d.missing_from_v5) for d in diffs)
    in_missing_sources = sum(len(portal[s]) for s in unmapped_portal)
    return {
        "total": inside_migrated + in_missing_sources,
        "inside_migrated_sources": inside_migrated,
        "in_sources_v5_lacks": in_missing_sources,
        "sources": unmapped_portal,
    }


class Command(BaseCommand):
    help = "Compare the portal's indicator catalogue against Epidata v5."

    def add_arguments(self, parser):
        parser.add_argument(
            "--gaps-only",
            action="store_true",
            help="Only show mapped sources that have unexplained differences.",
        )
        parser.add_argument(
            "--markdown",
            nargs="?",
            const=str(DEFAULT_MARKDOWN_PATH),
            dest="markdown_path",
            metavar="PATH",
            help=(
                "Write the diff as a Markdown document. Defaults to "
                f"{DEFAULT_MARKDOWN_PATH}; pass a PATH to write elsewhere."
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit the diff as JSON instead of a report.",
        )

    def handle(self, *args, **options):
        if options["as_json"] and options["markdown_path"]:
            raise CommandError("Pass either --json or --markdown, not both.")
        metadata = get_v5_metadata()
        if not metadata:
            raise CommandError(
                "Epidata v5 metadata is empty or unreachable; nothing to compare."
            )

        portal = portal_signals_by_source()
        skipped = Indicator.objects.filter(source__isnull=True).count()
        diffs, unmapped_v5, unmapped_portal = diff_catalogue(
            portal, metadata, source_map=source_map()
        )
        unresolvable = find_unresolvable_sources(metadata)
        v4_only = v4_only_summary(diffs, unmapped_portal, portal)

        if options["as_json"]:
            self._write_json(diffs, unmapped_v5, unmapped_portal, unresolvable, v4_only)
        elif options["markdown_path"]:
            self._write_markdown_file(
                Path(options["markdown_path"]),
                diffs, unmapped_v5, unresolvable, v4_only, metadata, portal, skipped,
            )
        else:
            self._write_report(
                diffs, unmapped_v5, unmapped_portal, unresolvable, v4_only,
                metadata, portal, skipped, options["gaps_only"],
            )

        if unresolvable:
            raise CommandError(
                "These migrated sources are missing from v5 metadata, so they "
                "silently fall back to v4: " + ", ".join(unresolvable)
            )

    def _write_markdown_file(
        self, path, diffs, unmapped_v5, unresolvable, v4_only, metadata, portal, skipped
    ):
        """Render the document and write it, creating the directory if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self._markdown(
                diffs, unmapped_v5, unresolvable, v4_only, metadata, portal, skipped
            )
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))

    def _markdown(
        self, diffs, unmapped_v5, unresolvable, v4_only, metadata, portal, skipped
    ):
        """Render the diff as a document meant to be read, not scrolled past.

        Generated rather than hand-written: every number here moves as Epidata
        publishes signals, so a snapshot someone edits by hand goes stale
        without anyone noticing.
        """
        lines = []
        add = lines.append
        v5_signals = sum(len(m.get("signals", [])) for m in metadata.values())
        portal_signals = sum(len(v) for v in portal.values())
        reachable = portal_signals - v4_only["total"]

        add("# Epidata v5 catalogue diff")
        add("")
        add(
            f"Generated by `manage.py diff_v5_indicators --markdown` on "
            f"{timezone.now():%Y-%m-%d}. Regenerate rather than edit."
        )
        add("")
        add("## Totals")
        add("")
        add("| | count |")
        add("|---|---|")
        add(f"| Portal sources | {len(portal)} |")
        add(f"| Portal indicators with a source | {portal_signals} |")
        add(f"| Sourceless indicators (excluded) | {skipped} |")
        add(f"| v5 sources | {len(metadata)} |")
        add(f"| v5 signals | {v5_signals} |")
        add("")
        add("Of the indicators that have a source:")
        add("")
        add("| | count |")
        add("|---|---|")
        add(f"| Reachable from v5 | {reachable} |")
        add(f"| **v4-only** | **{v4_only['total']}** |")
        add(
            f"| \u2014 inside sources that did migrate | "
            f"{v4_only['inside_migrated_sources']} |"
        )
        add(
            f"| \u2014 in {len(v4_only['sources'])} sources v5 has no counterpart "
            f"for | {v4_only['in_sources_v5_lacks']} |"
        )

        add("")
        add("## Mapped sources")
        add("")
        add(
            "| portal source | v5 source | matched | renamed | fill_method | "
            "only in v5 | only in portal |"
        )
        add("|---|---|--:|--:|--:|--:|--:|")
        for diff in diffs:
            add(
                f"| {diff.portal_source} | {diff.v5_source} | {len(diff.matched)} | "
                f"{len(diff.renamed)} | {len(diff.fill_variants)} | "
                f"{len(diff.missing_from_portal)} | {len(diff.missing_from_v5)} |"
            )

        for diff in diffs:
            add("")
            add(f"### {diff.portal_source} \u2192 {diff.v5_source}")
            add("")
            add(f"**Matched ({len(diff.matched)}):** {self._code_list(diff.matched)}")
            if diff.renamed:
                add("")
                add(f"**Renamed ({len(diff.renamed)}):**")
                add("")
                for signal, v5_name in diff.renamed:
                    add(f"- `{signal}` \u2192 `{v5_name}`")
            if diff.fill_variants:
                add("")
                add(f"**fill_method variants ({len(diff.fill_variants)}):**")
                add("")
                for signal, v5_name, fill_method in diff.fill_variants:
                    add(f"- `{signal}` \u2192 `{v5_name}` + `fill_method={fill_method}`")
            add("")
            add(
                f"**Only in v5 ({len(diff.missing_from_portal)}):** "
                f"{self._code_list(diff.missing_from_portal)}"
            )
            add("")
            add(
                f"**Only in portal ({len(diff.missing_from_v5)}):** "
                f"{self._code_list(diff.missing_from_v5)}"
            )

        add("")
        add("## v5 sources the portal has no mapping for")
        add("")
        if unmapped_v5:
            add("| v5 source | signals |")
            add("|---|--:|")
            for source in unmapped_v5:
                add(f"| {source} | {len(metadata[source].get('signals', []))} |")
        else:
            add("None.")

        add("")
        add("## v4-only portal sources")
        add("")
        add(
            f"{len(v4_only['sources'])} sources v5 has no counterpart for, holding "
            f"{v4_only['in_sources_v5_lacks']} indicators:"
        )
        add("")
        add(self._code_list(v4_only["sources"]))

        if unresolvable:
            add("")
            add("## Migrated sources missing from v5 metadata")
            add("")
            add(
                "These route to v5 in `MIGRATED_DATASOURCES` but v5 no longer "
                "lists them, so every request silently falls back to v4:"
            )
            add("")
            add(self._code_list(unresolvable))

        add("")
        add("## Known limitations")
        add("")
        add(
            f"- **{skipped} sourceless indicators are excluded.** Without a "
            "source there is nothing to compare them against."
        )
        add(
            "- **Several portal sources map to one v5 source.** Each is "
            "compared against the full v5 signal set independently, so one "
            "portal source's signals appear as the other's \"only in v5\" "
            "gaps. `beta_nssp` and `beta_nssp_github` are complementary halves "
            "of `nssp` and inflate each other's counts this way."
        )
        add(
            "- **`SIGNAL_RENAMES` is curated by hand.** A rename nobody has "
            "recorded yet shows up as a gap on both sides rather than a match."
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _code_list(values):
        return ", ".join(f"`{value}`" for value in values) if values else "\u2014"

    def _write_json(self, diffs, unmapped_v5, unmapped_portal, unresolvable, v4_only):
        self.stdout.write(
            json.dumps(
                {
                    "sources": [
                        {
                            "portal_source": d.portal_source,
                            "v5_source": d.v5_source,
                            "matched": d.matched,
                            "renamed": [list(pair) for pair in d.renamed],
                            "fill_variants": [list(t) for t in d.fill_variants],
                            "missing_from_v5": d.missing_from_v5,
                            "missing_from_portal": d.missing_from_portal,
                        }
                        for d in diffs
                    ],
                    "v4_only": v4_only,
                    "unmapped_v5_sources": unmapped_v5,
                    "unmapped_portal_sources": unmapped_portal,
                    "unresolvable_migrated_sources": unresolvable,
                },
                indent=2,
            )
        )

    def _write_report(
        self, diffs, unmapped_v5, unmapped_portal, unresolvable, v4_only,
        metadata, portal, skipped, gaps_only,
    ):
        write = self.stdout.write
        v5_signals = sum(len(m.get("signals", [])) for m in metadata.values())
        portal_signals = sum(len(v) for v in portal.values())

        write(self.style.MIGRATE_HEADING("Epidata v5 catalogue diff"))
        write(
            f"  portal: {len(portal)} sources / {portal_signals} indicators "
            f"({skipped} sourceless, excluded from the comparison)"
        )
        write(f"  v5:     {len(metadata)} sources / {v5_signals} signals")

        # portal_signals already counts only sourced indicators, so the
        # sourceless ones are not a further deduction here.
        reachable = portal_signals - v4_only["total"]
        write("")
        write(self.style.MIGRATE_HEADING("Of the indicators that have a source"))
        write(f"  reachable from v5: {reachable}")
        write(
            self.style.WARNING(
                f"  v4-only:           {v4_only['total']}"
            )
        )
        write(
            f"      {v4_only['inside_migrated_sources']} inside sources that "
            "did migrate (listed below as \"only in portal\")"
        )
        write(
            f"      {v4_only['in_sources_v5_lacks']} in "
            f"{len(v4_only['sources'])} sources v5 has no counterpart for"
        )

        write("")
        write(self.style.MIGRATE_HEADING("Mapped sources"))
        shown = [d for d in diffs if d.has_gaps or not gaps_only]
        if not shown:
            write("  every mapped source lines up")
        for diff in shown:
            write(f"  {diff.portal_source} -> {diff.v5_source}")
            explained = [f"{len(diff.matched)} matched"]
            if diff.renamed:
                explained.append(f"{len(diff.renamed)} renamed")
            if diff.fill_variants:
                explained.append(f"{len(diff.fill_variants)} fill_method variants")
            write(f"      {', '.join(explained)}")
            for signal in diff.matched:
                write(f"      matched:     {signal}")
            for signal, v5_name in diff.renamed:
                write(f"      renamed:     {signal} -> {v5_name}")
            for signal, v5_name, fill_method in diff.fill_variants:
                write(
                    f"      fill_method: {signal} -> {v5_name} "
                    f"(fill_method={fill_method})"
                )
            for signal in diff.missing_from_portal:
                write(self.style.WARNING(f"      only in v5:     {signal}"))
            for signal in diff.missing_from_v5:
                write(self.style.WARNING(f"      only in portal: {signal}"))

        if unmapped_v5:
            write("")
            write(self.style.MIGRATE_HEADING("v5 sources the portal has no mapping for"))
            for source in unmapped_v5:
                count = len(metadata[source].get("signals", []))
                write(f"  {source} ({count} signals)")

        if unmapped_portal:
            write("")
            write(
                self.style.MIGRATE_HEADING(
                    "v4-only portal sources (v5 has no counterpart)"
                )
            )
            write(f"  {len(unmapped_portal)}: {', '.join(unmapped_portal)}")

        if unresolvable:
            write("")
            write(self.style.ERROR("Migrated sources missing from v5 metadata:"))
            for source in unresolvable:
                write(self.style.ERROR(f"  {source}"))
