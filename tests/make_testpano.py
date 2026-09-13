"""Write the marker panoramas the tests read from.

seb_360_testpano.png   2048x1024 equirect: blue sky / brown ground, a 30-degree
                       grid, and a coloured marker at each cardinal longitude:
                         lon 0 RED, +90 GREEN, 180 MAGENTA, -90 BLUE
                       so a test can tell from a view's centre pixel where the
                       camera was really pointing.
seb_360_testpano_b.png the same, inverted -- unmistakably different, for
                       image-swap tests.

Writes into SEB_INPUT_DIR (see _common.py).
"""
import os

import cv2
import numpy as np

from _common import INPUT_DIR, PANO, PANO_B

W, H = 2048, 1024


def build(invert=False):
    img = np.zeros((H, W, 3), np.uint8)
    sky, ground = (200, 150, 90), (60, 85, 110)          # BGR
    for y in range(H):
        t = y / (H - 1)
        if t < 0.5:
            k = t / 0.5
            img[y, :] = tuple(int(c - 30 * k) for c in sky)
        else:
            k = (t - 0.5) / 0.5
            img[y, :] = tuple(int(c + 30 * k) for c in ground)

    for deg in range(-180, 181, 30):
        x = int((deg / 360.0 + 0.5) * W) % W
        cv2.line(img, (x, 0), (x, H), (255, 255, 255), 1)
    for deg in range(-90, 91, 30):
        y = min(max(int((deg / 180.0 + 0.5) * H), 0), H - 1)
        cv2.line(img, (0, y), (W, y), (255, 255, 255), 1)
    cv2.line(img, (0, H // 2), (W, H // 2), (0, 255, 255), 3)

    marks = [(0, "FRONT  lon 0", (0, 0, 255)), (90, "RIGHT  lon +90", (0, 255, 0)),
             (180, "BACK  lon 180", (255, 0, 255)), (-90, "LEFT  lon -90", (255, 128, 0))]
    for deg, label, col in marks:
        x = int((deg / 360.0 + 0.5) * W) % W
        cv2.line(img, (x, 0), (x, H), col, 5)
        cv2.circle(img, (x, H // 2), 26, col, -1)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 3)
        tx = min(max(x - tw // 2, 5), W - tw - 5)
        cv2.putText(img, label, (tx, H // 2 - 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 6)
        cv2.putText(img, label, (tx, H // 2 - 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, col, 3)

    for deg in range(-60, 61, 30):
        y = int((deg / 180.0 + 0.5) * H)
        lab = f"lat {deg:+d}" if deg else "lat 0 (horizon)"
        cv2.putText(img, lab, (W // 2 + 40, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 5)
        cv2.putText(img, lab, (W // 2 + 40, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    for text, y in (("UP / zenith", 70), ("DOWN / nadir", H - 40)):
        cv2.putText(img, text, (W // 2 - 130, y), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 6)
        cv2.putText(img, text, (W // 2 - 130, y), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
    return (255 - img) if invert else img


if __name__ == "__main__":
    os.makedirs(INPUT_DIR, exist_ok=True)
    for name, invert in ((PANO, False), (PANO_B, True)):
        out = os.path.join(INPUT_DIR, name)
        cv2.imwrite(out, build(invert))
        print("wrote", out, os.path.getsize(out) // 1024, "KB")
