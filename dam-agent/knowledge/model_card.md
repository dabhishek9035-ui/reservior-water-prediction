# Forecasting model

## What it predicts
The app forecasts the daily water level of each reservoir at four horizons: 1, 7, 14 and 30 days ahead. Forecasts are made from an "as-of" date using the observations available up to that date.

## Strategies per horizon
The primary model is labelled Delta-LSTM (daily). For each horizon the backend applies the saved best strategy, which can be the Delta-LSTM model, a recent-trend baseline, or persistence. The strategy can therefore differ between the 1, 7, 14 and 30 day horizons.

## Persistence baseline
Persistence assumes the last observed level stays unchanged. It is the simplest possible forecast and is used as a yardstick: a model is only useful if it beats persistence.

## Confidence
Each horizon has a model confidence value between 0 and 100 percent shown next to the persistence comparison. Confidence normally decreases as the horizon gets longer.

## Forecast sources shown in the app
- Trained model: a real forecast from the saved model.
- Historical estimate: for past dates the app can show a simple synthetic estimate instead of a true model backtest. Its confidence range is not calibrated.
- Demo: illustrative data used when no real backend is connected.

## Uncertainty band
When available, the chart shows a shaded band around the forecast. It normally widens with the horizon. It is hidden for historical estimates because it is not calibrated.

## Backtesting in the app
The Predictions page lets you pick an earlier as-of date, step one day at a time or press Play, and compare the forecast with what was actually observed. It reports running mean absolute error, RMSE and how often the model beats persistence.

## Training data and period
The models are trained across Karnataka's 10 major reservoirs: Almatti, Bhadra, Hemavathy, Kabini, Krishna Raja Sagara (KRS), Linganamakki, Malaprabha, Supa, Tungabhadra, and Vani Vilasa Sagara.
- Feature set: 50 input features per step (14-day lookback sequence), including reservoir level, live storage TMC, inflow and outflow rates (cusecs), gridded catchment rainfall (IMD), seasonal cyclic harmonics (sine/cosine day of year), lags, and rolling averages.
- Training split: 3-fold expanding rolling-origin cross-validation over the first 85% of records (from 2014/2018 through late 2023).
- Holdout test period: Chronological final 15% out-of-sample holdout (running from late 2023 through September 2026).

## Reported accuracy and benchmarks
The Delta-LSTM models show strong skill over naive persistence on test holdouts:
- Almatti: t+1 MAE 0.64 TMC (24.4% skill over persistence); t+7 MAE 3.51 TMC (28.4% skill); t+14 MAE 4.75 TMC (46.0% skill); t+30 MAE 6.83 TMC (59.4% skill, R² 0.90).
- Bhadra: t+1 MAE 0.15 TMC (55.7% skill); t+7 MAE 1.05 TMC (46.0% skill); t+14 MAE 2.04 TMC (45.3% skill); t+30 MAE 3.40 TMC (55.7% skill, R² 0.90).
- Hemavathy: t+1 MAE 0.07 TMC (52.0% skill); t+7 MAE 0.63 TMC (33.5% skill); t+14 MAE 1.30 TMC (28.2% skill); t+30 MAE 2.37 TMC (34.6% skill, R² 0.77).
- Kabini: t+1 MAE 0.17 TMC (12.5% skill); t+7 MAE 0.63 TMC (11.2% skill); t+14 MAE 0.92 TMC (19.8% skill); t+30 MAE 1.31 TMC (26.6% skill).
- Malaprabha: t+1 MAE 0.08 TMC (53.7% skill); t+7 MAE 0.62 TMC (44.3% skill); t+14 MAE 1.22 TMC (43.8% skill); t+30 MAE 2.00 TMC (53.6% skill, R² 0.90).
- Tungabhadra: t+1 MAE 0.69 TMC (26.6% skill); t+7 MAE 2.73 TMC (31.5% skill); t+14 MAE 4.23 TMC (40.6% skill); t+30 MAE 7.22 TMC (46.4% skill, R² 0.88).
- For reservoirs with limited test series variation (e.g. Linganamakki and Supa at t+30), the strategy selector automatically switches to the conservative persistence or recent-trend baseline.

## Known limitations
- Emergency gate operations: Unscheduled emergency spillway gate openings or sudden large canal releases driven by upstream state orders cannot be anticipated by hydrologic weather alone.
- Rainfall forecast latency: Catchment rainfall uses observed IMD precipitation; multi-week forecasts depend on seasonal climatology rather than numerical weather prediction (NWP) beyond typical lead times.
- Not a flood warning authority: Forecasts represent predictive decision-support and situational awareness, not official dam discharge orders or civil evacuation alerts. Official flood warnings come from the Karnataka State Natural Disaster Monitoring Centre (KSNDMC) and Central Water Commission (CWC).

