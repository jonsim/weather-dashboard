#!/usr/bin/env python3
"""Render an 800x480 watercolor weather dashboard from Open-Meteo data."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH = 800
HEIGHT = 480

BACKGROUND = (249, 247, 240)
TEXT = (38, 48, 64)
MUTED_TEXT = (58, 76, 101)
LINE = (195, 218, 228)
TILE_FILL = (251, 250, 245)

# The palette definitions and 0.5 blend match Pimoroni's E673 Spectra 6
# driver. The blended values approximate the pigments closely enough for
# useful error diffusion while retaining the display's six native colours.
SPECTRA6_DESATURATED_PALETTE = (
    (0, 0, 0),
    (255, 255, 255),
    (255, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
    (0, 255, 0),
)
SPECTRA6_SATURATED_PALETTE = (
    (0, 0, 0),
    (161, 164, 165),
    (208, 190, 71),
    (156, 72, 75),
    (61, 59, 94),
    (58, 91, 70),
)
SPECTRA6_SATURATION = 0.5

WMO_DESCRIPTIONS = {
    0: ("Sunny", "Clear"),
    1: ("Mainly sunny", "Mainly clear"),
    2: ("Partly cloudy", "Partly cloudy"),
    3: ("Cloudy", "Cloudy"),
    45: ("Foggy", "Foggy"),
    48: ("Rime fog", "Rime fog"),
    51: ("Light drizzle", "Light drizzle"),
    53: ("Drizzle", "Drizzle"),
    55: ("Heavy drizzle", "Heavy drizzle"),
    56: ("Light freezing drizzle", "Light freezing drizzle"),
    57: ("Freezing drizzle", "Freezing drizzle"),
    61: ("Light rain", "Light rain"),
    63: ("Rain", "Rain"),
    65: ("Heavy rain", "Heavy rain"),
    66: ("Light freezing rain", "Light freezing rain"),
    67: ("Freezing rain", "Freezing rain"),
    71: ("Light snow", "Light snow"),
    73: ("Snow", "Snow"),
    75: ("Heavy snow", "Heavy snow"),
    77: ("Snow grains", "Snow grains"),
    80: ("Light showers", "Light showers"),
    81: ("Showers", "Showers"),
    82: ("Heavy showers", "Heavy showers"),
    85: ("Light snow showers", "Light snow showers"),
    86: ("Snow showers", "Snow showers"),
    95: ("Thunderstorm", "Thunderstorm"),
    96: ("Thunderstorm with light hail", "Thunderstorm with light hail"),
    99: ("Thunderstorm with hail", "Thunderstorm with hail"),
}


@dataclass(frozen=True)
class ForecastPoint:
    time: datetime
    temperature: int
    code: int
    is_day: bool


@dataclass(frozen=True)
class DailyPoint:
    time: datetime
    temperature: int
    code: int


@dataclass(frozen=True)
class DashboardData:
    current: ForecastPoint
    high: int
    low: int
    hourly: list[ForecastPoint]
    daily: list[DailyPoint]


def fetch_open_meteo(
    latitude: float,
    longitude: float,
    timezone: str,
    timeout: float,
) -> dict[str, Any]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,is_day",
        "hourly": "temperature_2m,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": timezone,
        "forecast_days": 6,
        "temperature_unit": "celsius",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "watercolor-weather-dashboard/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not retrieve weather data: {exc}") from exc


def load_weather_file(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read weather data from {path}: {exc}") from exc


def rounded(value: float) -> int:
    return int(round(float(value)))


def build_dashboard_data(payload: dict[str, Any]) -> DashboardData:
    try:
        current_raw = payload["current"]
        hourly_raw = payload["hourly"]
        daily_raw = payload["daily"]

        current_time = datetime.fromisoformat(current_raw["time"])
        current = ForecastPoint(
            time=current_time,
            temperature=rounded(current_raw["temperature_2m"]),
            code=int(current_raw["weather_code"]),
            is_day=bool(current_raw["is_day"]),
        )

        hourly_times = [datetime.fromisoformat(value) for value in hourly_raw["time"]]
        start = current_time.replace(minute=0, second=0, microsecond=0)
        hourly: list[ForecastPoint] = []
        for offset in range(0, 12, 2):
            target = start + timedelta(hours=offset)
            try:
                index = next(i for i, value in enumerate(hourly_times) if value >= target)
            except StopIteration as exc:
                raise ValueError("Hourly forecast does not cover the next 10 hours") from exc
            hourly.append(
                ForecastPoint(
                    time=hourly_times[index],
                    temperature=rounded(hourly_raw["temperature_2m"][index]),
                    code=int(hourly_raw["weather_code"][index]),
                    is_day=bool(hourly_raw["is_day"][index]),
                )
            )

        daily_times = [datetime.fromisoformat(value) for value in daily_raw["time"]]
        if len(daily_times) < 6:
            raise ValueError("Daily forecast does not contain five future days")

        high = rounded(daily_raw["temperature_2m_max"][0])
        low = rounded(daily_raw["temperature_2m_min"][0])
        daily = [
            DailyPoint(
                time=daily_times[index],
                temperature=rounded(daily_raw["temperature_2m_max"][index]),
                code=int(daily_raw["weather_code"][index]),
            )
            for index in range(1, 6)
        ]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unexpected Open-Meteo response: {exc}") from exc

    return DashboardData(
        current=current,
        high=high,
        low=low,
        hourly=hourly,
        daily=daily,
    )


def font_path(weight: str) -> Path | None:
    custom = os.environ.get("WEATHER_DASHBOARD_FONT")
    if custom:
        candidate = Path(custom).expanduser()
        if candidate.is_file():
            return candidate

    candidates = {
        "bold": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ],
        "regular": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ],
    }
    for value in candidates[weight]:
        candidate = Path(value)
        if candidate.is_file():
            return candidate
    return None


def load_font(size: int, weight: str = "regular") -> ImageFont.ImageFont:
    path = font_path(weight)
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size=size)


def paper_background() -> Image.Image:
    base = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    noise = Image.effect_noise((WIDTH, HEIGHT), 5.0)
    grain = ImageOps.colorize(noise, black=(239, 237, 230), white=(255, 253, 247))
    return Image.blend(base, grain, 0.10)


def icon_path(icons_dir: Path, code: int, is_day: bool) -> Path:
    state = "day" if is_day else "night"
    requested = icons_dir / f"wmo-{code}-{state}.png"
    if requested.is_file():
        return requested
    day_fallback = icons_dir / f"wmo-{code}-day.png"
    if day_fallback.is_file():
        return day_fallback
    return icons_dir / f"wmo-3-{state}.png"


def paste_icon(
    canvas: Image.Image,
    icons_dir: Path,
    code: int,
    is_day: bool,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    max_width = right - left
    max_height = bottom - top
    with Image.open(icon_path(icons_dir, code, is_day)) as source:
        icon = source.convert("RGBA")
        scale = min(max_width / icon.width, max_height / icon.height)
        resized = (
            max(1, round(icon.width * scale)),
            max(1, round(icon.height * scale)),
        )
        icon = icon.resize(resized, Image.Resampling.LANCZOS)
        x = left + (max_width - icon.width) // 2
        y = top + (max_height - icon.height) // 2
        canvas.paste(icon, (x, y), icon)


def centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] = TEXT,
) -> None:
    draw.text(xy, value, font=font, fill=fill, anchor="mm")


def hour_label(value: datetime) -> str:
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{hour}{suffix}"


def description(code: int, is_day: bool) -> str:
    values = WMO_DESCRIPTIONS.get(code, ("Cloudy", "Cloudy"))
    return values[0 if is_day else 1]


def dither_for_spectra6(image: Image.Image) -> Image.Image:
    """Dither an RGB image to the Inky Frame's six native colours."""
    palette_values = [
        int(saturated * SPECTRA6_SATURATION + desaturated * (1.0 - SPECTRA6_SATURATION))
        for saturated_colour, desaturated_colour in zip(
            SPECTRA6_SATURATED_PALETTE,
            SPECTRA6_DESATURATED_PALETTE,
        )
        for saturated, desaturated in zip(saturated_colour, desaturated_colour)
    ]
    palette = Image.new("P", (1, 1))
    palette.putpalette(palette_values)
    dithered = image.convert("RGB").quantize(
        colors=6,
        palette=palette,
        dither=Image.Dither.FLOYDSTEINBERG,
    )
    dithered.putpalette(
        [component for colour in SPECTRA6_DESATURATED_PALETTE for component in colour]
    )
    return dithered


