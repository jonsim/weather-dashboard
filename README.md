# Watercolor Weather Dashboard

Creates an **800×480 PNG** weather dashboard from live Open-Meteo data. It is
packaged with a `src` layout and managed with [uv](https://docs.astral.sh/uv/).
The dashboard contains:

- today's conditions at the upper left;
- a large current-weather icon in the upper middle;
- six two-hour forecast tiles in a 3×2 grid at the upper right;
- the next five days in a single strip below a divider.

The bundled assets contain day and night icons in high-contrast and watercolor
themes for every supported WMO weather code. Open-Meteo does not require an API
key.

## Set up the project

Install the application and its development dependencies:

```console
uv sync --group dev
```

## Generate the dashboard

The defaults use central London and let Open-Meteo choose the local timezone:

```console
uv run weather-dashboard
```

The generated file is `weather-dashboard.png` in the project directory.

Choose another location and output path:

```console
uv run weather-dashboard \
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
--theme NAME           Bundled icon theme: high-contrast or watercolor
--icons-dir PATH       Override the selected theme with a custom icon directory
--timeout SECONDS      HTTP request timeout
--data-file PATH       Render a saved Open-Meteo JSON response offline
--dither               Dither to the six-colour Spectra 6 display palette
```

The new high-contrast artwork is used by default because it survives Spectra 6
dithering particularly well. Select the original watercolor artwork with:

```console
uv run weather-dashboard --theme watercolor
```

The `--icons-dir` option takes precedence over `--theme` so existing custom icon
packs continue to work.

For a 7.3-inch Inky Frame with a Spectra 6 panel, generate a display-ready
palette PNG with Floyd–Steinberg dithering:

```console
uv run weather-dashboard --dither
```

The dithered PNG contains exactly the panel's six native colours. This lets the
Inky Frame use the prepared pixels directly instead of dithering the full-colour
dashboard while loading it.

## Cached or offline data

The `--data-file` option accepts the unmodified JSON returned by the Open-Meteo
forecast endpoint. This is useful for testing and reproducible rendering:

```console
uv run weather-dashboard \
  --data-file open-meteo-response.json \
  --output output/cached-weather.png
```

## Fonts

The renderer uses DejaVu Sans or Liberation Sans when available, then falls back
to Pillow's default font. Set `WEATHER_DASHBOARD_FONT` to a `.ttf` file to
override the regular and bold font source:

```console
WEATHER_DASHBOARD_FONT=/path/to/font.ttf uv run weather-dashboard
```

## Data and icon selection

- Current conditions use Open-Meteo's `current` values.
- The six hourly tiles begin at the current local hour and advance in two-hour
  steps.
- The five-day strip excludes today and uses the following five forecast days.
- Current and hourly icons switch between day and night assets using Open-Meteo's
  `is_day` value.
- Daily icons use their daytime variants.

If an unexpected WMO code is returned, the cloudy icon is used as a safe fallback.

## Run the tests

The unit tests use Python's standard `unittest` framework:

```console
uv run python -m unittest discover -s tests
```

Run the same tests with coverage and print the missing lines:

```console
uv run coverage run -m unittest discover -s tests
uv run coverage report
```

## Run the checks

Install the Git hook once after cloning the project:

```console
uv run pre-commit install
```

Run every check over the repository whenever needed:

```console
uv run pre-commit run --all-files
```
