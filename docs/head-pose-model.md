# The head-pose model

Camera-based head rotation needs a neural network. **openstargazer ships
one.** Since v0.4.0 the project carries its own weights under GPL-3.0 and
loads them by default; no download and no separate fetch is needed.

Without the model the tracker still delivers gaze, head position and roll;
what it adds is **yaw and pitch**, the two axes the device's data stream
does not carry.

## The shipped weights

The file is `openstargazer/models/head-pose.onnx`. The training code is
ISC-licensed, and the training data is `replicantface` — 100 000 rendered
faces with pose annotations, MIT-licensed, from the same author. The
network was trained from scratch: no pretrained checkpoint, no Basel Face
Model, no non-commercial training data. The resulting weights carry no
non-commercial clause at all and are distributed here under the project's
own GPL-3.0.

Nothing has to be configured to use them. Without a `model_path` the
lookup takes `~/.local/share/openstargazer/models/head-pose.onnx` if it is
there and the shipped file otherwise — the user directory is an override,
not the normal location. The same applies to an optional
`head-localizer.onnx`: it is used from either directory, because inside an
installed package there is nowhere for a user to put one.

`onnxruntime` is needed to run it and is an optional dependency:

```bash
pip install onnxruntime      # or: pip install .[camera]
```

Without it the camera source still starts and still tracks; it logs
plainly that yaw and pitch are unavailable and why. It does not fail
silently, and it does not pretend to a rotation it does not have.

## The geometric localizer

A pose network needs a cropped face patch, not a whole frame. Previous
versions used a second ONNX network — `head-localizer.onnx`, trained on
WIDER FACE (**CC BY-NC-ND**) — to find the head first. That file could not
be shipped, and it is no longer needed.

The gaze stream reports both eye origins (`eye_origin_mm`) 33 times a
second. Projecting them into the camera frame gives the patch centre, and
the interpupillary distance gives its size. For the ET5 this is enough:
one user, one fixed camera, one fixed distance.

**Camera geometry.** The measured diagonal field of view is **55.7°**.
The tracker's coordinate system has *x* right, *y* down, *z* toward the
user. The camera looks toward the user, so the transformation to camera
space is:

```
cam_x = -z
cam_y =  y
cam_z = -x
```

A standard pinhole projection maps the eye midpoint to pixel coordinates.
The patch width is the interpupillary distance multiplied by **2.5** (a
human face is roughly 2.5× as wide as the eye distance), then by
`PATCH_MARGIN` (1.05) for a small border. Everything the localizer needs
comes from the device itself — no neural network, no third-party data.

When eye positions are unavailable — the tracker loses the eyes on about
60 % of frames during a wide turn — the source falls back to the ONNX
localizer if one is present in the model directory, or reports no pose for
that frame. It never guesses.

## Why the project carries its own weights

The obvious thing would have been to ship the opentrack models or fetch
them silently on first run. Neither is done, and the reason is not file
size.

A model file is two things: an architecture, and a set of **weights** —
the numbers that came out of training it on a pile of photographs. The
architecture and the training code of the model this project was tested
against are ISC-licensed and unproblematic. The opentrack weights are a
different question, because they are the product of the photographs.

