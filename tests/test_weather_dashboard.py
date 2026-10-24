import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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
    current_date_label,
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
    def test_formats_current_date_with_ordinal_suffix(self) -> None:
        self.assertEqual(
            'Friday\n24th October',
            current_date_label(datetime(2025, 10, 24)),
        )

        suffixes = {
            1: 'st',
            2: 'nd',
            3: 'rd',
            4: 'th',
            11: 'th',
            12: 'th',
            13: 'th',
            21: 'st',
            22: 'nd',
            23: 'rd',
            31: 'st',
        }
        for day, suffix in suffixes.items():
            with self.subTest(day=day):
                label = current_date_label(datetime(2026, 1, day))
                self.assertIn(f'\n{day}{suffix} January', label)

    def test_builds_six_hourly_and_five_future_daily_entries(self) -> None:
        data = build_dashboard_data(sample_payload())

        self.assertEqual(6, len(data.hourly))
        self.assertEqual(5, len(data.daily))
        self.assertEqual(
            [10, 12, 14, 16, 18, 20], [point.time.hour for point in data.hourly]
        )

    def test_hourly_entries_begin_at_the_closest_hour(self) -> None:
        cases = {
            '2026-10-17T06:55': [7, 9, 11, 13, 15, 17],
            '2026-10-17T07:25': [7, 9, 11, 13, 15, 17],
            '2026-10-17T07:30': [8, 10, 12, 14, 16, 18],
        }

        for current_time, expected_hours in cases.items():
            with self.subTest(current_time=current_time):
                payload = sample_payload()
                start = datetime(2026, 10, 17, 6)
                hourly_times = [start + timedelta(hours=offset) for offset in range(14)]
                payload['current']['time'] = current_time
                payload['hourly']['time'] = [
                    value.isoformat(timespec='minutes') for value in hourly_times
                ]
                payload['hourly']['temperature_2m'] = list(range(14))
                payload['hourly']['weather_code'] = [2] * 14
                payload['hourly']['is_day'] = [1] * 14

                data = build_dashboard_data(payload)

                self.assertEqual(
                    expected_hours, [point.time.hour for point in data.hourly]
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

        colour_counts = {index: count for count, index in dithered.getcolors() or []}
        used_indices = set(colour_counts)
        self.assertTrue(used_indices)
        self.assertLessEqual(used_indices, {0, 1})
        self.assertGreater(colour_counts.get(1, 0), colour_counts.get(0, 0))

    def test_dither_boosts_muted_colour_before_palette_reduction(self) -> None:
        muted_blue = Image.new('RGB', (32, 16), (120, 140, 180))

        dithered = dither_for_spectra6(muted_blue)

        used_indices = {index for _, index in dithered.getcolors() or []}
        self.assertIn(4, used_indices)
        self.assertLessEqual(used_indices, {0, 1, 4})

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

    def test_full_colour_render_skips_inky_compensation(self) -> None:
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

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'dashboard.png'
            with patch('weather_dashboard.dither_for_spectra6') as compensate:
                render_dashboard(
                    data,
                    ICONS_ROOT / DEFAULT_THEME,
                    output,
                    dither=False,
                )

            compensate.assert_not_called()
            with Image.open(output) as image:
                self.assertEqual('RGB', image.mode)


if __name__ == '__main__':
    unittest.main()
