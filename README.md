# Watercolor Weather Dashboard

Creates an **800×480 PNG** weather dashboard from live Open-Meteo data. The layout matches the supplied mock-up:

- today's conditions at the upper left;
- a large current-weather icon in the upper middle;
- six two-hour forecast tiles in a 3×2 grid at the upper right;
- the next five days in a single strip below a divider.

The bundled assets contain day and night watercolor icons for the supported WMO weather codes. Open-Meteo does not require an API key.

## Requirements

- Python 3.10 or newer
- Pillow
- Internet access when requesting live weather data

## Setup

```bash
cd ~/programming/python/weather-dashboard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Generate the dashboard

The defaults use central London and let Open-Meteo choose the local timezone:

```bash
python weather-dashboard.py
```

The generated file is `weather-dashboard.png` in the project directory.

Choose another location and output path:

```bash
python weather-dashboard.py \
  --latitude 53.4808 \
  --longitude -2.2426 \
  --timezone Europe/London \
  --output output/manchester-weather.png
```

Available options:

```text
--latitude FLOAT       Location latitude
--longitude FLOAT      Location longitude
--timezone NAME        Open-Meteo timezone or "auto"
--output PATH          Output PNG path
--icons-dir PATH       Override the bundled icon directory
--timeout SECONDS      HTTP request timeout
--data-file PATH       Render a saved Open-Meteo JSON response offline
```

## Cached or offline data

The `--data-file` option accepts the unmodified JSON returned by the Open-Meteo forecast endpoint. This is useful for testing and reproducible rendering:

```bash
python weather-dashboard.py \
  --data-file open-meteo-response.json \
  --output output/cached-weather.png
```

## Fonts

The renderer uses DejaVu Sans or Liberation Sans when available, then falls back to Pillow's default font. Set `WEATHER_DASHBOARD_FONT` to a `.ttf` file to override the regular and bold font source:

```bash
WEATHER_DASHBOARD_FONT=/path/to/font.ttf python weather-dashboard.py
```

## Data and icon selection

- Current conditions use Open-Meteo's `current` values.
- The six hourly tiles begin at the current local hour and advance in two-hour steps.
- The five-day strip excludes today and uses the following five forecast days.
- Current and hourly icons switch between day and night assets using Open-Meteo's `is_day` value.
- Daily icons use their daytime variants.

If an unexpected WMO code is returned, the cloudy icon is used as a safe fallback.
