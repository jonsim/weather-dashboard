import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

from weather_dashboard import (
    DEFAULT_THEME,
    ICONS_ROOT,
    SPECTRA6_OUTPUT_PALETTE,
    THEMES,
    DailyPoint,
    DashboardData,
    ForecastPoint,
    build_dashboard_data,
    dither_for_spectra6,
    parse_args,
    render_dashboard,
    theme_icons_dir,
)


def sample_payload() -> dict[str, object]:
    start = datetime(2026, 10, 17, 9)
    hourly_times = [start + timedelta(hours=offset) for offset in range(12)]
    daily_times = [start + timedelta(days=offset) for offset in range(6)]
    return {
        'current': {
            'time': '2026-10-17T09:30',
            'temperature_2m': 13.4,
            'weather_code': 2,
            'is_day': 1,
        },
        'hourly': {
            'time': [value.isoformat(timespec='minutes') for value in hourly_times],
            'temperature_2m': list(range(12, 24)),
            'weather_code': [2] * 12,
            'is_day': [1] * 9 + [0] * 3,
        },
        'daily': {
            'time': [value.date().isoformat() for value in daily_times],
            'temperature_2m_max': list(range(15, 21)),
            'temperature_2m_min': list(range(8, 14)),
            'weather_code': [2] * 6,
        },
    }


class TestDashboardData(unittest.TestCase):
    def test_builds_six_hourly_and_five_future_daily_entries(self) -> None:
        data = build_dashboard_data(sample_payload())

        self.assertEqual(6, len(data.hourly))
        self.assertEqual(5, len(data.daily))
        self.assertEqual(
            [9, 11, 13, 15, 17, 19], [point.time.hour for point in data.hourly]
        )


class TestRendering(unittest.TestCase):
    def test_bundled_themes_each_contain_all_icons(self) -> None:
        expected_names = {
            f'wmo-{code}-{state}.png'
            for code in (
                0,
                1,
                2,
                3,
                45,
                48,
                51,
                53,
                55,
                56,
                57,
                61,
                63,
                65,
                66,
                67,
                71,
                73,
                75,
                77,
                80,
                81,
                82,
                85,
                86,
                95,
                96,
                99,
            )
            for state in ('day', 'night')
        }

        for theme in THEMES:
            with self.subTest(theme=theme):
                names = {path.name for path in (ICONS_ROOT / theme).glob('wmo-*.png')}
                self.assertEqual(expected_names, names)

    def test_theme_selection_and_custom_icon_override(self) -> None:
        args = parse_args(['--theme', 'watercolor'])
        self.assertEqual('watercolor', args.theme)
        self.assertEqual(ICONS_ROOT / 'watercolor', theme_icons_dir(args.theme))

        custom = Path('custom-icons')
        self.assertEqual(custom.resolve(), theme_icons_dir(DEFAULT_THEME, custom))

    def test_dither_uses_only_the_six_spectra_colours(self) -> None:
        image = Image.new('RGB', (32, 16), (120, 140, 180))

        dithered = dither_for_spectra6(image)

        palette = dithered.getpalette()
        expected = [
            component for colour in SPECTRA6_OUTPUT_PALETTE for component in colour
        ]
        self.assertEqual('P', dithered.mode)
        self.assertEqual(expected, palette)
        self.assertLessEqual(len(dithered.getcolors(maxcolors=256) or []), 6)

    def test_dither_keeps_paper_white(self) -> None:
        paper = Image.new('RGB', (32, 16), (249, 247, 240))

        dithered = dither_for_spectra6(paper)

        self.assertEqual([(paper.width * paper.height, 1)], dithered.getcolors())

    def test_dither_keeps_neutral_tones_achromatic(self) -> None:
        grey = Image.new('RGB', (32, 16), (128, 128, 128))

        dithered = dither_for_spectra6(grey)

        used_indices = {index for _, index in dithered.getcolors() or []}
        self.assertTrue(used_indices)
        self.assertLessEqual(used_indices, {0, 1})

    def test_dither_retains_pale_blue_watercolor(self) -> None:
        watercolor = Image.new('RGB', (32, 16), (190, 210, 235))

        dithered = dither_for_spectra6(watercolor)

        colour_counts = {index: count for count, index in dithered.getcolors() or []}
        self.assertGreater(colour_counts.get(4, 0), 0)

    def test_renders_an_800_by_480_png(self) -> None:
        current = ForecastPoint(datetime(2026, 10, 17, 9), 13, 2, True)
        data = DashboardData(
            current=current,
            high=15,
            low=9,
            hourly=[
                ForecastPoint(
                    current.time + timedelta(hours=offset), 13 + offset, 2, True
                )
                for offset in range(0, 12, 2)
            ],
            daily=[
                DailyPoint(current.time + timedelta(days=offset), 15 + offset, 2)
                for offset in range(1, 6)
            ],
        )
        icons_dir = ICONS_ROOT / DEFAULT_THEME

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'dashboard.png'
            render_dashboard(data, icons_dir, output, dither=True)

            with Image.open(output) as image:
                self.assertEqual((800, 480), image.size)
                self.assertEqual('P', image.mode)


if __name__ == '__main__':
    unittest.main()
