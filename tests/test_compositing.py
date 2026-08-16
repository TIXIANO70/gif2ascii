"""
tests/test_compositing.py - Unit tests for GIF frame extraction, disposal methods, and anti-ghosting.
"""

import os
import sys
import unittest
from PIL import Image

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gif2ascii import extract_composited_frames

class TestCompositing(unittest.TestCase):

    def test_disposal_method_2_anti_ghosting(self):
        """Test that frames with disposal method 2 clear previous frames without leaving ghost trails."""
        # Create a synthetic 2-frame GIF with moving box and disposal=2
        im1 = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
        # Draw 5x5 red square at (0, 0)
        for x in range(5):
            for y in range(5):
                im1.putpixel((x, y), (255, 0, 0, 255))

        im2 = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
        # Draw 5x5 blue square at (10, 10)
        for x in range(10, 15):
            for y in range(10, 15):
                im2.putpixel((x, y), (0, 0, 255, 255))

        # Save as animated GIF in memory/temp with disposal=2
        import io
        buf = io.BytesIO()
        im1.convert("P", palette=Image.Palette.ADAPTIVE).save(
            buf,
            format="GIF",
            save_all=True,
            append_images=[im2.convert("P", palette=Image.Palette.ADAPTIVE)],
            duration=100,
            disposal=2,
            transparency=0,
            loop=0
        )
        buf.seek(0)

        gif = Image.open(buf)
        frames = extract_composited_frames(gif)

        self.assertEqual(len(frames), 2)
        frame0_img, _ = frames[0]
        frame1_img, _ = frames[1]

        # Frame 0 should have the red square at (0, 0)
        self.assertEqual(frame0_img.getpixel((2, 2))[3], 255)
        self.assertEqual(frame0_img.getpixel((12, 12))[3], 0)

        # Frame 1 should NOT have red square at (0, 0) (no ghosting!)
        self.assertEqual(frame1_img.getpixel((2, 2))[3], 0)
        # Frame 1 should have blue square at (12, 12)
        self.assertEqual(frame1_img.getpixel((12, 12))[3], 255)

if __name__ == "__main__":
    unittest.main()
