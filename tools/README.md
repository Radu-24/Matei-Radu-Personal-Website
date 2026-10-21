# Tools: the 3D model build

The rover and the controller on the site are generated here in Python. The inputs are meshes exported from my CAD files and the datasheet sizes of the parts. One command rebuilds both models:

```
python tools/build_models.py
```

On a two-core machine it takes about two minutes. It writes five files into `site/assets/models/`:

| File | Contents | Size |
|---|---|---|
| `rover.js` | the rover, light version (the page loads it first) | 0.3 MB |
| `rover-hi.js` | the rover, detailed version | 0.9 MB |
| `remote.js` | the controller, light version | 0.9 MB |
| `remote-hi.js` | the controller, detailed version (about 1.4 million triangles) | 4.1 MB |
| `atlas.webp` | the texture both models share: board tops, chip markings and labels | 0.3 MB |

The `.js` files hold data, not code. For each mesh they store delta-coded positions, colours with baked ambient occlusion, texture coordinates and indices. That data is gzipped, base64-encoded and assigned to one global variable, which `site/assets/js/datalink-3d.js` unpacks in the browser. The page swaps in the detailed versions only on devices that can draw them smoothly.

On the same machine, running the build again gives byte-identical files, so git only shows a change when a model has really changed. A different computer or package version can produce slightly different numbers.

## Setup (once)

The build needs Python 3.12 or newer, and I tested it with Python 3.13 on Linux. Run these commands from the repository folder.

**Linux or macOS:**

```
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/requirements.txt
.venv/bin/python -m pip install --pre meshoptimizer==0.2.30a0
```

On Debian, Ubuntu or Parrot, first install the venv module and a compiler: `sudo apt install python3-venv python3-dev build-essential`.

**Windows** (PowerShell or Command Prompt):

```
python -m venv .venv
.venv\Scripts\python -m pip install -r tools\requirements.txt
.venv\Scripts\python -m pip install --pre meshoptimizer==0.2.30a0
```

All packages in `requirements.txt` install from ready-made wheels on 64-bit Linux and Windows and on Apple-silicon Macs.

`meshoptimizer` is different. It is a pre-release that pip compiles from source, so it needs a C++ compiler. On Linux, that is `g++` (in `build-essential`). On Windows, it is Microsoft's Build Tools for Visual Studio with the "Desktop development with C++" workload. I have only run the build on Linux; on Windows, WSL is the closest match. Without `meshoptimizer` the model files come out about twice as large, so `build_models.py` stops unless you add `--without-meshoptimizer`.

## Build

```
.venv/bin/python tools/build_models.py          (Linux, macOS)
.venv\Scripts\python tools\build_models.py      (Windows)
```

Then reload the page. When you are trying out changes, add `--fast` for a quicker build with fewer occlusion rays. Run a full build before you commit.

## What is in this folder

```
build_models.py          runs the three build steps and copies the results into site/assets/models
requirements.txt         packages for the build
requirements-cad.txt     extra packages for re-exporting the CAD meshes
datalink3d/
  make_rover.py          step 1: builds the rover at two detail levels and paints the texture atlas
  pack_rover.py          step 2: bakes ambient occlusion into the rover and packs it
  build_remote.py        step 3: builds the controller, bakes and packs it, and writes the finished atlas
  rover.py               the rover, part by part: T101 frame and tracks, motors, the printed plate and battery box,
                         Pi 5, Arduino Nano, sensors, cameras, servo mast, fibre converter, cells, wiring
  rparts.py              boards and parts built to datasheet sizes: XL4015, INA219, ADS1015, 2S BMS, USB-C board,
                         MTS-102 switch, 30 mm fan
  geom.py                mesh toolkit: primitives, sweeps, booleans (manifold3d), detail control
  atlas.py               paints the texture atlas: PCB tops, chip markings, labels, the plate's print lines
  bake.py                ambient occlusion with Embree ray casting
  pack.py                the packed format the page reads
  export_remote_cad.py   controller STEP file -> remote_cad.npz, remote_cad_names.json and designed.step
  stepdb.py              minimal STEP file reader used by export_remote_cad.py
  remesh.py              meshes every solid in a STEP file
cad/                     the CAD meshes the build starts from
fonts/                   DejaVu Sans for the painted labels (licence in fonts/LICENSE)
work/, build/            created by the build; ignored by git
```

## Where the geometry comes from

- **From my CAD:** the rover's printed plate and battery box, the overview camera's bracket, and the controller's shell, covers, supports, screen, joysticks and battery holders.
- **Built to datasheet sizes:** the boards and parts, from the Raspberry Pi 5 boards and the Arduino Nano to the sensors, cameras, converters, switch, fan and 21700 cells.
- **From the seller's product photos:** the T101 tank chassis (frame, tracks, sprockets, idlers and motors).
- The wiring is illustrative. A few boards inside the rover sit where the build photos suggest, not where a drawing puts them.

## Re-exporting the CAD meshes

You only need this when the CAD changes. The STEP files are not in the repository: `.gitignore` keeps `*.step` files on your computer.

```
pip install -r tools/requirements-cad.txt

# rover: plate (solid 0) and battery box (solid 1), at a fine and a coarse tolerance
python tools/datalink3d/remesh.py "rover.step" tools/cad/rover_cad_hi.npz <linear mm> <angle rad>
python tools/datalink3d/remesh.py "rover.step" tools/cad/rover_cad_lo.npz <linear mm> <angle rad>

# controller: every solid with its name, plus designed.step (the printed parts only), then those re-meshed finer
python tools/datalink3d/export_remote_cad.py "controller.step" tools/cad
python tools/datalink3d/remesh.py tools/cad/designed.step tools/cad/remote_designed_hi.npz <linear mm> <angle rad>
python tools/datalink3d/remesh.py tools/cad/designed.step tools/cad/remote_designed_lo.npz <linear mm> <angle rad>
```

Smaller tolerances give finer meshes and bigger files. The `remesh.py` tolerances used for the current meshes were not recorded, so pick new ones by eye. `export_remote_cad.py` meshes the designed parts at fixed values (0.12 mm, 0.2 rad).
