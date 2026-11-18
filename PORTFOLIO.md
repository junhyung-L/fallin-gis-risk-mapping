# Fallin: A GIS Fall-Risk Mapping Prototype for Older Pedestrians

[English](PORTFOLIO.md) | [한국어](PORTFOLIO.ko.md) · [README](README.md)

## At a glance

Can terrain, pedestrian-environment, and weather conditions identify outdoor
segments that deserve an earlier safety warning for older pedestrians? The
prototype scores each Incheon pedestrian segment 0–20 with explicit rules and
draws the result on a Folium map. Ranking between segments is set by slope,
hazards, and lighting (up to 11 points); weather (0–9 points) raises every
segment's level together, so the ranking serves maintenance priority and the
level serves same-day alerts.

Idea proposal, 11th Incheon Public Data Use Competition. Software lead in a
two-person team. The proposal describes a broader service (risk maps, safer
routing, caregiver alerts, smartphone fall detection); the repository
implements the core: Shapefile loading and CRS conversion, KMA weather
retrieval or a demo fallback, rule-based scoring, and the interactive map.

**Scope: environmental risk, not clinical prediction.** Falls also depend on
medical history, medication, strength, balance, and behavior. The prototype
limits itself to publicly observable outdoor conditions and outputs a relative
risk score per pedestrian segment.

| Signal group | Examples used in code | Intended role |
|---|---|---|
| Terrain | Mean slope degree | Capture walking burden on gradients |
| Pedestrian environment | Hazard count and illuminance | Represent pavement and visibility conditions |
| Weather | Temperature, humidity, precipitation, snow, wind | Represent slip or freeze conditions |
| Spatial representation | Segment geometry and centroids | Make priorities inspectable on a map |

## Key decisions

**1. Rule score or trained model.**
Options: train a classifier on fall incidents, or score segments with explicit
rules.
Choice: transparent rules whose every point traces to a condition.
Why: no incident data linked to segments was available, so a model would have
had no target.
Cost: weights are judgment, not estimates, and accuracy cannot be checked until
incident or complaint data is joined.

**2. Weather per segment or one forecast per run.**
Options: fetch weather for each KMA grid cell (as the competition notebook
did), or one forecast per run.
Choice: one forecast per run in the CLI.
Why: simpler, one API call.
Cost: weather adds the same 0 to 9 points to every segment, so it moves levels
but not order; under the fallback winter weather no segment can be Low.

**3. Where to put the level cut-offs.**
Options: the notebook's 0–3 / 4–6 / 7+, or higher cut-offs.
Choice: 0–5 / 6–10 / 11–20 in the CLI.
Why: higher cut-offs flag fewer segments, which suits a repair-priority list.
Cost: in clear weather a segment needs slope above 7 degrees, three or more
hazards, and dark lighting (a "dark" label or a reading below 2 lx) to be High. Neither setting was tuned
against outcomes, so the cut-off is the first thing to calibrate.

**4. What to do without an API key.**
Options: stop with an error, or fall back to demo weather.
Choice: a fixed winter-precipitation fallback.
Why: anyone can run the pipeline.
Cost: those maps reflect no real weather; the run log says when the fallback
was used.

## Results

`scripts/rule_sensitivity.py` scores synthetic segments with `RiskCalculator`:

| Segment | Clear weather | Fallback weather |
|---|---|---|
| Flat, no hazards, lit | 0, Low | 9, Medium |
| Slope 6 degrees | 3, Low | 12, High |
| Slope 8 degrees + 3 hazards | 10, Medium | 19, High |
| Slope 8 degrees + 3 hazards + dark | 11, High | 20, High |
| Slope 8 degrees + 3 hazards + 3903 lx | 10, Medium | 19, High |
| Slope 8 degrees + 3 hazards + 1 lx | 11, High | 20, High |

The lighting rule accepts a text label or a numeric lux reading; below 2 lx
counts as dark. 2 lx is the lowest average illuminance among the pedestrian
lighting classes P1–P6 in EN 13201-2:2015 (following CIE 115:2010), set as
`DARK_LUX_THRESHOLD` in `src/config.py`.

Pipeline: Shapefile → GeoPandas load and EPSG:4326 conversion → weather fields
→ rule score per segment → Folium HTML map. `GISDataLoader` rejects a source
without a coordinate reference system; `MapVisualizer` draws all segments as a
heatmap and marks high-risk centroids in red.

The proposal includes an Inju-daero map example and an on-site observation that
a yellow-labeled area contained a crosswalk curb and overpass stairs.

## Limitations

- Weights are design assumptions, not coefficients calibrated against observed falls; there are no incident labels or field-validation logs.
- The 2 lx lighting cut-off comes from a design standard for average illuminance, not from fall data, and a single sensor reading depends on when it was taken.
- Fallback-weather maps do not represent the weather at any real moment.
- Accuracy, subscription, and fall-reduction numbers in the proposal (for example an 85% fall-prediction target) are targets, and push alerts, sensor detection, and safer routing are not implemented.

## Next steps

- Join governed fall or pedestrian-safety incidents spatially and calibrate the
  rules with time and spatial separation.
- Log API call time, coordinates, and responses so a map can be reproduced.
- Build the proposed app features (safe routing, caregiver alerts, sensor
  detection) as separate modules and test them with users.

[Competition proposal](reports/fallin_incheon_open_data.pdf) · [Risk rules](src/risk_calculator.py) · [Pipeline entry point](main.py)
