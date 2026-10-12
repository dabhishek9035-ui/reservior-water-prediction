# Data sources

## Water level observations
Observed levels come from the app's backend API, one reading per reservoir per day, in feet. The Predictions page shows them as the observed line.

## Reservoir details
Each reservoir record holds its name, reservoir, river, location, district, state, full reservoir level, minimum level, storage figures, nearby places and overflow-affected regions.

## Original provider of the level data
Water level and reservoir telemetry is collected from official monitoring agencies:
- Karnataka State Natural Disaster Monitoring Centre (KSNDMC) daily reservoir bulletins.
- Central Water Commission (CWC) National Water Informatics Centre / India-WRIS portal.
- Karnataka Water Resources Department (WRD) dam management divisions.
- India Meteorological Department (IMD) high-resolution gridded daily rainfall dataset (0.25° x 0.25° grid).

## Update frequency
- Reservoir water levels, gross/live storage, daily inflows (cusecs) and canal/river discharges (cusecs) are recorded daily at 08:30 IST.
- The pipeline ingests telemetry daily; historical records date back from 2014 to present.

## Known gaps and quality issues
- Gauge reading discrepancies: Occasional missing telemetry reporting during sensor calibration or maintenance is handled by linear and spline interpolation for gaps under 3 days.
- Unit conversions: Water levels are standardized in feet (ft) above mean sea level or crest datum; reservoir storage is reported in Thousand Million Cubic feet (TMC); discharges and inflows are in cubic feet per second (cusecs).
- Outlier filtering: Outliers that violate physical conservation of mass (e.g. storage exceeding gross capacity or sudden negative storage) are clipped against engineering capacity limits.

## Other inputs used by the model
The predictive pipeline combines:
- Upstream catchment rainfall: Spatially averaged precipitation across each dam's hydrological catchment basin using IMD gridded rainfall points.
- Antecedent moisture and runoff memory: 3-day, 7-day, and 14-day cumulative precipitation and rolling average inflow rates.
- Seasonal astronomical cycles: Sine and cosine harmonic encodings of the day of the year (DOY) to capture southwest and northeast monsoon arrival and post-monsoon depletion cycles.
- Upstream and downstream discharge rates: Canal releases for irrigation and spillway gate discharges.

