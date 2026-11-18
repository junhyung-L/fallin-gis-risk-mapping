# Fallin: A GIS Prototype for Older-Pedestrian Fall-Risk Mapping

[English](PORTFOLIO.md) | [한국어](PORTFOLIO.ko.md)

## At a glance

Can terrain, pedestrian-environment, and weather conditions identify outdoor
segments that deserve an earlier safety warning for older pedestrians? The
competition proposal (11th Incheon Public Data Use Competition, two-person
team; CTO / overall software-development lead in its role table) describes a
broader service: risk maps, safer routing, caregiver alerts, and smartphone
fall detection. The repository implements the core prototype: Shapefile
loading and CRS conversion, KMA weather retrieval or a demo fallback,
rule-based scoring of GIS segments, and an interactive Folium map.

## Scope: environmental risk, not clinical prediction

Falls also depend on medical history, medication, strength, balance, and
behaviour. The prototype limits itself to publicly observable outdoor
conditions and outputs a relative risk score per pedestrian segment.

| Signal group | Examples used in code | Intended role |
|---|---|---|
| Terrain | mean slope degree | capture walking burden on gradients |
| Pedestrian environment | risk-element count and illuminance | represent pavement and visibility conditions |
| Weather | temperature, humidity, precipitation, snow, wind | represent weather-related slip or freeze conditions |
| Spatial representation | segment geometry and centroids | make priorities inspectable on a map |

## Decisions

**1. Rule score or trained model.** Options: train a classifier on fall
incidents, or score segments with explicit rules. Choice: transparent rules
whose every point traces to a condition. Why: no incident data linked to
segments was available, so a model would have had no target. Cost: weights are
judgement, not estimates, and accuracy cannot be checked until incident or
complaint data is joined.

**2. Weather per segment or one forecast per run.** The competition notebook
fetched weather for each KMA grid cell; the CLI fetches one forecast per run.
Why: simpler, one API call. Cost, shown by `scripts/rule_sensitivity.py`:
weather adds the same 0 to 9 points to every segment, moving segments between
levels without changing their order; under the fallback winter weather no
segment can be Low.

**3. Where to put the level cut-offs.** Notebook: 0–3 / 4–6 / 7+. CLI:
0–5 / 6–10 / 11–20. Why: higher cut-offs flag fewer segments, which suits a
repair-priority list. Cost: in clear weather a segment needs slope above 7
degrees, three or more hazards, and a dark lighting label to be High. Neither
setting was tuned against outcomes, so the cut-off is the first thing to
calibrate.

**4. A demo fallback instead of failing without an API key.** Why: anyone can
run the pipeline. Cost: those maps reflect no real weather; the README and run
log say when the fallback was used.

## Pipeline

```text
Shapefile → GeoPandas load / EPSG:4326 conversion → weather fields → rule score per segment → Folium HTML map
```

- `GISDataLoader` rejects a source without a coordinate reference system and
  converts valid inputs to WGS84 for display.
- `WeatherFetcher` retrieves `TMP`, `REH`, `PTY`, `PCP`, `SNO`, and `WSD` from
  the KMA forecast API when `KMA_SERVICE_KEY` is set; without a key, or after a
  failed request, it returns a fixed winter-precipitation scenario.
- `RiskCalculator` adds five points for slope above 7 degrees and three above 5;
  five for three or more recorded risk elements and three for one or more; plus
  points for cold, high humidity, precipitation, snowfall, and high wind.
  Levels: Low (0–5), Medium (6–10), High (11–20).
- `MapVisualizer` draws all segments as a heatmap and marks high-risk centroids
  in red.

**Code-level finding.** In the notebook's data the lighting column holds
numbers (for example 22786), while the rule checks the text labels "낮음" /
"어두움" (low / dark). On that input the lighting rule never fires, so
clear-weather scores top out at 10 (Medium). The fix is to bin numeric lux
values before scoring; the code is unchanged and the behaviour is documented.

## From proposal to prototype

The proposal considers KMA forecasts, Incheon mobility datasets, road
illuminance/temperature/humidity/foot-traffic data, a fall-incident API, and
KOSIS statistics; the code reads `mean_slope_degree`, `risk_count`, an
illuminance field when present, and weather fields. The proposal includes an
Inju-daero map example and an on-site observation that a yellow-labelled area
contained a crosswalk curb and overpass stairs. Its service plan adds a 500 m
risk map, senior-friendly UI, caregiver notifications, alternative routes,
prevention content and commerce, and B2C/B2G delivery.

## Limitations

- No complete Shapefile sidecars and provenance, incident labels, route outcomes, or field-validation logs are retained.
- Weights are design assumptions, not coefficients calibrated against observed falls; the output cannot support claims of predicting falls at a stated accuracy or of routes reducing accidents.
- Subscription, user-growth, accuracy (for example an 85% fall-prediction target), and fall-reduction numbers in the proposal are plans or targets.
- Push alerts, sensor detection, and safer-route routing are proposed features, not implemented.
- Fallback-weather maps do not represent the weather at any real moment.

## Next steps

- Retain complete Shapefile sidecar files with data source and collection date, where permitted.
- Join governed fall or pedestrian-safety incidents spatially and calibrate the rules with time/spatial separation.
- Log API call time, coordinates, and responses so a map can be reproduced.
- Build the proposed app features (safe routing, caregiver alerts, sensor detection) as separate modules and test them with users.

## Evidence

- [Competition proposal](reports/fallin_incheon_open_data.pdf)
- [Pipeline entry point](main.py)
- [Risk rules](src/risk_calculator.py)
- [GIS loader](src/data_loader.py), [weather module](src/weather.py), and [map visualiser](src/map_visualizer.py)
