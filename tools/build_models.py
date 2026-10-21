"""Rebuild the site's 3D models (the DataLink rover and its controller) and copy them into site/assets/models.

    python tools/build_models.py            full quality, what the site ships
    python tools/build_models.py --fast     fewer occlusion rays: a quicker build for trying out changes

It stops if meshoptimizer is missing, because the model files then come out about twice as large.
Add --without-meshoptimizer to build anyway.

The three steps, each a script in tools/datalink3d that takes this folder (tools/) as its first argument:
  1. make_rover.py     builds the rover at two detail levels and paints the shared texture atlas   -> work/rover.pkl
  2. pack_rover.py     bakes ambient occlusion into the rover and packs it for the page            -> build/rover.js, build/rover-hi.js
  3. build_remote.py   builds the controller from its CAD meshes, bakes and packs it, and writes
                       the finished atlas                                                          -> build/remote.js, build/remote-hi.js,
                                                                                                      build/atlas.webp
"""
import os
import shutil
import subprocess
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(TOOLS, 'datalink3d')
SITE_MODELS = os.path.join(os.path.dirname(TOOLS), 'site', 'assets', 'models')
OUTPUTS = ('rover.js', 'rover-hi.js', 'remote.js', 'remote-hi.js', 'atlas.webp')


def run(script, *args):
    print(f'\n== {script} {" ".join(args)}', flush=True)
    t0 = time.time()
    subprocess.run([sys.executable, os.path.join(CODE, script), TOOLS, *args], check=True)
    print(f'== {script} done in {time.time() - t0:.0f} s', flush=True)


def has_meshoptimizer():
    try:
        import meshoptimizer  # noqa: F401  (used by datalink3d/pack.py)
        return True
    except ImportError:
        return False


def main():
    fast = ['fast'] if '--fast' in sys.argv[1:] else []
    if not has_meshoptimizer() and '--without-meshoptimizer' not in sys.argv[1:]:
        sys.exit('meshoptimizer is not installed, so the model files would come out about twice as large.\n'
                 'Install it (see tools/README.md), or run again with --without-meshoptimizer to build anyway.')
    for d in ('work', 'build'):
        os.makedirs(os.path.join(TOOLS, d), exist_ok=True)
    t0 = time.time()
    run('make_rover.py', '3')        # 3 = tessellation scale of the detailed rover
    run('pack_rover.py', *fast)
    run('build_remote.py', *fast)
    os.makedirs(SITE_MODELS, exist_ok=True)
    for name in OUTPUTS:
        shutil.copyfile(os.path.join(TOOLS, 'build', name), os.path.join(SITE_MODELS, name))
    print(f'\nCopied {", ".join(OUTPUTS)} to site/assets/models ({time.time() - t0:.0f} s in all).')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f'\nBuild stopped: {os.path.basename(e.cmd[1])} failed (exit code {e.returncode}). '
                 'The files in site/assets/models were not changed.')
