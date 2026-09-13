"""Python extraction: does yaw/pitch point where the panorama says it does?

Reads the marker pano through the API and checks the centre of each view:
yaw +90 must land on the GREEN marker (lon +90), -90 on BLUE, 0 on RED;
pitch +55 must see sky (blue-dominant), -55 ground (red-dominant).
"""
from _common import PANO, centre_stats, finish, forget, require_server, view_rgb

require_server()
forget(PANO)

rep = {}
expect = {"yaw_0": "R", "yaw_+90": "G", "yaw_-90": "B", "pitch_+55": "B", "pitch_-55": "R"}
rep["yaw_0"] = centre_stats(view_rgb(yaw=0))
rep["yaw_+90"] = centre_stats(view_rgb(yaw=90))
rep["yaw_-90"] = centre_stats(view_rgb(yaw=-90))
rep["pitch_+55"] = centre_stats(view_rgb(pitch=55))
rep["pitch_-55"] = centre_stats(view_rgb(pitch=-55))
rep["expected"] = expect
rep["VERDICT"] = {k: rep[k]["dominant"] == v for k, v in expect.items()}
finish(rep, all(rep["VERDICT"].values()))
