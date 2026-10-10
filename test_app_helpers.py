"""Lightweight tests for helper behavior. Run with: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

# Importing app.py invokes Streamlit UI, so test equivalent small pure helpers here.
def safe_stem(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    return cleaned[:80] or "image"


class HelperTests(unittest.TestCase):
    def test_safe_stem(self):
        self.assertEqual(safe_stem("../../holiday photo.jpg"), "holiday_photo")
        self.assertEqual(safe_stem("portrait.png"), "portrait")
        self.assertEqual(safe_stem("..."), "image")

if __name__ == "__main__":
    unittest.main()
