# In-Game Validation Guide

[简体中文](../zh-CN/runtime_validation.md) | [Development](development.md)

This page describes the rules, performance-capture methods and environment to use for in-game validation.

## Queue and upgrade rules

[rgo_queue.py](../../src/eu5autobuild/rgo_queue.py) uses `Location.GetMaxRGOWorkersUnderConstruction`. Empty civil queues count as zero. Nonempty readings validate owner, date, civil count and RGO level; stale readings become unknown and cannot release output records. Workforce reservations may use a conservative upper bound while waiting, but that bound cannot establish project identity or cancellation.

Civil counts and `CountAllInLocation` include estate and foreign-funded projects. `CountMyKindInLocation` is not total occupancy. [construction_slots.py](../../src/eu5autobuild/construction_slots.py) checks location limits and total occupancy. Batches use scan results; a rejected native command releases that project's reservations and moves on without an extra pre-start sampling wait. Mixed-project scheduling requires advancing time to compare actual progress.

[upgrade_queue.py](../../src/eu5autobuild/upgrade_queue.py) reads `Building.GetLevelsUnderUpgrade` during location sampling. Target construction and predecessor upgrade counts describe the same project and must not be added together. Classification, capacity exemptions and old-job deductions require an unreserved predecessor level. Different occupations do not offset each other. `building_type.employment_size` is already in thousands and must not be divided by 1,000 again.

[gui_integer.py](../../src/eu5autobuild/gui_integer.py) handles integer transfer; the float returned by `IntToFixedPoint` cannot directly supply the fixed-point value needed by `MakeScopeValue`.

## Industry, governor and decision rules

Industry snapshots use `Country.GetIndustryPromotions` and `IndustryPromotion.GetArea/GetOwner/GetType` through location-capacity sampling. Missing or stale data gives no preference bonus for that pass without blocking ordinary screening. Revocation and area changes refresh on the next location scan.

Governor calculations use all current proximity sources, including special buildings, policies and temporary effects. Local and naval plans each move only their own ordinary governor sources. Slots account for applicable special seats and construction; no relocation is published above capacity. Periodic refresh catches temporary changes without callbacks. The default relocation threshold is 80%; results are recommendations only.

Manual decisions identify their dedicated entries through localized names, retaining other native decision behavior. The deep-plan Continue action starts work without selecting the native event option; Done becomes available after actual completion. If the date crosses a month, an unexecuted plan expires and the event must allow closing. Reset cleanup is limited to the player's data, keeps templates/settings and clears assignments, tracking and spending without cancelling projects or refunding gold.

## Performance comparison

1. Fully restart to load changes. Run each compared version from the same original save, keeping country, templates, settings, speed and dates identical.
2. Cover scanning on days 2–22, starts from day 23 and the month boundary. Record evaluation counts, actual project locations/types, unprocessed candidates and budget. Less work is not proof of faster work per candidate.
3. Export native profiler CSVs and retain new `debug.log` and `error.log` output. Analyze with `python -B scripts/analyze_native_profile.py <report.csv> --top 15`.
4. Compare total time, call counts and maximum single-call time separately. Inclusive Time contains child calls and cannot be added to them as stall duration. Cumulative milliseconds are not frame times.
5. Disable diagnostic probes for final performance comparisons and record real frame timing or video with identifiable game dates. Exclude saving and manual snapshots from measurement windows.

The [scan probe](../../src/eu5autobuild/scan_probe.py) measures current scan volume, callbacks and concentrated work for performance investigations. It is off by default:

```text
effect eu5ab_probe_scan_start = yes
effect eu5ab_probe_scan_snapshot = yes
effect eu5ab_probe_scan_stop = yes
```

Call `start` once per run, `snapshot` on chosen dates and `stop` at the end. Snapshots contain cumulative counts; differences give interval counts, but maxima cannot be subtracted. Export the CSV, take the snapshot, then reset the profiler. GUI callbacks can complete while paused, causing small boundary differences between the two records.

The probe tracks locations owned at startup without limiting construction. Its state may persist in saves; stop it or begin a fresh run after loading such a save. `effect eu5ab_probe_scan_trace = yes` records the next 32 active diagnostic windows to locate concentrated work. These windows are not exact rendering frames.

## Validation environment

Fully restart the game to load generated files, then use a separate vanilla + CMF + EU5AB playset. Attribute other UI mods' errors to their sources and recheck hot-reload failures after restart. Preserve the original save and use copies for construction, cancellation and advancing time.