def render_dashboard(
    data: DashboardData,
    icons_dir: Path,
    output: Path,
    dither: bool = False,
) -> None:
    if not icons_dir.is_dir():
        raise RuntimeError(f"Icon directory does not exist: {icons_dir}")

    canvas = paper_background()
    draw = ImageDraw.Draw(canvas)

    regular_13 = load_font(13)
    regular_15 = load_font(15)
    regular_18 = load_font(18)
    regular_20 = load_font(20)
    regular_22 = load_font(22)
    regular_27 = load_font(27)
    bold_20 = load_font(20, "bold")
    bold_82 = load_font(82, "bold")

    # Current conditions: upper-left.
    draw.text((43, 61), "TODAY", font=regular_22, fill=MUTED_TEXT)
    draw.text((39, 89), f"{data.current.temperature}°", font=bold_82, fill=TEXT)
    draw.text(
        (43, 201),
        description(data.current.code, data.current.is_day),
        font=regular_27,
        fill=TEXT,
    )
    draw.text(
        (43, 241),
        f"High {data.high}°  ·  Low {data.low}°",
        font=regular_18,
        fill=MUTED_TEXT,
    )

    # Today's large icon: upper-middle.
    paste_icon(
        canvas,
        icons_dir,
        data.current.code,
        data.current.is_day,
        (247, 44, 493, 292),
    )

    # Six bi-hourly tiles: upper-right, 3x2.
    tile_left = 496
    tile_top = 46
    tile_width = 91
    tile_height = 112
    tile_gap_x = 6
    tile_gap_y = 8
    for index, point in enumerate(data.hourly):
        row, column = divmod(index, 3)
        left = tile_left + column * (tile_width + tile_gap_x)
        top = tile_top + row * (tile_height + tile_gap_y)
        right = left + tile_width
        bottom = top + tile_height
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=9,
            fill=TILE_FILL,
            outline=LINE,
            width=1,
        )
        centered_text(draw, ((left + right) // 2, top + 17), hour_label(point.time), regular_13)
        paste_icon(canvas, icons_dir, point.code, point.is_day, (left + 18, top + 31, right - 18, top + 79))
        centered_text(
            draw,
            ((left + right) // 2, top + 95),
            f"{point.temperature}°",
            bold_20,
        )

    # Divider and five-day forecast strip.
    draw.line((24, 311, 776, 311), fill=LINE, width=1)
    daily_left = 25
    daily_width = 150
    for index, point in enumerate(data.daily):
        left = daily_left + index * daily_width
        right = left + daily_width
        center = (left + right) // 2
        if index:
            draw.line((left, 333, left, 466), fill=LINE, width=1)
        centered_text(draw, (center, 337), point.time.strftime("%a").upper(), regular_15)
        paste_icon(canvas, icons_dir, point.code, True, (left + 43, 352, right - 43, 418))
        centered_text(draw, (center, 446), f"{point.temperature}°", regular_20)

    output.parent.mkdir(parents=True, exist_ok=True)
    output_image = dither_for_spectra6(canvas) if dither else canvas
    output_image.save(output, format="PNG", optimize=True)


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Create an 800x480 watercolor weather dashboard PNG.",
    )
    parser.add_argument("--latitude", type=float, default=51.5072, help="Latitude (default: London)")
    parser.add_argument("--longitude", type=float, default=-0.1276, help="Longitude (default: London)")
    parser.add_argument(
        "--timezone",
        default="auto",
        help="Open-Meteo timezone, such as Europe/London (default: auto)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_dir / "weather-dashboard.png",
        help="Output PNG path",
    )
    parser.add_argument(
        "--icons-dir",
        type=Path,
        default=project_dir / "assets" / "icons",
        help="Directory containing wmo-CODE-day/night.png assets",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        help="Read a saved Open-Meteo JSON response instead of requesting live data",
    )
    parser.add_argument(
        "--dither",
        action="store_true",
        help="Dither the PNG to the six-colour Spectra 6 display palette",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = (
            load_weather_file(args.data_file.expanduser())
            if args.data_file
            else fetch_open_meteo(args.latitude, args.longitude, args.timezone, args.timeout)
        )
        data = build_dashboard_data(payload)
        output = args.output.expanduser().resolve()
        render_dashboard(data, args.icons_dir.expanduser().resolve(), output, dither=args.dither)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
