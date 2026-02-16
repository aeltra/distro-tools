AELTRA_ENVIRONMENT_SH_PRE_FLIGHT_CHECKS_OK=true

if [ ! -f "environment.sh" ]; then
    echo "The environment.sh file must be sourced locally as '. ./environment.sh'."
    AELTRA_ENVIRONMENT_SH_PRE_FLIGHT_CHECKS_OK=false
fi

if [ "$AELTRA_ENVIRONMENT_SH_PRE_FLIGHT_CHECKS_OK" = true ]; then
    mkdir -p .pythonpath/aeltra

    ln -sf ../../ffi-libarchive/lib/aeltra/ffi    .pythonpath/aeltra/
    ln -sf ../../distro-info/lib/aeltra/distro    .pythonpath/aeltra/
    ln -sf ../../misc/lib/aeltra/error.py         .pythonpath/aeltra/
    ln -sf ../../misc/lib/aeltra/miscellaneous    .pythonpath/aeltra/
    ln -sf ../../package/lib/aeltra/package       .pythonpath/aeltra/
    ln -sf ../../repository/lib/aeltra/repository .pythonpath/aeltra/
    ln -sf ../../image-gen/lib/aeltra/osimage     .pythonpath/aeltra/

    touch .pythonpath/aeltra/__init__.py

    if [ "x$AELTRA_LOCAL_PROJECT_SOURCED" = "x" ]; then
        export PYTHONPATH="$(pwd)/.pythonpath:$PYTHONPATH"

        PATH="$(pwd)/image-gen/bin:$PATH"
        PATH="$(pwd)/distro-info/bin:$PATH"
        PATH="$(pwd)/package/bin:$PATH"
        PATH="$(pwd)/repository/bin:$PATH"

        export PATH
        export PS1="(distro-tools)$PS1"
        export AELTRA_LOCAL_PROJECT_SOURCED="yes"
    fi
fi

unset AELTRA_ENVIRONMENT_SH_PRE_FLIGHT_CHECKS_OK
