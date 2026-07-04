"""Tests unitaires des fonctions utilitaires."""

import tempfile
import unittest
from pathlib import Path

from fencing_videos_downloader.utils import (
    format_timestamp,
    parse_timestamp,
    sanitize_filename,
    unique_path,
)


class ParseTimestampTests(unittest.TestCase):
    def test_secondes_seules(self):
        self.assertEqual(parse_timestamp("45"), 45)

    def test_minutes_secondes(self):
        self.assertEqual(parse_timestamp("2:35"), 155)

    def test_heures_minutes_secondes(self):
        self.assertEqual(parse_timestamp("1:02:03"), 3723)

    def test_espaces_toleres(self):
        self.assertEqual(parse_timestamp(" 14:50 "), 890)

    def test_rejette_vide(self):
        with self.assertRaises(ValueError):
            parse_timestamp("")

    def test_rejette_lettres(self):
        with self.assertRaises(ValueError):
            parse_timestamp("abc")

    def test_rejette_secondes_hors_limite(self):
        with self.assertRaises(ValueError):
            parse_timestamp("1:75")

    def test_rejette_trop_de_segments(self):
        with self.assertRaises(ValueError):
            parse_timestamp("1:2:3:4")


class FormatTimestampTests(unittest.TestCase):
    def test_secondes(self):
        self.assertEqual(format_timestamp(45), "45s")

    def test_minutes(self):
        self.assertEqual(format_timestamp(155), "2m35s")

    def test_heures(self):
        self.assertEqual(format_timestamp(3723), "1h02m03s")


class SanitizeFilenameTests(unittest.TestCase):
    def test_caracteres_interdits(self):
        self.assertEqual(sanitize_filename('a<b>:"c/d'), "a_b___c_d")

    def test_accents_conserves(self):
        self.assertEqual(sanitize_filename("rapproché"), "rapproché")

    def test_points_et_espaces_en_bordure(self):
        self.assertEqual(sanitize_filename("  clip.  "), "clip")

    def test_longueur_limitee(self):
        self.assertEqual(len(sanitize_filename("x" * 300)), 150)


class IsStreamUrlTests(unittest.TestCase):
    def test_detecte_m3u8(self):
        from fencing_videos_downloader.downloader import is_stream_url

        self.assertTrue(is_stream_url("https://cdn.fencingtv.com/live/match.M3U8?token=abc"))

    def test_youtube_non_detecte(self):
        from fencing_videos_downloader.downloader import is_stream_url

        self.assertFalse(is_stream_url("https://www.youtube.com/watch?v=abc123"))


class UniquePathTests(unittest.TestCase):
    def test_evite_les_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            first = unique_path(directory, "clip")
            self.assertEqual(first.name, "clip.mp4")
            first.touch()
            second = unique_path(directory, "clip")
            self.assertEqual(second.name, "clip (2).mp4")


if __name__ == "__main__":
    unittest.main()
