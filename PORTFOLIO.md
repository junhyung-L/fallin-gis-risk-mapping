# Fallin: A GIS Prototype for Older-Pedestrian Fall-Risk Mapping

[English](PORTFOLIO.md) | [한국어](PORTFOLIO.ko.md)

## At a glance

Fallin starts with a practical question: can terrain, pedestrian-environment, and weather conditions identify outdoor segments that deserve an earlier safety warning for older pedestrians? The competition proposal describes a broader service—risk maps, safer routing, caregiver alerts, and smartphone fall detection. The implemented repository covers a narrower, concrete prototype: score GIS segments with explicit rules and render an interactive Folium map.

The proposal was written by a two-person team, and its role table lists me as CTO / overall software-development lead. The code implements Shapefile loading and CRS conversion, KMA weather retrieval or a demo fallback, rule-based scoring, and HTML map generation. Push alerts, sensor detection, and safer-route routing are proposed product features, not completed or validated repository features.

## Scope: environmental risk, not a clinical prediction

Falls also depend on medical history, medication, strength, balance, and individual behaviour. This prototype deliberately restricts itself to publicly observable outdoor conditions rather than claiming an individual clinical risk score. Its output is a relative risk score for a pedestrian segment.

| Signal group | Examples used in code | Intended role |
|---|---|---|
| Terrain | mean slope degree | capture walking burden on gradients |
| Pedestrian environment | risk-element count and illuminance | represent pavement and visibility conditions |
| Weather | temperature, humidity, precipitation, snow, wind | represent weather-related slip or freeze conditions |
| Spatial representation | segment geometry and centroids | make priorities inspectable on a map |

## Decisions

**1. Rule score or trained model.** Options: train a classifier on fall
incidents, or score segments with explicit rules. No incident data linked to
segments was available, so a trained model would have had no target. We chose
transparent rules whose every point can be traced to a condition. The cost:
the weights are judgement, not estimates, and the score cannot be checked for
accuracy until incident or complaint data is joined.

**2. Weather per segment or one forecast per run.** The competition notebook
fetched weather for each KMA grid cell. The maintained CLI fetches one
forecast for the whole run, which is simpler and needs one API call. The cost,
shown by `scripts/rule_sensitivity.py`: weather now adds the same 0 to 9
points to every segment. It moves segments between levels but never changes
their order, and under the fallback winter weather no segment can be Low.

**3. Where to put the level cut-offs.** The notebook used 0–3 / 4–6 / 7+; the
CLI uses 0–5 / 6–10 / 11–20. Higher cut-offs flag fewer segments, which suits
a repair-priority list, but in clear weather a segment needs slope above 7
degrees, three or more hazards, and a dark lighting label to be High. Neither
setting was tuned against outcomes, so the cut-off is the first thing to
calibrate.

**4. A demo fallback instead of failing without an API key.** The fallback lets
anyone run the pipeline, at the cost of maps that reflect no real weather. The
README and log say when the fallback was used.

## Implemented pipeline

`main.py` follows a direct workflow:

```text
Shapefile → GeoPandas load / EPSG:4326 conversion → weather fields → rule score per segment → Folium HTML map
```

`GISDataLoader` refuses a source without a coordinate reference system and converts valid inputs to WGS84 for display. `WeatherFetcher` retrieves `TMP`, `REH`, `PTY`, `PCP`, `SNO`, and `WSD` from the KMA forecast API when `KMA_SERVICE_KEY` is set. Without a key—or after a failed request—it returns a fixed winter-precipitation scenario so the demo can still run.

`RiskCalculator` makes the scoring assumptions visible. A slope above 7 degrees adds five points; a slope above 5 adds three. Three or more recorded risk elements add five points, while one or more add three. Cold temperature, high humidity, precipitation, snowfall, and high wind also contribute. Scores are grouped as Low (0–5), Medium (6–10), and High (11–20). `MapVisualizer` draws all segments as a heatmap and marks high-risk centroids in red.

The deterministic weather fallback makes demonstration possible, but it does not represent the weather at a real historical moment. API use and timestamp need to be recorded when interpreting a generated map.

## From proposal to prototype

The proposal considers KMA forecasts, Incheon mobility datasets, road illuminance/temperature/humidity/foot-traffic data, a fall-incident API, and KOSIS statistics. The implementation reads `mean_slope_degree`, `risk_count`, an illuminance field when present, and weather fields. The proposal also includes an Inju-daero map example and an on-site observation that a yellow-labelled area contained a crosswalk curb and overpass stairs.

The wider service plan includes a 500 m risk map, senior-friendly UI, caregiver notifications, alternative routes, prevention content, and B2C/B2G delivery. That is valuable product and policy framing, but proposed subscription, user-growth, accuracy (for example an 85% fall-prediction target), and fall-reduction numbers in the report are plans or targets, not measured outcomes from this codebase.

## A code-level finding

In the notebook's loaded data the lighting column holds numbers (for example
22786), while the rule checks for the text labels "낮음" / "어두움" (low /
dark). On that input the lighting rule never fires, so clear-weather scores
top out at 10 (Medium). The fix is to bin the numeric lux values before
scoring. I left the code unchanged and documented the behaviour.

## Honest result boundary and next step

The output is an HTML map that assigns a score and risk level to supplied GIS segments. The repository does not retain complete Shapefile sidecars and provenance, incident labels, route outcomes, or field-validation logs. The weights are design assumptions, not coefficients calibrated against observed falls. It therefore cannot support claims that it predicts falls at a stated accuracy or that its routes reduce accidents.

What is implemented is still a meaningful prototype: it links spatial data, changing weather inputs, transparent rules, and a readable map. The next iteration should retain complete data provenance, join governed incident or safety records spatially, validate with time/spatial separation, record API calls, and test the proposed app features independently.

## Evidence

- [Competition proposal](reports/fallin_incheon_open_data.pdf)
- [Pipeline entry point](main.py)
- [Risk rules](src/risk_calculator.py)
- [GIS loader](src/data_loader.py), [weather module](src/weather.py), and [map visualiser](src/map_visualizer.py)
