###############################################################################
#
# Builds and installs the Python project in the current directory. A wheel is
# built by calling the build backend named in pyproject.toml directly and put
# into the folder "dist". There is no isolated build environment, whatever the
# backend needs has to be installed. The wheel is then installed with the
# "installer" module. Python runs with -P, the current directory may not
# hide an installed module. Understands the following parameters:
#
# --build           Build the wheel.
# --install         Install the wheel, build it first if there is none yet
#                   (the default).
# --root <path>     The installation path.
# --python3, --py3  Accepted for old recipes, Python 3 is always used.
#
###############################################################################
bh_python_install()
{
    local py_interp="$AELTRA_INSTALL_PREFIX/bin/python3"
    local py_action="install"
    local py_root=""
    local py_wheel=""

    while true; do
        case "$1" in
            --python3|--py3)
                shift
                ;;
            --build)
                local py_action="build"
                shift
                ;;
            --install)
                local py_action="install"
                shift
                ;;
            --root)
                local py_root="$2"
                shift 2
                ;;
            --)
                shift
                break
                ;;
            *)
                # unknown argument
                break
                ;;
        esac
    done

    if [ $# -gt 0 ]; then
        echo "bh_python_install: don't know what to do with '$1', there is no setup.py call to pass it to. Aborting." >&2
        exit 17
    fi

    if [ "$py_action" = "install" ]; then
        if [ -z "$py_root" ] || [ ! -d "$py_root" ]; then
            echo "bh_python_install: invalid or empty installation path '$py_root', aborting." >&2
            exit 17
        fi
    fi

    if [ "$py_action" = "build" ] || ! ls dist/*.whl > /dev/null 2>&1; then
        "$py_interp" -P - <<'EOF'
import importlib
import os
import sys
import tomllib

try:
    with open("pyproject.toml", "rb") as f:
        build_system = tomllib.load(f).get("build-system", {})
except FileNotFoundError:
    build_system = {}

name, _, attr = build_system.get(
    "build-backend", "setuptools.build_meta:__legacy__"
).partition(":")

sys.path[:0] = [
    os.path.abspath(path) for path in build_system.get("backend-path", [])
]

backend = importlib.import_module(name)
for part in filter(None, attr.split(".")):
    backend = getattr(backend, part)

os.makedirs("dist", exist_ok=True)
backend.build_wheel("dist")
EOF
    fi

    if [ "$py_action" = "install" ]; then
        for py_wheel in dist/*.whl; do
            DEB_PYTHON_INSTALL_LAYOUT="deb" "$py_interp" -P -m installer \
                --destdir="$py_root" \
                --prefix="$AELTRA_INSTALL_PREFIX" \
                "$py_wheel"
        done
    fi
}
