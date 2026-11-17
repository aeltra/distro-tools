###############################################################################
#
# Converts a machine name (armv6, x86_64) or a target triplet
# (armv6-linux-gnueabihf, x86_64-pc-linux-gnu) to the corresponding kernel
# ARCH.
#
# $1: a machine name or target triplet
#
# Prints the corresponding kernel ARCH name.
#
###############################################################################
bh_kernel_arch_for_target()
{
    local uname="`echo $1 | cut -d'-' -f1`"

    echo $(
        # The following is in large parts stolen from a kernel makefile
        echo "$uname" | sed -e 's/i.86/x86/'        -e 's/x86_64/x86/'     \
                            -e 's/sun4u/sparc64/'   -e 's/arm.*/arm/'      \
                            -e 's/sa110/arm/'       -e 's/s390x/s390/'     \
                            -e 's/parisc64/parisc/' -e 's/ppc.*/powerpc/'  \
                            -e 's/mips.*/mips/'     -e 's/sh[234].*/sh/'   \
                            -e 's/aarch64.*/arm64/' -e 's/powerpc64.*/powerpc/' \
                            -e 's/riscv.*/riscv/'   -e 's/loongarch.*/loongarch/'
    )
}

###############################################################################
#
# Converts a machine name (armv6, x86_64) or a target triplet
# (armv6-linux-gnueabihf, x86_64-pc-linux-gnu) to the corresponding musl
# architecture.
#
# $1: a machine name or target triplet
#
# Prints the corresponding musl architecture name.
#
###############################################################################
bh_musl_arch_for_target()
{
    case "$1" in
        arm*)
            echo "arm"
            ;;
        aarch64*)
            echo "aarch64"
            ;;
        i?86-nt32*)
            echo "nt32"
            ;;
        i?86*)
            echo "i386"
            ;;
        loongarch64*)
            echo "loongarch64"
            ;;
        x86_64-x32*|x32*|x86_64*x32)
            echo "x32"
            ;;
        x86_64-nt64*)
            echo "nt64"
            ;;
        x86_64*)
            echo "x86_64"
            ;;
        mips64*|mipsisa64*)
            echo "mips64"
            ;;
        mips*)
            echo "mips"
            ;;
        microblaze*)
            echo "microblaze"
            ;;
        or1k*)
            echo "or1k"
            ;;
        powerpc64*|ppc64*)
            echo "powerpc64"
            ;;
        powerpc*)
            echo "powerpc"
            ;;
        riscv64*)
            echo "riscv64"
            ;;
        sh[1-9bel-]*|sh|superh*)
            echo "sh"
            ;;
        s390x*)
            echo "s390x"
            ;;
    esac
}

###############################################################################
#
# Takes a target triplet (powerpc64le-linux-musl, x86_64-tools-linux-gnu) and
# spits out the default settings with which to configure GCC. Some of them
# depend on the libc, which is taken from the triplet.
#
# $1: a target triplet
#
# Prints the corresponding GCC configure options. Prints an error message to
# stderr and returns 1 if the argument is not a target triplet.
#
###############################################################################
bh_gcc_config_for_machine()
{
    local _libc=""

    case "$1" in
        *-*-gnu*)
            _libc="glibc"
            ;;
        *-*-musl*)
            _libc="musl"
            ;;
        *)
            echo "bh_gcc_config_for_machine: not a target triplet: '$1'" >&2
            return 1
            ;;
    esac

    case "$1" in
        aarch64*)
            echo "--enable-default-pie --enable-fix-cortex-a53-843419"
            ;;
        loongarch64*)
            echo "--enable-default-pie"
            ;;
        powerpc64el*|powerpc64le*|ppc64el*)
            case "$_libc" in
                glibc)
                    echo "--enable-default-pie --enable-secureplt --with-abi=elfv2 --with-long-double-128 --with-long-double-format=ieee"
                    ;;
                *)
                    echo "--enable-default-pie --enable-secureplt --with-abi=elfv2 --without-long-double-128 --enable-decimal-float=no"
                    ;;
            esac
            ;;
        riscv64*)
            echo "--enable-default-pie --with-arch=rv64imafdc_zicsr_zicntr_ziccif_ziccrse_ziccamoa_zifencei --with-abi=lp64d"
            ;;
        s390x*)
            echo "--enable-default-pie --with-arch=z196 --with-long-double-128 --disable-s390-excess-float-precision"
            ;;
        x86_64*)
            echo "--enable-default-pie --enable-cet --with-tune=generic"
            ;;
    esac
}

###############################################################################
#
# Takes a <machine>-<vendor>-<os> target triplet and inserts 'xxx' for the 
# vendor part. This is commonly used to trigger a cross compilation.
#
# $1: a target triplet
#
# Prints the modified target triplet.
#
###############################################################################
bh_spoof_target_triplet()
{
    echo "$1" | \
        sed 's/\([^-]\+\)-\([^-]\+-\)\?\([^-]\+\)-\([^-]\+\)/\1-xxx-\3-\4/g'
}

###############################################################################
#
# Replace all occurences of config.sub and config.guess in the current source
# tree with the versions stored in /usr/share/misc.
#
# Prints nothing.
#
###############################################################################
bh_autotools_dev_update()
{
    find . -name "config.guess" | while read filename
    do
        if [ -f "/tools/share/misc/config.guess" ]
        then
            cp "/tools/share/misc/config.guess" "$filename"
        else
            cp "/usr/share/misc/config.guess" "$filename"
        fi
    done
    find . -name "config.sub" | while read filename
    do
        if [ -f "/tools/share/misc/config.sub" ]
        then
            cp "/tools/share/misc/config.sub" "$filename"
        else
            cp "/usr/share/misc/config.sub" "$filename"
        fi
    done
}

###############################################################################
#
# Takes a machine name (armv6, x86_64) or a target triplet
# (armv6-linux-gnueabihf, x86_64-pc-linux-gnu) and tells the native word size
# of that platform (i.e. "32" or "64").
#
# $1: a machine name or target triplet
#
# Prints the corresponding word size in bits.
#
###############################################################################
bh_os_bits()
{
    case "$1" in
        *64*|s390x*)
            echo "64"
            ;;
        *)
            echo "32"
            ;;
    esac
}

###############################################################################
#
# Copies the contents of the lib64 directory to the standard lib directory.
#
# $1: the base directory (think $1/$prefix/lib64).
#
# Prints nothing.
#
###############################################################################
bh_unify_lib64_with_lib()
{
    local __base="$1"

    if [ -d "$__base/$AELTRA_INSTALL_PREFIX/lib64" ]; then
        mkdir -p "$__base/$AELTRA_INSTALL_PREFIX/lib"
        mv "$__base/$AELTRA_INSTALL_PREFIX/lib64/"* \
            "$__base/$AELTRA_INSTALL_PREFIX/lib/"
        rmdir "$__base/$AELTRA_INSTALL_PREFIX/lib64"
        ln -sf lib "$__base/$AELTRA_INSTALL_PREFIX/lib64"
    fi
}