For the opentrack head-pose models, that question has an uncomfortable
answer. The training repository
([opentrack/neuralnet-tracker-traincode](https://github.com/opentrack/neuralnet-tracker-traincode))
separates its software licence from its data licences, and the data side
reads:

| Training data | Terms |
|---|---|
| Extended WFLW and LaPa | **CC BY-NC 4.0** — *"You may not use the material for commercial purposes"* |
| Microsoft Face Synthetics | **Research Use of Data Agreement** — research only |
| 300W-LP / AFLW2000-3D | *"Cannot find licensing information"* |
| Basel Face Model (via the augmentation) | *"only for academic use"* |

Whether trained weights are a derived work of their training data is not
settled law and differs by jurisdiction. The shipped weights sidestep the
question entirely: `replicantface` is MIT, and MIT has no
non-commercial restriction. Nothing here depends on a clause anyone might
argue about.

If you are using openstargazer privately and for free, none of this is
likely to concern you. If you intend to sell something built on it, note
that **changing openstargazer's own licence does not help with the
opentrack weights.** A non-commercial clause on the training data binds
regardless of what licence the surrounding program carries. The shipped
weights have no such clause.

## Which model, and how well it works

Measured on 807 recorded frames from the ET5's own infrared camera,
against a prescribed angle rather than a reconstructed one:

| | |
|---|---|
| correlation with the prescribed turn | **r = 0.992** |
| residual scatter | **2.24°** |
| head found | **98 %** |
| cost per picture | **5.8 ms** — 19 % of one core at 33 Hz |

The shipped weights, measured against the same prescribed runs on the
ET5's own camera:

| | own weights | `0.4-big` (opentrack) |
|---|---|---|
| yaw, correlation / residual | r = 0.989 / 2.68° | r = 0.992 / 2.25° |
| nod, best run | **r = 0.947 / 2.24°** | r = 0.955 / 2.76° |
| roll against the device's eye baseline | **r = 0.966 / 0.48°** | r = 0.922 / 0.70° |

Slightly behind on yaw, ahead on roll, comparable on the nod — from a
network that has never seen an infrared picture and was trained purely on
synthetic daylight renders.

**Pitch is verified too.** The yaw figures above come from a horizontal
sweep, which prescribes no pitch at all. Three further recordings
prescribed the nod instead, and both networks read it:

| nod run | `0.4-big` r / residual | own weights r / residual |
|---|---|---|
| 965 mm | 0.915 / 4.06° | 0.890 / 3.71° |
| 835 mm | 0.866 / 3.57° | 0.846 / 2.92° |
| **739 mm** | **0.955 / 2.76°** | **0.947 / 2.24°** |

Yaw read from the same runs stays at r ≈ 0.05–0.3, so neither network
mistakes a nod for a turn. The reachable range is one-sided — nose up
only, because the tracker sits below the screen.

**Sit closer.** That table is sorted by distance for a reason: brightness
follows distance, not room light. At the 99th percentile a frame from
751 mm reaches 49 of 255, from 835 mm 33, and from 965 mm *with the room
lit* 30. The sensor is infrared and sees mostly the return of its own
illuminators, so a lamp barely helps and half a metre does. On the darkest
run the localizer found a head in 11 % of frames until the picture was
scaled up before it, the way the pose patch already was.

**The slope is not a model figure.** Across the three runs it moved by a
factor of 1.8 — for both networks together, and what shifts for both is a
property of neither. The cue says where the nose should point, not how far
the head must turn to get there: someone who overshoots produces a slope
above 1, someone who helps with their eyes one below.

Their *ratio*, however, held at **1.32 ± 2.9 %** across all three. Against
the same head movement the opentrack model reads about a third more nod
than the own weights do — a real, systematic difference in scale, and one
a constant would correct.

## It does not cost you the gaze

The reasonable worry about switching this on is that the tracker has one
USB endpoint and the camera pictures are large. Measured over three
30-second passes — the plain driver, then the camera source, then the
plain driver again:

| | gaze rate | largest gap | samples distinct |
|---|---|---|---|
| without the camera | 33.1 fps | 36 ms | 100 % |
| **with it** | **33.1 fps** | **49 ms** | **100 %** |
| without it, again | 33.1 fps | 37 ms | 100 % |

Nothing is given up. Meanwhile 33.1 pictures a second went through the
network at 7.8 ms each.

Two controls around the test rather than one before it, because a single
pair cannot separate the camera's cost from a device that simply got
slower. And what is counted is *distinct* device timestamps, not validity
flags: a stream that froze behind healthy flags is exactly the failure
this measurement exists to catch.

One thing that fell out of it: on the same run the camera had a rotation
on **99 %** of frames while the device's own eye positions were valid on
**40 %**. Turn your head far enough and the tracker loses your eyes; the
picture still has a head in it.

## Using a different model (for developers)

`model_path` accepts any ONNX file with the same interface: a single
`1×1×129×129` float input named `x`, and outputs named `quat` (as x, y, z,
w) and `pos_size`.

This is an escape hatch for developers who want to experiment with
third-party weights, such as the opentrack models. It is **not the
standard path** and not something end users need to touch. Functionality
with third-party models may be limited: the geometric localizer was
designed for the shipped weights and their training crop, and a model
trained against a different crop may be less accurate without a matching
localizer. When eye positions are available the geometric localizer is
used regardless of which pose model is loaded; when they are not, an ONNX
localizer file (`head-localizer.onnx`) placed next to the pose model
serves as fallback.

```toml
[input]
source = "et5_ttp_camera"

[input.et5_camera]
model_path = "/path/to/head-pose-0.4-big-int8.onnx"
```

The licence caveats above apply: if you point `model_path` at the opentrack
weights, you are responsible for the training-data terms those weights
carry.