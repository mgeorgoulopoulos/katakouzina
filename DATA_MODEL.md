# Graph and evidence model

Each `<data_path>/<episode>/edges.tsv` is the canonical public graph for that episode. UTF-8,
tab-separated, with stable edge IDs and one undirected node pair per episode.

Columns:

- `edge_id`, `episode`: stable identifiers.
- `from`, `to`: node labels; preserve meaningful spelling distinctions.
- `relation`, `layer`: analytical relationship and category.
- `status`: CONFIRMED, HYPOTHESIS or REJECTED editorial assessment.
- `decision_basis`: origin of the editorial assessment, independent of runtime human review.
- `evidence_refs`: JSON list containing only `episode`, `start`, `end`, using HH:MM:SS,mmm.
- `reason`: short public analytical rationale; never a transcript excerpt.
- `external_sources`: optional references supporting analysis.

Evidence ranges are half-open: a subtitle overlaps when its start is before the reference
end and its end is after the reference start. Cue numbers are not identifiers. No graph
column stores subtitle text. The reader matches the configured local subtitles by time
range. Without matching local subtitles it displays only the episode and time range.
Existing Why explanations are retained independently of the evidence display.

This is the reference-only graph representation. No format version is declared or bumped.
Do not add inline evidence fields. Preserve IDs and assessments when editing metadata.

The dataset root is selected by config.json data_path. Optional dialogue is read from its srt/<episode>.srt subdirectory. The bundled example-data is synthetic and independent of any external dataset.

## Curation

`<episode>/curation.json` is a tracked UTF-8 JSON object keyed by stable edge ID.
It stores `decision` (unreviewed, accepted, rejected), `why` (exact curator text),
`author` (human, ai, or unknown for legacy notes without attribution), `updated_at` (UTC timestamp; null for migrated notes whose
original edit time is unknown), and `based_on` (SHA-256 of the sorted-key JSON
canonical edge record). Missing entries are unreviewed. IDs are unique per episode.
Multiple graph TSVs in an episode share this curation file and must use unique IDs.

Only human acceptance with a matching fingerprint counts as verified by human.
Changed evidence flags the review for rechecking. Human rejection remains hidden
unless enabled in View even when stale; it is never silently discarded.
`previous_why` optionally preserves the earlier explanation when an edge is rejected,
and is restored when rejection is removed. Existing text is never regenerated.
Saving Why on an unrejected edge clears acceptance, requiring renewed review.
Coordinates remain separate ignored JSON sidecars; local SRTs remain optional.

AI should read the canonical graph and curation together. Put proposed changes in
`<episode>/proposals.json`, keyed by edge ID using the same fields with `author: ai`.
The app does not apply proposals automatically. AI must not overwrite human decisions
or claim human authorship. A human may apply a proposal and then verify it in the app.

Writes use an exclusive `.json.lock` file, reload current content, and atomically
replace JSON after checking for intervening edits. Close the app before external
editing or migration; external writers must honor the same lock protocol. A lock
left by a crash may be removed only after confirming no writer is running.
Legacy SQLite and local note files are migrated with tools/migrate_curation.py in
the application repo; exact backups are retained under ignored `.local` storage.
Curation files are now intended for version control in the data repo.

## Node merge and split

Right-click an edge, choose Merge, then choose the name to retain. Connections
are rewired to that node; self-loops disappear. Duplicate pairs retain the existing
edge of the kept node and combine timestamp references. Existing curation entries
are retained unchanged by ID, including entries for retired edges; changed edge
fingerprints require renewed verification. Original edge metadata is recoverable
from the per-operation `.history` backup. No Why text is rewritten.

Right-click a node and choose Split to enter a unique name. The new node gets a
SPLIT_FROM connection with empty Why and evidence. Optional inheritance copies
original connections using new IDs, without inheriting human review decisions.
Leaf hiding is disabled after splitting so the new connection is visible.
`<graph>.nodes.json` stores node names, including isolated nodes after a merge.
Topology edits apply only to the selected graph, with stale-data checks and backups.

## Soft deletion

Right-click a node or edge and choose Delete. `<graph>.deletions.json` records
node labels and edge IDs with separate deletion flags and timestamped human action
history. Canonical rows, evidence, Why, and review decisions remain unchanged.
Deleting a node hides its incident edges without individually deleting them.
Show rejected does not reveal deleted objects. Deleted nodes remain in the tree;
select one to restore it in the inspector. Deleted edges remain in node connection
lists, marked Deleted; open one to restore it. Restoration preserves prior reviews.
Deletion sidecars belong in version control with the graph.
