# All Global changes to build and install go here.
# Per the below section about __spec_install_pre, any rpm
# environment changes that affect %%install need to go
# here before the %%install macro is pre-built.

# Disable frame pointers
%undefine _include_frame_pointers

# Disable LTO in userspace packages.
%global _lto_cflags %{nil}

# Option to enable compiling with clang instead of gcc.
%bcond_with toolchain_clang

%if %{with toolchain_clang}
%global toolchain clang
%endif

# Compile the kernel with LTO (only supported when building with clang).
%bcond_with clang_lto

%if %{with clang_lto} && %{without toolchain_clang}
{error:clang_lto requires --with toolchain_clang}
%endif

# RPM macros strip everything in BUILDROOT, either with __strip
# or find-debuginfo.sh. Make use of __spec_install_post override
# and save/restore binaries we want to package as unstripped.
%define buildroot_unstripped %{_builddir}/root_unstripped
%define buildroot_save_unstripped() \
(cd %{buildroot}; cp -rav --parents -t %{buildroot_unstripped}/ %1 || true) \
%{nil}
%define __restore_unstripped_root_post \
    echo "Restoring unstripped artefacts %{buildroot_unstripped} -> %{buildroot}" \
    cp -rav %{buildroot_unstripped}/. %{buildroot}/ \
%{nil}

# The kernel's %%install section is special
# Normally the %%install section starts by cleaning up the BUILD_ROOT
# like so:
#
# %%__spec_install_pre %%{___build_pre}\
#     [ "$RPM_BUILD_ROOT" != "/" ] && rm -rf "${RPM_BUILD_ROOT}"\
#     mkdir -p `dirname "$RPM_BUILD_ROOT"`\
#     mkdir "$RPM_BUILD_ROOT"\
# %%{nil}
#
# But because of kernel variants, the %%build section, specifically
# BuildKernel(), moves each variant to its final destination as the
# variant is built.  This violates the expectation of the %%install
# section.  As a result we snapshot the current env variables and
# purposely leave out the removal section.  All global wide changes
# should be added above this line otherwise the %%install section
# will not see them.
%global __spec_install_pre %{___build_pre}

# Replace '-' with '_' where needed so that variants can use '-' in
# their name.
%define uname_suffix() %{lua:
	local flavour = rpm.expand('%{?1:+%{1}}')
	flavour = flavour:gsub('-', '_')
	if flavour ~= '' then
		print(flavour)
	end
}

# This returns the main kernel tied to a debug variant. For example,
# kernel-debug is the debug version of kernel, so we return an empty
# string. However, kernel-64k-debug is the debug version of kernel-64k,
# in this case we need to return "64k", and so on. This is used in
# macros below where we need this for some uname based requires.
%define uname_variant() %{lua:
	local flavour = rpm.expand('%{?1:%{1}}')
	_, _, main, sub = flavour:find("(%w+)-(.*)")
	if main then
		print("+" .. main)
	end
}


# At the time of this writing (2019-03), RHEL8 packages use w2.xzdio
# compression for rpms (xz, level 2).
# Kernel has several large (hundreds of mbytes) rpms, they take ~5 mins
# to compress by single-threaded xz. Switch to threaded compression,
# and from level 2 to 3 to keep compressed sizes close to "w2" results.
#
# NB: if default compression in /usr/lib/rpm/redhat/macros ever changes,
# this one might need tweaking (e.g. if default changes to w3.xzdio,
# change below to w4T.xzdio):
#
# This is disabled on i686 as it triggers oom errors

%ifnarch i686
%define _binary_payload w3T.xzdio
%endif

Summary: The Linux kernel
%if 0%{?fedora}
%define secure_boot_arch x86_64
%else
%define secure_boot_arch x86_64 aarch64 s390x ppc64le
%endif

# Signing for secure boot authentication
%ifarch %{secure_boot_arch}
%global signkernel 1
%else
%global signkernel 0
%endif

# Sign modules on all arches
%global signmodules 1

# Compress modules only for architectures that build modules
%ifarch noarch
%global zipmodules 0
%else
%global zipmodules 1
%endif

# Default compression algorithm
%global compression xz
%global compression_flags --compress --check=crc32 --lzma2=dict=1MiB
%global compext xz

%if 0%{?fedora}
%define primary_target fedora
%else
%define primary_target rhel
%endif

#
# genspec.sh variables
#

# kernel package name
%global package_name kernel
%global gemini 0
# Include Fedora files
%global include_fedora 1
# Include RHEL files
%global include_rhel 1
# Include RT files
%global include_rt 1
# Include Automotive files
%global include_automotive 1
# Provide Patchlist.changelog file
%global patchlist_changelog 1
# Set released_kernel to 1 when the upstream source tarball contains a
#  kernel release. (This includes prepatch or "rc" releases.)
# Set released_kernel to 0 when the upstream source tarball contains an
#  unreleased kernel development snapshot.
%global released_kernel 1
# Set debugbuildsenabled to 1 to build separate base and debug kernels
#  (on supported architectures). The kernel-debug-* subpackages will
#  contain the debug kernel.
# Set debugbuildsenabled to 0 to not build a separate debug kernel, but
#  to build the base kernel using the debug configuration. (Specifying
#  the --with-release option overrides this setting.)
%define debugbuildsenabled 1
%define buildid .spacemit
%define specrpmversion 6.15.7
%define specversion 6.15.7
%define patchversion 6.15
%define pkgrelease 200
%define kversion 6
%define tarfile_release 6.15.7
# This is needed to do merge window version magic
%define patchlevel 15
# This allows pkg_release to have configurable %%{?dist} tag
%define specrelease 200%{?buildid}%{?dist}
# This defines the kabi tarball version
%define kabiversion 6.15.7

# If this variable is set to 1, a bpf selftests build failure will cause a
# fatal kernel package build error
%define selftests_must_build 0

#
# End of genspec.sh variables
#

%define pkg_release %{specrelease}

# libexec dir is not used by the linker, so the shared object there
# should not be exported to RPM provides
%global __provides_exclude_from ^%{_libexecdir}/kselftests

# The following build options are (mostly) enabled by default, but may become
# enabled/disabled by later architecture-specific checks.
# Where disabled by default, they can be enabled by using --with <opt> in the
# rpmbuild command, or by forcing these values to 1.
# Where enabled by default, they can be disabled by using --without <opt> in
# the rpmbuild command, or by forcing these values to 0.
#
# standard kernel
%define with_up        %{?_without_up:        0} %{?!_without_up:        1}
# build the base variants
%define with_base      %{?_without_base:      0} %{?!_without_base:      1}
# build also debug variants
%define with_debug     %{?_without_debug:     0} %{?!_without_debug:     1}
# kernel-zfcpdump (s390 specific kernel for zfcpdump)
%define with_zfcpdump  %{?_without_zfcpdump:  0} %{?!_without_zfcpdump:  1}
# kernel-16k (aarch64 kernel with 16K page_size)
%define with_arm64_16k %{?_with_arm64_16k:    1} %{?!_with_arm64_16k:    0}
# kernel-64k (aarch64 kernel with 64K page_size)
%define with_arm64_64k %{?_without_arm64_64k: 0} %{?!_without_arm64_64k: 1}
# kernel-rt (x86_64 and aarch64 only PREEMPT_RT enabled kernel)
%define with_realtime  %{?_without_realtime:  0} %{?!_without_realtime:  1}
# kernel-rt-64k (aarch64 RT kernel with 64K page_size)
%define with_realtime_arm64_64k %{?_without_realtime_arm64_64k: 0} %{?!_without_realtime_arm64_64k: 1}
# kernel-automotive (x86_64 and aarch64 with PREEMPT_RT enabled - currently off by default)
%define with_automotive %{?_with_automotive:  1} %{?!_with_automotive:   0}

# Supported variants
#            with_base with_debug    with_gcov
# up         X         X             X
# zfcpdump   X                       X
# arm64_16k  X         X             X
# arm64_64k  X         X             X
# realtime   X         X             X
# automotive X         X             X

# kernel-doc
%define with_doc       %{?_without_doc:       0} %{?!_without_doc:       1}
# kernel-headers
%define with_headers   %{?_without_headers:   0} %{?!_without_headers:   1}
%define with_cross_headers   %{?_without_cross_headers:   0} %{?!_without_cross_headers:   1}
# perf
%define with_perf      %{?_without_perf:      0} %{?!_without_perf:      1}
# libperf
%define with_libperf   %{?_without_libperf:   0} %{?!_without_libperf:   1}
# tools
%define with_tools     %{?_without_tools:     0} %{?!_without_tools:     1}
# ynl
%define with_ynl      %{?_without_ynl:      0} %{?!_without_ynl:      1}
# kernel-debuginfo
%define with_debuginfo %{?_without_debuginfo: 0} %{?!_without_debuginfo: 1}
# kernel-abi-stablelists
%define with_kernel_abi_stablelists %{?_without_kernel_abi_stablelists: 0} %{?!_without_kernel_abi_stablelists: 1}
# internal samples and selftests
%define with_selftests %{?_without_selftests: 0} %{?!_without_selftests: 1}
#
# Additional options for user-friendly one-off kernel building:
#
# Only build the base kernel (--with baseonly):
%define with_baseonly  %{?_with_baseonly:     1} %{?!_with_baseonly:     0}
# Only build the debug variants (--with dbgonly):
%define with_dbgonly   %{?_with_dbgonly:      1} %{?!_with_dbgonly:      0}
# Only build the realtime kernel (--with rtonly):
%define with_rtonly    %{?_with_rtonly:       1} %{?!_with_rtonly:       0}
# Only build the automotive kernel (--with automotiveonly):%
%define with_automotiveonly %{?_with_automotiveonly:       1} %{?!_with_automotiveonly:       0}
# Only build the tools package
%define with_toolsonly %{?_with_toolsonly:    1} %{?!_with_toolsonly:    0}
# Control whether we perform a compat. check against published ABI.
%define with_kabichk   %{?_without_kabichk:   0} %{?!_without_kabichk:   1}
# Temporarily disable kabi checks until RC.
%define with_kabichk 0
# Control whether we perform a compat. check against DUP ABI.
%define with_kabidupchk %{?_with_kabidupchk:  1} %{?!_with_kabidupchk:   0}
#
# Control whether to run an extensive DWARF based kABI check.
# Note that this option needs to have baseline setup in SOURCE300.
%define with_kabidwchk %{?_without_kabidwchk: 0} %{?!_without_kabidwchk: 1}
%define with_kabidw_base %{?_with_kabidw_base: 1} %{?!_with_kabidw_base: 0}
#
# Control whether to install the vdso directories.
%define with_vdso_install %{?_without_vdso_install: 0} %{?!_without_vdso_install: 1}
#
# should we do C=1 builds with sparse
%define with_sparse    %{?_with_sparse:       1} %{?!_with_sparse:       0}
#
# Cross compile requested?
%define with_cross    %{?_with_cross:         1} %{?!_with_cross:        0}
#
# build a release kernel on rawhide
%define with_release   %{?_with_release:      1} %{?!_with_release:      0}

# verbose build, i.e. no silent rules and V=1
%define with_verbose %{?_with_verbose:        1} %{?!_with_verbose:      0}

#
# check for mismatched config options
%define with_configchecks %{?_without_configchecks:        0} %{?!_without_configchecks:        1}

#
# gcov support
%define with_gcov %{?_with_gcov:1}%{?!_with_gcov:0}

# Want to build a vanilla kernel build without any non-upstream patches?
%define with_vanilla %{?_with_vanilla: 1} %{?!_with_vanilla: 0}

%ifarch x86_64 aarch64 riscv64
%define with_efiuki %{?_without_efiuki: 0} %{?!_without_efiuki: 1}
%else
%define with_efiuki 0
%endif

%if 0%{?fedora}
# Kernel headers are being split out into a separate package
%define with_headers 0
%define with_cross_headers 0
# no stablelist
%define with_kernel_abi_stablelists 0
%define with_arm64_64k 0
%define with_realtime 0
%define with_realtime_arm64_64k 0
%define with_automotive 0
%endif

%if %{with_verbose}
%define make_opts V=1
%else
%define make_opts -s
%endif

%if %{with toolchain_clang}
%ifarch s390x ppc64le
%global llvm_ias 0
%else
%global llvm_ias 1
%endif
%global clang_make_opts HOSTCC=clang CC=clang LLVM_IAS=%{llvm_ias}
%if %{with clang_lto}
# LLVM=1 enables use of all LLVM tools.
%global clang_make_opts %{clang_make_opts} LLVM=1
%endif
%global make_opts %{make_opts} %{clang_make_opts}
%endif

# turn off debug kernel and kabichk for gcov builds
%if %{with_gcov}
%define with_debug 0
%define with_kabichk 0
%define with_kabidupchk 0
%define with_kabidwchk 0
%define with_kabidw_base 0
%define with_kernel_abi_stablelists 0
%endif

# turn off kABI DWARF-based check if we're generating the base dataset
%if %{with_kabidw_base}
%define with_kabidwchk 0
%endif

%define make_target bzImage
%define image_install_path boot

%define KVERREL %{specversion}-%{release}.%{_target_cpu}
%define KVERREL_RE %(echo %KVERREL | sed 's/+/[+]/g')
%define hdrarch %_target_cpu
%define asmarch %_target_cpu

%if 0%{!?nopatches:1}
%define nopatches 0
%endif

%if %{with_vanilla}
%define nopatches 1
%endif

%if %{with_release}
%define debugbuildsenabled 1
%endif

%if !%{with_debuginfo}
%define _enable_debug_packages 0
%endif
%define debuginfodir /usr/lib/debug
# Needed because we override almost everything involving build-ids
# and debuginfo generation. Currently we rely on the old alldebug setting.
%global _build_id_links alldebug

# if requested, only build base kernel
%if %{with_baseonly}
%define with_debug 0
%define with_realtime 0
%define with_vdso_install 0
%define with_perf 0
%define with_libperf 0
%define with_tools 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%endif

# if requested, only build debug kernel
%if %{with_dbgonly}
%define with_base 0
%define with_vdso_install 0
%define with_perf 0
%define with_libperf 0
%define with_tools 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%endif

# if requested, only build realtime kernel
%if %{with_rtonly}
%define with_realtime 1
%define with_realtime_arm64_64k 1
%define with_automotive 0
%define with_up 0
%define with_debug 0
%define with_debuginfo 0
%define with_vdso_install 0
%define with_perf 0
%define with_libperf 0
%define with_tools 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%define with_headers 0
%define with_efiuki 0
%define with_zfcpdump 0
%define with_arm64_16k 0
%define with_arm64_64k 0
%endif

# if requested, only build automotive kernel
%if %{with_automotiveonly}
%define with_automotive 1
%define with_realtime 0
%define with_up 0
%define with_debug 0
%define with_debuginfo 0
%define with_vdso_install 0
%define with_selftests 1
%endif

# if requested, only build tools
%if %{with_toolsonly}
%define with_tools 1
%define with_up 0
%define with_base 0
%define with_debug 0
%define with_realtime 0
%define with_realtime_arm64_64k 0
%define with_arm64_16k 0
%define with_arm64_64k 0
%define with_automotive 0
%define with_cross_headers 0
%define with_doc 0
%define with_selftests 0
%define with_headers 0
%define with_efiuki 0
%define with_zfcpdump 0
%define with_vdso_install 0
%define with_kabichk 0
%define with_kabidwchk 0
%define with_kabidw_base 0
%define with_kernel_abi_stablelists 0
%define with_selftests 0
%define with_vdso_install 0
%define with_configchecks 0
%endif

# RT and Automotive kernels are only built on x86_64 and aarch64
%ifnarch x86_64 aarch64
%define with_realtime 0
%define with_automotive 0
%endif

%if %{with_automotive}
# overrides compression algorithms for automotive
%global compression zstd
%global compression_flags --rm
%global compext zst

# automotive does not support the following variants
%define with_realtime 0
%define with_realtime_arm64_64k 0
%define with_arm64_16k 0
%define with_arm64_64k 0
%define with_efiuki 0
%define with_doc 0
%define with_headers 0
%define with_cross_headers 0
%define with_perf 0
%define with_libperf 0
%define with_tools 0
%define with_kabichk 0
%define with_kernel_abi_stablelists 0
%define with_kabidw_base 0
%endif


%if %{zipmodules}
%global zipsed -e 's/\.ko$/\.ko.%compext/'
# for parallel xz processes, replace with 1 to go back to single process
%endif

# turn off kABI DUP check and DWARF-based check if kABI check is disabled
%if !%{with_kabichk}
%define with_kabidupchk 0
%define with_kabidwchk 0
%endif

%if %{with_vdso_install}
%define use_vdso 1
%endif

%ifnarch noarch
%define with_kernel_abi_stablelists 0
%endif

# Overrides for generic default options

# only package docs noarch
%ifnarch noarch
%define with_doc 0
%define doc_build_fail true
%endif

%if 0%{?fedora}
# don't do debug builds on anything but aarch64 and x86_64
%ifnarch aarch64 x86_64
%define with_debug 0
%endif
%endif

%define all_configs %{name}-%{specrpmversion}-*.config

# don't build noarch kernels or headers (duh)
%ifarch noarch
%define with_up 0
%define with_realtime 0
%define with_automotive 0
%define with_headers 0
%define with_cross_headers 0
%define with_tools 0
%define with_perf 0
%define with_libperf 0
%define with_selftests 0
%define with_debug 0
%endif

# sparse blows up on ppc
%ifnarch ppc64le
%define with_sparse 0
%endif

# zfcpdump mechanism is s390 only
%ifnarch s390x
%define with_zfcpdump 0
%endif

# 16k and 64k variants only for aarch64
%ifnarch aarch64
%define with_arm64_16k 0
%define with_arm64_64k 0
%define with_realtime_arm64_64k 0
%endif

%if 0%{?fedora}
# This is not for Fedora
%define with_zfcpdump 0
%endif

# Per-arch tweaks

%ifarch i686
%define asmarch x86
%define hdrarch i386
%define kernel_image arch/x86/boot/bzImage
%endif

%ifarch x86_64
%define asmarch x86
%define kernel_image arch/x86/boot/bzImage
%endif

%ifarch ppc64le
%define asmarch powerpc
%define hdrarch powerpc
%define make_target vmlinux
%define kernel_image vmlinux
%define kernel_image_elf 1
%define use_vdso 0
%endif

%ifarch s390x
%define asmarch s390
%define hdrarch s390
%define kernel_image arch/s390/boot/bzImage
%define vmlinux_decompressor arch/s390/boot/vmlinux
%endif

%ifarch aarch64
%define asmarch arm64
%define hdrarch arm64
%define make_target vmlinuz.efi
%define kernel_image arch/arm64/boot/vmlinuz.efi
%endif

%ifarch riscv64
%define asmarch riscv
%define hdrarch riscv
%define make_target vmlinuz.efi
%define kernel_image arch/riscv/boot/vmlinuz.efi
%endif

# Should make listnewconfig fail if there's config options
# printed out?
%if %{nopatches}
%define with_configchecks 0
%endif

# To temporarily exclude an architecture from being built, add it to
# %%nobuildarches. Do _NOT_ use the ExclusiveArch: line, because if we
# don't build kernel-headers then the new build system will no longer let
# us use the previous build of that package -- it'll just be completely AWOL.
# Which is a BadThing(tm).

# We only build kernel-headers on the following...
%if 0%{?fedora}
%define nobuildarches i386
%else
%define nobuildarches i386 i686
%endif

%ifarch %nobuildarches
# disable BuildKernel commands
%define with_up 0
%define with_debug 0
%define with_zfcpdump 0
%define with_arm64_16k 0
%define with_arm64_64k 0
%define with_realtime 0
%define with_realtime_arm64_64k 0
%define with_automotive 0

%define with_debuginfo 0
%define with_perf 0
%define with_libperf 0
%define with_tools 0
%define with_selftests 0
%define _enable_debug_packages 0
%endif

# Architectures we build tools/cpupower on
%if 0%{?fedora}
%define cpupowerarchs %{ix86} x86_64 ppc64le aarch64 riscv64
%else
%define cpupowerarchs i686 x86_64 ppc64le aarch64 riscv64
%endif

# Architectures we build kernel livepatching selftests on
%define klptestarches x86_64 ppc64le s390x

%if 0%{?use_vdso}
%define _use_vdso 1
%else
%define _use_vdso 0
%endif

# If build of debug packages is disabled, we need to know if we want to create
# meta debug packages or not, after we define with_debug for all specific cases
# above. So this must be at the end here, after all cases of with_debug or not.
%define with_debug_meta 0
%if !%{debugbuildsenabled}
%if %{with_debug}
%define with_debug_meta 1
%endif
%define with_debug 0
%endif

# short-hand for "are we building base/non-debug variants of ...?"
%if %{with_up} && %{with_base}
%define with_up_base 1
%else
%define with_up_base 0
%endif
%if %{with_realtime} && %{with_base}
%define with_realtime_base 1
%else
%define with_realtime_base 0
%endif
%if %{with_automotive} && %{with_base}
%define with_automotive_base 1
%else
%define with_automotive_base 0
%endif
%if %{with_arm64_16k} && %{with_base}
%define with_arm64_16k_base 1
%else
%define with_arm64_16k_base 0
%endif
%if %{with_arm64_64k} && %{with_base}
%define with_arm64_64k_base 1
%else
%define with_arm64_64k_base 0
%endif
%if %{with_realtime_arm64_64k} && %{with_base}
%define with_realtime_arm64_64k_base 1
%else
%define with_realtime_arm64_64k_base 0
%endif

#
# Packages that need to be installed before the kernel is, because the %%post
# scripts use them.
#
%define kernel_prereq  coreutils, systemd >= 203-2, /usr/bin/kernel-install
%define initrd_prereq  dracut >= 027


Name: %{package_name}
License: ((GPL-2.0-only WITH Linux-syscall-note) OR BSD-2-Clause) AND ((GPL-2.0-only WITH Linux-syscall-note) OR BSD-3-Clause) AND ((GPL-2.0-only WITH Linux-syscall-note) OR CDDL-1.0) AND ((GPL-2.0-only WITH Linux-syscall-note) OR Linux-OpenIB) AND ((GPL-2.0-only WITH Linux-syscall-note) OR MIT) AND ((GPL-2.0-or-later WITH Linux-syscall-note) OR BSD-3-Clause) AND ((GPL-2.0-or-later WITH Linux-syscall-note) OR MIT) AND 0BSD AND BSD-2-Clause AND (BSD-2-Clause OR Apache-2.0) AND BSD-3-Clause AND BSD-3-Clause-Clear AND CC0-1.0 AND GFDL-1.1-no-invariants-or-later AND GPL-1.0-or-later AND (GPL-1.0-or-later OR BSD-3-Clause) AND (GPL-1.0-or-later WITH Linux-syscall-note) AND GPL-2.0-only AND (GPL-2.0-only OR Apache-2.0) AND (GPL-2.0-only OR BSD-2-Clause) AND (GPL-2.0-only OR BSD-3-Clause) AND (GPL-2.0-only OR CDDL-1.0) AND (GPL-2.0-only OR GFDL-1.1-no-invariants-or-later) AND (GPL-2.0-only OR GFDL-1.2-no-invariants-only) AND (GPL-2.0-only OR GFDL-1.2-no-invariants-or-later) AND (GPL-2.0-only WITH Linux-syscall-note) AND GPL-2.0-or-later AND (GPL-2.0-or-later OR BSD-2-Clause) AND (GPL-2.0-or-later OR BSD-3-Clause) AND (GPL-2.0-or-later OR CC-BY-4.0) AND (GPL-2.0-or-later WITH GCC-exception-2.0) AND (GPL-2.0-or-later WITH Linux-syscall-note) AND ISC AND LGPL-2.0-or-later AND (LGPL-2.0-or-later OR BSD-2-Clause) AND (LGPL-2.0-or-later WITH Linux-syscall-note) AND LGPL-2.1-only AND (LGPL-2.1-only OR BSD-2-Clause) AND (LGPL-2.1-only WITH Linux-syscall-note) AND LGPL-2.1-or-later AND (LGPL-2.1-or-later WITH Linux-syscall-note) AND (Linux-OpenIB OR GPL-2.0-only) AND (Linux-OpenIB OR GPL-2.0-only OR BSD-2-Clause) AND Linux-man-pages-copyleft AND MIT AND (MIT OR Apache-2.0) AND (MIT OR GPL-2.0-only) AND (MIT OR GPL-2.0-or-later) AND (MIT OR LGPL-2.1-only) AND (MPL-1.1 OR GPL-2.0-only) AND (X11 OR GPL-2.0-only) AND (X11 OR GPL-2.0-or-later) AND Zlib AND (copyleft-next-0.3.1 OR GPL-2.0-or-later)
URL: https://www.kernel.org/
Version: %{specrpmversion}
Release: %{pkg_release}
# DO NOT CHANGE THE 'ExclusiveArch' LINE TO TEMPORARILY EXCLUDE AN ARCHITECTURE BUILD.
# SET %%nobuildarches (ABOVE) INSTEAD
%if 0%{?fedora}
ExclusiveArch: noarch x86_64 s390x aarch64 ppc64le riscv64
%else
ExclusiveArch: noarch i386 i686 x86_64 s390x aarch64 ppc64le
%endif
ExclusiveOS: Linux
%ifnarch %{nobuildarches}
Requires: kernel-core-uname-r = %{KVERREL}
Requires: kernel-modules-uname-r = %{KVERREL}
Requires: kernel-modules-core-uname-r = %{KVERREL}
Requires: ((kernel-modules-extra-uname-r = %{KVERREL}) if kernel-modules-extra-matched)
Provides: installonlypkg(kernel)
%endif


#
# List the packages used during the kernel build
#
BuildRequires: kmod, bash, coreutils, tar, git-core, which
BuildRequires: bzip2, xz, findutils, m4, perl-interpreter, perl-Carp, perl-devel, perl-generators, make, diffutils, gawk, %compression
# Kernel EFI/Compression set by CONFIG_KERNEL_ZSTD
%ifarch x86_64 aarch64 riscv64
BuildRequires: zstd
%endif
BuildRequires: gcc, binutils, redhat-rpm-config, hmaccalc, bison, flex, gcc-c++
BuildRequires: rust, rust-src, bindgen, rustfmt, clippy
BuildRequires: net-tools, hostname, bc, elfutils-devel
BuildRequires: dwarves
BuildRequires: python3
BuildRequires: python3-devel
BuildRequires: python3-pyyaml
BuildRequires: kernel-rpm-macros
# glibc-static is required for a consistent build environment (specifically
# CONFIG_CC_CAN_LINK_STATIC=y).
BuildRequires: glibc-static
%if %{with_headers} || %{with_cross_headers}
BuildRequires: rsync
%endif
%if %{with_doc}
BuildRequires: xmlto, asciidoc, python3-sphinx, python3-sphinx_rtd_theme
%endif
%if %{with_sparse}
BuildRequires: sparse
%endif
%if %{with_perf}
BuildRequires: zlib-devel binutils-devel newt-devel perl(ExtUtils::Embed) bison flex xz-devel
BuildRequires: audit-libs-devel python3-setuptools
BuildRequires: java-devel
BuildRequires: libbpf-devel >= 0.6.0-1
BuildRequires: libbabeltrace-devel
BuildRequires: libtraceevent-devel
%ifnarch s390x
BuildRequires: numactl-devel
%endif
%ifarch aarch64
BuildRequires: opencsd-devel >= 1.0.0
%endif
%endif
%if %{with_tools}
BuildRequires: python3-docutils
BuildRequires: gettext ncurses-devel
BuildRequires: libcap-devel libcap-ng-devel
# The following are rtla requirements
BuildRequires: python3-docutils
BuildRequires: libtraceevent-devel
BuildRequires: libtracefs-devel
BuildRequires: libbpf-devel
BuildRequires: bpftool
BuildRequires: clang

%ifnarch s390x
BuildRequires: pciutils-devel
%endif
%ifarch i686 x86_64
BuildRequires: libnl3-devel
%endif
%endif

%if %{with_tools} && %{with_ynl}
BuildRequires: python3-pyyaml python3-jsonschema python3-pip python3-setuptools >= 61
BuildRequires: (python3-wheel if python3-setuptools < 70)
%endif

%if %{with_tools} || %{signmodules} || %{signkernel}
BuildRequires: openssl-devel
%endif
%if %{with_selftests}
BuildRequires: clang llvm-devel fuse-devel zlib-devel binutils-devel python3-docutils python3-jsonschema
%ifarch x86_64 riscv64
BuildRequires: lld
%endif
BuildRequires: libcap-devel libcap-ng-devel rsync libmnl-devel
BuildRequires: numactl-devel
%endif
BuildConflicts: rhbuildsys(DiskFree) < 500Mb
%if %{with_debuginfo}
BuildRequires: rpm-build, elfutils
BuildConflicts: rpm < 4.13.0.1-19
BuildConflicts: dwarves < 1.13
# Most of these should be enabled after more investigation
%undefine _include_minidebuginfo
%undefine _find_debuginfo_dwz_opts
%undefine _unique_build_ids
%undefine _unique_debug_names
%undefine _unique_debug_srcs
%undefine _debugsource_packages
%undefine _debuginfo_subpackages

# Remove -q option below to provide 'extracting debug info' messages
%global _find_debuginfo_opts -r -q

%global _missing_build_ids_terminate_build 1
%global _no_recompute_build_ids 1
%endif
%if %{with_kabidwchk} || %{with_kabidw_base}
BuildRequires: kabi-dw
%endif

%if %{signkernel}%{signmodules}
BuildRequires: openssl
%if %{signkernel}
# ELN uses Fedora signing process, so exclude
%if 0%{?rhel}%{?centos} && !0%{?eln}
BuildRequires: system-sb-certs
%endif
%ifarch x86_64 aarch64 riscv64
BuildRequires: nss-tools
BuildRequires: pesign >= 0.10-4
%endif
%endif
%endif

%if %{with_cross}
BuildRequires: binutils-%{_build_arch}-linux-gnu, gcc-%{_build_arch}-linux-gnu
%define cross_opts CROSS_COMPILE=%{_build_arch}-linux-gnu-
%define __strip %{_build_arch}-linux-gnu-strip

%if 0%{?fedora} && 0%{?fedora} <= 41
# Work around find-debuginfo for cross builds.
# find-debuginfo doesn't support any of CROSS options (RHEL-21797),
# and since debugedit > 5.0-16.el10, or since commit
#   dfe1f7ff30f4 ("find-debuginfo.sh: Exit with real exit status in parallel jobs")
# it now aborts on failure and build fails.
# debugedit-5.1-5 in F42 added support to override tools with target versions.
%undefine _include_gdb_index
%endif
%endif

# These below are required to build man pages
%if %{with_perf}
BuildRequires: xmlto
%endif
%if %{with_perf} || %{with_tools}
BuildRequires: asciidoc
%endif

%if %{with toolchain_clang}
BuildRequires: clang
%endif

%if %{with clang_lto}
BuildRequires: llvm
BuildRequires: lld
%endif

%if %{with_efiuki}
BuildRequires: dracut
# For dracut UEFI uki binaries
BuildRequires: binutils
# For the initrd
BuildRequires: lvm2
BuildRequires: systemd-boot-unsigned
# For systemd-stub and systemd-pcrphase
BuildRequires: systemd-udev >= 252-1
# For UKI kernel cmdline addons
BuildRequires: systemd-ukify
# For TPM operations in UKI initramfs
BuildRequires: tpm2-tools
# For UKI sb cert
%if 0%{?rhel}%{?centos} && !0%{?eln}
%if 0%{?centos}
BuildRequires: centos-sb-certs >= 9.0-23
%else
BuildRequires: redhat-sb-certs >= 9.4-0.1
%endif
%endif
%endif

# Because this is the kernel, it's hard to get a single upstream URL
# to represent the base without needing to do a bunch of patching. This
# tarball is generated from a src-git tree. If you want to see the
# exact git commit you can run
#
# xzcat -qq ${TARBALL} | git get-tar-commit-id
Source0: linux-%{tarfile_release}.tar.xz

Source1: Makefile.rhelver
Source2: kernel.changelog

Source10: redhatsecurebootca5.cer
Source13: redhatsecureboot501.cer

%if %{signkernel}
# Name of the packaged file containing signing key
%ifarch ppc64le
%define signing_key_filename kernel-signing-ppc.cer
%endif
%ifarch s390x
%define signing_key_filename kernel-signing-s390.cer
%endif

# Fedora/ELN pesign macro expects to see these cert file names, see:
# https://github.com/rhboot/pesign/blob/main/src/pesign-rpmbuild-helper.in#L216
%if 0%{?fedora}%{?eln}
%define pesign_name_0 redhatsecureboot501
%define secureboot_ca_0 %{SOURCE10}
%define secureboot_key_0 %{SOURCE13}
%endif

# RHEL/centos certs come from system-sb-certs
%if 0%{?rhel} && !0%{?eln}
%define secureboot_ca_0 %{_datadir}/pki/sb-certs/secureboot-ca-%{_arch}.cer
%define secureboot_key_0 %{_datadir}/pki/sb-certs/secureboot-kernel-%{_arch}.cer

%if 0%{?centos}
%define pesign_name_0 centossecureboot201
%else
%ifarch x86_64 aarch64
%define pesign_name_0 redhatsecureboot501
%endif
%ifarch s390x
%define pesign_name_0 redhatsecureboot302
%endif
%ifarch ppc64le
%define pesign_name_0 redhatsecureboot701
%endif
%endif
# rhel && !eln
%endif

# signkernel
%endif

Source20: mod-denylist.sh
Source21: mod-sign.sh
Source22: filtermods.py

%define modsign_cmd %{SOURCE21}

%if 0%{?include_rhel}
Source23: x509.genkey.rhel

Source24: %{name}-aarch64-rhel.config
Source25: %{name}-aarch64-debug-rhel.config

Source27: %{name}-ppc64le-rhel.config
Source28: %{name}-ppc64le-debug-rhel.config
Source29: %{name}-s390x-rhel.config
Source30: %{name}-s390x-debug-rhel.config
Source31: %{name}-s390x-zfcpdump-rhel.config
Source32: %{name}-x86_64-rhel.config
Source33: %{name}-x86_64-debug-rhel.config

Source34: def_variants.yaml.rhel

Source41: x509.genkey.centos
# ARM64 64K page-size kernel config
Source42: %{name}-aarch64-64k-rhel.config
Source43: %{name}-aarch64-64k-debug-rhel.config

%endif

%if 0%{?include_fedora}
Source50: x509.genkey.fedora

Source52: %{name}-aarch64-fedora.config
Source53: %{name}-aarch64-debug-fedora.config
Source54: %{name}-aarch64-16k-fedora.config
Source55: %{name}-aarch64-16k-debug-fedora.config
Source56: %{name}-ppc64le-fedora.config
Source57: %{name}-ppc64le-debug-fedora.config
Source58: %{name}-s390x-fedora.config
Source59: %{name}-s390x-debug-fedora.config
Source60: %{name}-x86_64-fedora.config
Source61: %{name}-x86_64-debug-fedora.config
Source700: %{name}-riscv64-fedora.config
Source701: %{name}-riscv64-debug-fedora.config

Source62: def_variants.yaml.fedora
%endif

Source70: partial-kgcov-snip.config
Source71: partial-kgcov-debug-snip.config
Source72: partial-clang-snip.config
Source73: partial-clang-debug-snip.config
Source74: partial-clang_lto-x86_64-snip.config
Source75: partial-clang_lto-x86_64-debug-snip.config
Source76: partial-clang_lto-aarch64-snip.config
Source77: partial-clang_lto-aarch64-debug-snip.config
Source80: generate_all_configs.sh
Source81: process_configs.sh

Source86: dracut-virt.conf

Source87: flavors

Source151: uki_create_addons.py
Source152: uki_addons.json

Source100: rheldup3.x509
Source101: rhelkpatch1.x509
Source102: nvidiagpuoot001.x509
Source103: rhelimaca1.x509
Source104: rhelima.x509
Source105: rhelima_centos.x509
Source106: fedoraimaca.x509

%if 0%{?fedora}%{?eln}
%define ima_ca_cert %{SOURCE106}
%endif

%if 0%{?rhel} && !0%{?eln}
%define ima_ca_cert %{SOURCE103}
# rhel && !eln
%endif

%if 0%{?centos}
%define ima_signing_cert %{SOURCE105}
%else
%define ima_signing_cert %{SOURCE104}
%endif

%define ima_cert_name ima.cer

Source200: check-kabi

Source201: Module.kabi_aarch64
Source202: Module.kabi_ppc64le
Source203: Module.kabi_s390x
Source204: Module.kabi_x86_64
Source205: Module.kabi_riscv64

Source210: Module.kabi_dup_aarch64
Source211: Module.kabi_dup_ppc64le
Source212: Module.kabi_dup_s390x
Source213: Module.kabi_dup_x86_64
Source214: Module.kabi_dup_riscv64

Source300: kernel-abi-stablelists-%{kabiversion}.tar.xz
Source301: kernel-kabi-dw-%{kabiversion}.tar.xz

%if 0%{include_rt}
%if 0%{include_rhel}
Source474: %{name}-aarch64-rt-rhel.config
Source475: %{name}-aarch64-rt-debug-rhel.config
Source476: %{name}-aarch64-rt-64k-rhel.config
Source477: %{name}-aarch64-rt-64k-debug-rhel.config
Source478: %{name}-x86_64-rt-rhel.config
Source479: %{name}-x86_64-rt-debug-rhel.config
%endif
%if 0%{include_fedora}
Source480: %{name}-aarch64-rt-fedora.config
Source481: %{name}-aarch64-rt-debug-fedora.config
Source482: %{name}-aarch64-rt-64k-fedora.config
Source483: %{name}-aarch64-rt-64k-debug-fedora.config
Source484: %{name}-x86_64-rt-fedora.config
Source485: %{name}-x86_64-rt-debug-fedora.config
Source486: %{name}-riscv64-rt-fedora.config
Source487: %{name}-riscv64-rt-debug-fedora.config
%endif
%endif

%if %{include_automotive}
# automotive config files
Source488: %{name}-aarch64-automotive-rhel.config
Source489: %{name}-aarch64-automotive-debug-rhel.config
Source490: %{name}-x86_64-automotive-rhel.config
Source491: %{name}-x86_64-automotive-debug-rhel.config
%endif


# Sources for kernel-tools
Source2002: kvm_stat.logrotate

# Some people enjoy building customized kernels from the dist-git in Fedora and
# use this to override configuration options. One day they may all use the
# source tree, but in the mean time we carry this to support the legacy workflow
Source3000: merge.py
Source3001: kernel-local
%if %{patchlist_changelog}
Source3002: Patchlist.changelog
%endif

Source4000: README.rst
Source4001: rpminspect.yaml
Source4002: gating.yaml

## Patches needed for building this package

%if !%{nopatches}

Patch1: patch-%{patchversion}-redhat.patch





Patch10001: 0001-add-k1-pro-base-platform-support.patch
Patch10002: 0002-media-support-a-new-vpu-driver-which-use-V4L2-standa.patch
Patch10003: 0003-add-SOC_SPACEMIT_K1-for-spacemit-k1-serial-SOCs.patch
Patch10004: 0004-update-kernel-configuration-for-qemu-board.patch
Patch10005: 0005-kernel-config-add-SOC_SPACEMIT_K1_FPGA-option-for-fp.patch
Patch10006: 0006-fpga-kconfig-update-kernel-configuration-for-k1-pro-.patch
Patch10007: 0007-qemu-kconfig-update-kernel-configuration-for-k1-pro-.patch
Patch10008: 0008-sim-kconfig-update-kernel-configuration-for-k1-pro-s.patch
Patch10009: 0009-add-k1pro-ccu-driver-and-config.patch
Patch10010: 0010-add-k1pro-reset-controller-driver-and-config.patch
Patch10011: 0011-update-kernel-config-add-FPGA-label-and-enable-debug.patch
Patch10012: 0012-dtsi-enable-zicbom.patch
Patch10013: 0013-change-dtb-configuration-to-k1-pro-SOC-1.-ddr-uart-p.patch
Patch10014: 0014-dts-add-tcm-node-kernel-add-tcm-driver.patch
Patch10015: 0015-add-.h-for-clock-reset-and-change-reg.patch
Patch10016: 0016-pwm-dwc-driver-loaded-by-platform-changes-in-Makefil.patch
Patch10017: 0017-sync-clk-reset-V1.1-spec-and-use-CLK_OF_DECLARE-for-.patch
Patch10018: 0018-spi-adding-the-driver-for-Designware-enhanced-spi-co.patch
Patch10019: 0019-riscv-support-svpbmt.patch
Patch10020: 0020-usb-dwc3-support-spacemit-platform.patch
Patch10021: 0021-dts-dwc3-add-dts-config-for-k1-pro.patch
Patch10022: 0022-usb-update-usb-kernel-configuration.patch
Patch10023: 0023-usb-dwc3-avoid-suspend-phy.patch
Patch10024: 0024-riscv-mm-fix-reserve-cma-for-platform-not-having-ZON.patch
Patch10025: 0025-kconfig-enable-cma-for-k1-pro-board.patch
Patch10026: 0026-ethernet-adding-the-driver-of-the-Designware-gmac-co.patch
Patch10027: 0027-reset-reset-driver-handle-all-global-soft-reset-sing.patch
Patch10028: 0028-dma-dw-axi-dma-support-handshake-num-more-than-16.patch
Patch10029: 0029-usb-dwc3-modify-reset-control-for-usb31.patch
Patch10030: 0030-usb-dwc3-modify-DMA-capability.patch
Patch10031: 0031-dma-fix-an-error-burst_trans_len-undeclare-in-dma-dr.patch
Patch10032: 0032-mmc-support-spacemit-k1-pro-platform.patch
Patch10033: 0033-mmc-dts-support-emmc-and-sdcard.patch
Patch10034: 0034-reset-add-spinlock-for-timing-issue.patch
Patch10035: 0035-mmc-modify-reset-card-only-once.patch
Patch10036: 0036-reshape-dtsi-format-use-table-to-replace-space.patch
Patch10037: 0037-k1-pro.dtsi-add-pmu-configs.patch
Patch10038: 0038-pcie-support-spacemit-k1-pro-pcie-controller-RC-mode.patch
Patch10039: 0039-usb-xhci-modify-DMA-capability-for-k1-pro-platform.patch
Patch10040: 0040-change-dts-for-I2C-support.patch
Patch10041: 0041-can-add-can-device-driver-and-kernel-config.patch
Patch10042: 0042-ccu-add-mcu-clocks.patch
Patch10043: 0043-fs-support-nfs.patch
Patch10044: 0044-spi-support-spi-nor-and-correct-the-params-of-the-sp.patch
Patch10045: 0045-mmc-enable-host-version-4-mode.patch
Patch10046: 0046-mmc-deattach-clk-400k-during-mmc_rescan.patch
Patch10047: 0047-add-script-for-extract-generate-rootfs.cpio.gz.patch
Patch10048: 0048-mmc-increase-date-timeout-counter-value-to-max.patch
Patch10049: 0049-remoteproc-support-bringup-esos-for-spacemit-k1-pro_.patch
Patch10050: 0050-media-support-usb-media-enable-uvc-and-f_uvc.patch
Patch10051: 0051-vpu-fix-vpu-compile-error-for-linux6.1.patch
Patch10052: 0052-vpu-add-vpu-dts-config.patch
Patch10053: 0053-can-update-kernel-defconfig-IPMS_CAN-y.patch
Patch10054: 0054-clk-add-spinlock-and-mailbox-clock-for-mcu-system.patch
Patch10055: 0055-reset-add-spinlock-and-mailbox-reset-for-mcu-system.patch
Patch10056: 0056-mailbox-enable-spacemit-mailbox-driver.patch
Patch10057: 0057-scmi-support-arm-s-scmi-protocol-for-spacemit-platfo.patch
Patch10058: 0058-rproc-change-compatible-name-for-rproc-driver.patch
Patch10059: 0059-pinctrl-support-the-driver-of-spacemit-pinctrl-contr.patch
Patch10060: 0060-dts-add-the-table-of-pin-functions.patch
Patch10061: 0061-vpu-add-reset-control-logic.patch
Patch10062: 0062-vpu-add-device-caps-config.patch
Patch10063: 0063-vpu-remove-severity-and-drain-file-node-for-probe-er.patch
Patch10064: 0064-vpu-enable-debug-mode.patch
Patch10065: 0065-arm_scmi-regulator-enable-an-dummy-regulator-using-s.patch
Patch10066: 0066-dts-disable-vpu-as-some-bitfiles-have-no-vpu.patch
Patch10067: 0067-ethernet-support-ethernet-qos.patch
Patch10068: 0068-scmi-enable-scmi-power-domain-protocol.patch
Patch10069: 0069-scmi-voltage_domain-add-vlittle-vgpu-nodes-in-scmi-d.patch
Patch10070: 0070-cpufreq-support-scmi-cpufreq-driver-spacemit-platfor.patch
Patch10071: 0071-wifi-cfg80211-enable-wireless-LAN-configuration-API.patch
Patch10072: 0072-mmc-dts-support-sdio-interface.patch
Patch10073: 0073-GMAC-support-IEEE_1588-hwtimestamp.patch
Patch10074: 0074-usb-dts-add-dwc2-dts-for-k1-pro-fpga.patch
Patch10075: 0075-usb-kconfig-enable-dwc2-configuration.patch
Patch10076: 0076-usb-dwc2-add-params-for-k1-pro-fpga.patch
Patch10077: 0077-pinctrl-change-the-format-of-pin-config.patch
Patch10078: 0078-spi-nand-support-2x-4x-8x-for-spi-nand-tx-and-rx.patch
Patch10079: 0079-ubi-kconfig-enable-ubi-configuration.patch
Patch10080: 0080-usb-dwc2-modify-gadget-DMA-capability.patch
Patch10081: 0081-add-k1-x-device-support.patch
Patch10082: 0082-update-vpu-driver.patch
Patch10083: 0083-cpu-support-cpu-hotplug.patch
Patch10084: 0084-pinctrl-modify-the-format-of-the-pinctrl-group-name.patch
Patch10085: 0085-update-dts-for-k1-x-platform.patch
Patch10086: 0086-add-pxa_k1x-driver-for-k1x-platform.patch
Patch10087: 0087-k1pro-enable-first-can-use-version-of-cpuidle.patch
Patch10088: 0088-k1x-multi-core-modify-the-configurations-related-to-.patch
Patch10089: 0089-k1pro-add-i2c-configuration.patch
Patch10090: 0090-disable-pm-power-management-is-not-support-now.patch
Patch10091: 0091-k1-x-add-mmp_pdma-driver-support.patch
Patch10092: 0092-k1x-add-k1-x_fpga-1x4-2x2-proj.patch
Patch10093: 0093-k1-x-support-pxa-uart-driver-dts-configs-pm-amend-in.patch
Patch10094: 0094-ethernet-adding-gmac-driver-for-k1-x.patch
Patch10095: 0095-mmc-support-spacemit-k1x-platform.patch
Patch10096: 0096-ethernet-change-the-phy-mode-config-from-device-tree.patch
Patch10097: 0097-hotplug-we-d-better-flush-the-local-l2-cache-when-on.patch
Patch10098: 0098-mmc-update-dts-remove-axi-node.patch
Patch10099: 0099-turn-off-CONFIG_PM-for-debug.patch
Patch10100: 0100-config-support-gmac-driver-for-k1-x-1x4-and-2x2.patch
Patch10101: 0101-support-tcm-for-k1x.patch
Patch10102: 0102-add-udma-driver-for-userspace.patch
Patch10103: 0103-dma-copy-use-vaddr.patch
Patch10104: 0104-rm-udma-log.patch
Patch10105: 0105-update-defconfig-for-support-sdmmc-udma.patch
Patch10106: 0106-add-mutex-va2pa-fix-tcm_discontinuous_malloc.patch
Patch10107: 0107-update-for-support-tcm.patch
Patch10108: 0108-usb-gadget-support-k1x-udc.patch
Patch10109: 0109-pcie-adding-pcie-driver-for-k1x.patch
Patch10110: 0110-usb-dwc3-support-k1x-platform.patch
Patch10111: 0111-k1x-add-pwm-pxa-driver-support.patch
Patch10112: 0112-update-vpu-driver.patch
Patch10113: 0113-k1pro-adjust-pwm-driver-config-name.patch
Patch10114: 0114-k1x-add-soc-timer-driver-support.patch
Patch10115: 0115-k1pro-deconfig-axi-dma-driver-Y.patch
Patch10116: 0116-support-I2C-for-k1x.patch
Patch10117: 0117-media-k1x-vpu-reshape-file-style.patch
Patch10118: 0118-update-kernel-default-config.patch
Patch10119: 0119-reset-update-reset-controller-driver.patch
Patch10120: 0120-ccu-update-clock-controller-driver.patch
Patch10121: 0121-fix-config-PCIE_SPACEMIT-depends-on-CONFIG_SOC_SPACE.patch
Patch10122: 0122-k1x-switch-pwm-deconfig-Y-on-1x4-2x2-board.patch
Patch10123: 0123-k1pro-cpuidle-support-cpuidle.patch
Patch10124: 0124-k1pro-add-k1pro-fpga_1x4-k1pro-fpga_2x2-proj.patch
Patch10125: 0125-k1-x-add-k1x-gpio-driver-support.patch
Patch10126: 0126-riscv-spacemit-remove-k1pro-configuration-it-is-just.patch
Patch10127: 0127-yk1x-add-the-first-version-of-pm-domain.patch
Patch10128: 0128-k1-x-add-gmac-PTP-support.patch
Patch10129: 0129-usb-dwc2-update-fifo-and-reset-config-for-k1-pro.patch
Patch10130: 0130-k1x-enable-dmabuf.patch
Patch10131: 0131-qspi-adding-driver-for-k1x-qspi-controller.patch
Patch10132: 0132-qspi-fix-typo-cause-compilation-errors.patch
Patch10133: 0133-add-spacemit-ir-rx-driver.patch
Patch10134: 0134-k1x-dts-modify-the-actual-reference-clock-for-sdhci.patch
Patch10135: 0135-k1pro-cpuidle-support-cpu0-cluster0-go-deepidle.patch
Patch10136: 0136-cpuidle-adapt-code-for-CPUidle-functionality.patch
Patch10137: 0137-update-k1x-vpu-driver.patch
Patch10138: 0138-k1x-cpuidle-synchronize-relevant-patches-from-k1pro.patch
Patch10139: 0139-k1x-support-cpufreq-driver.patch
Patch10140: 0140-reset-add-reset-controller-driver-for-k1x.patch
Patch10141: 0141-clock-add-clock-controller-driver-for-k1x.patch
Patch10142: 0142-dts-fix-worng-and-warning-for-k1x-clk-reset.patch
Patch10143: 0143-clock-fix-k1x-clock-id.patch
Patch10144: 0144-pinctrl-adding-pinctrl-config-for-k1x-soc.patch
Patch10145: 0145-reset-modify-reset-driver-file-name-of-k1pro.patch
Patch10146: 0146-clock-modify-clock-driver-file-name-of-k1pro.patch
Patch10147: 0147-pm_domain-move-the-pm_domain-driver-to-the-directy-s.patch
Patch10148: 0148-v2d-Add-v2d-driver.patch
Patch10149: 0149-add-tcm_cfg_save-restore.patch
Patch10150: 0150-add-tcm-sync-malloc-code-clean.patch
Patch10151: 0151-update-k1-x_fpga.dts-with-device-k1-x-board.dts.patch
Patch10152: 0152-mmc-sdhci-of-k1x-support-configure-reset-and-clk-fro.patch
Patch10153: 0153-usb-add-reset-and-clk-configurations.patch
Patch10154: 0154-pinctrl-supports-the-allocation-of-GPIOs-with-the-sa.patch
Patch10155: 0155-pcie-update-the-operations-of-clk-and-reset.patch
Patch10156: 0156-display-Add-spacemit-drm-driver.patch
Patch10157: 0157-gpu-Add-spacemit-gpu-driver.patch
Patch10158: 0158-gpio-update-the-operation-of-clk-for-gpio.patch
Patch10159: 0159-pmic-add-the-first-version-of-pmic-driver.patch
Patch10160: 0160-pmic-spm8821-pinctrl-first-version-to-support-pinctr.patch
Patch10161: 0161-fix-some-warning-when-building-dts.patch
Patch10162: 0162-add-configurations-for-k1-x-evb-board.patch
Patch10163: 0163-ethernet-update-driver-of-k1x-emac-driver.patch
Patch10164: 0164-pm-domain-correction-of-previous-driver-errors-and-a.patch
Patch10165: 0165-add-ranges-property-for-some-nodes-which-contain-som.patch
Patch10166: 0166-qspi-update-the-opertions-of-clk-and-reset-for-k1x-q.patch
Patch10167: 0167-pm_domain-improve-the-execution-process-of-this-driv.patch
Patch10168: 0168-pm_domain-move-the-pm-domain-dts-node-to-k1-x.dtsi-f.patch
Patch10169: 0169-gpu-Compatible-with-gpu-umd-driver.patch
Patch10170: 0170-camera-init-version-of-camera-driver-on-k1.patch
Patch10171: 0171-display-Add-spacemit-drm-debugfs-node.patch
Patch10172: 0172-k1x-dma-add-clk-reset-control-in-dma-driver.patch
Patch10173: 0173-qspi-adding-resets-for-k1-x-qspi.patch
Patch10174: 0174-fix-cpu-node-properties-defined-by-linux-6.x.y.patch
Patch10175: 0175-spi-add-the-driver-for-k1x-spi-controller.patch
Patch10176: 0176-pmic-pm853-support-regulator-driver-and-compatible-w.patch
Patch10177: 0177-k1x-uart-add-clock-reset-in-uart-driver.patch
Patch10178: 0178-clock-fix-clock-driver-issues-of-k1x.patch
Patch10179: 0179-pm-domain-add-new-feature.patch
Patch10180: 0180-update-dts-for-support-i2c0.patch
Patch10181: 0181-k1x-pwm-driver-adds-clk-reset-control.patch
Patch10182: 0182-update-kconfig-to-support-spacemit-k1x-timer-configu.patch
Patch10183: 0183-fix-uart-board-configuration-for-asic.patch
Patch10184: 0184-clock-reset-fix-pwm-clk-reset-reg-bit.patch
Patch10185: 0185-pm853-support-the-regulator-func-in-asic.patch
Patch10186: 0186-pmic-open-the-configuration-of-pmic-driver.patch
Patch10187: 0187-update-dts-for-i2c-to-support-clk-operation.patch
Patch10188: 0188-k1x-i2c-driver-add-clk-reset.patch
Patch10189: 0189-k1x-pm-domain-add-gnss-domain.patch
Patch10190: 0190-gmac-modify-the-config-for-k1x-gmac-controller.patch
Patch10191: 0191-usb-udc-k1x_udc-fix-udc-disconnect.patch
Patch10192: 0192-k1x-usb-fix-reset-and-clk-configuration.patch
Patch10193: 0193-update-evb-board-dts.patch
Patch10194: 0194-remove-some-unused-kernel-module.patch
Patch10195: 0195-k1-x-pinctrl-add-fast-config-for-sdcard.patch
Patch10196: 0196-update-board-dts-for-evb-and-fpga-boards.patch
Patch10197: 0197-display-Add-lcd-gc9503v_mipi.patch
Patch10198: 0198-support-jpu-driver-for-k1x.patch
Patch10199: 0199-clock-fix-the-result-of-set_rate-is-not-the-closest-.patch
Patch10200: 0200-clock-enable-some-clocks.patch
Patch10201: 0201-remove-clint-timer.patch
Patch10202: 0202-update-dtsi-for-k1-x-platform.patch
Patch10203: 0203-config-adding-spacemit-k1x-spi-driver.patch
Patch10204: 0204-qspi-fix-the-bus_num-for-k1x-qspi-controller.patch
Patch10205: 0205-k1x-vpu-update-driver.patch
Patch10206: 0206-k1x-dtsi-linlon-vpu-update-config.patch
Patch10207: 0207-usb-k1x_udc-deassert-reset-before-phy-init.patch
Patch10208: 0208-k1x-dma-1.add-pm-func-in-dma-driver-2.modify-dma-Kco.patch
Patch10209: 0209-k1x-uart-driver-add-pm-func.patch
Patch10210: 0210-k1x-i2c-driver-add-pm-domains-revision.patch
Patch10211: 0211-qspi-support-pm-runtime-for-qspi-driver.patch
Patch10212: 0212-dts-adding-power-domains-for-k1x-qspi.patch
Patch10213: 0213-k1x-pm-open-the-configuration-of-pm-domain-driver.patch
Patch10214: 0214-k1x-dtsi-jpu-update-config.patch
Patch10215: 0215-k1x-evb-defconfig-enable-CHIP_MEDIA_JPU.patch
Patch10216: 0216-add-some-debug-configuration.patch
Patch10217: 0217-feat-gpu-Support-gpu-for-k1x-evb-board.patch
Patch10218: 0218-mmc-k1x-add-host-capability-MMC_CAP_NEED_RSP_BUSY.patch
Patch10219: 0219-k1x-dtsi-jpu-add-reset-config.patch
Patch10220: 0220-k1x-uart-add-reference-to-pm-domain.patch
Patch10221: 0221-k1x-dma-add-reference-to-pm-domain.patch
Patch10222: 0222-k1x-cpufreq-support-cpufreq-function.patch
Patch10223: 0223-usb-phy-k1x-ci-usb2-update-phy-init-parameters-fix-h.patch
Patch10224: 0224-usb-ehci-add-support-for-k1-x-ehci-driver.patch
Patch10225: 0225-dts-k1-x-add-ehci-usb-host-support.patch
Patch10226: 0226-config-enable-k1x-ehci-host-driver.patch
Patch10227: 0227-update-evb-board-dts.patch
Patch10228: 0228-disable-cpufreq-it-will-crash-kernel.patch
Patch10229: 0229-config-k1-x-enable-more-usb-functions.patch
Patch10230: 0230-clock-fix-camm2-no-clock-issue-change-enable-bit.patch
Patch10231: 0231-clock-fix-set_rate-function-it-change-rate-by-div-an.patch
Patch10232: 0232-clock-enable-some-clocks-for-cpu-remove-cpu-core-clk.patch
Patch10233: 0233-k1x-cpufreq-don-t-need-to-set-parent-when-set-the-fr.patch
Patch10234: 0234-display-Support-lcd-icnl9911c-mipi.patch
Patch10235: 0235-sync-dts-with-device-board.dts.patch
Patch10236: 0236-usb-hid-enable-raw-HID-device-support.patch
Patch10237: 0237-clock-fix-qspi_clk-issue-only-set-fc-bit-when-settin.patch
Patch10238: 0238-k1x-pm-domain-change-the-log-level-of-debug-info.patch
Patch10239: 0239-display-fix-dpu-reset-control.patch
Patch10240: 0240-config-k1x-enable-usb-webcam-support.patch
Patch10241: 0241-k1x-add-watchdog-driver-support.patch
Patch10242: 0242-k1x-add-reboot-with-args-support.patch
Patch10243: 0243-fix-gpu-move-loading-firmware-later.patch
Patch10244: 0244-k1x-spacemit-timer-driver-add-clk-reset-interface.patch
Patch10245: 0245-k1x-timer-clk-reset-dts-config.patch
Patch10246: 0246-mmc-sdhci-of-k1x-add-quirks2-SDHCI_QUIRK2_BROKEN_64_.patch
Patch10247: 0247-reserved-2GB-4GB-area-from-memory-space-it-should-be.patch
Patch10248: 0248-k1x-pm_domain-using-hw-mode-to-power-on-off-audio-s-.patch
Patch10249: 0249-k1x-add-k1x-soc-rtc-driver-and-clk-reset-interface.patch
Patch10250: 0250-sync-evb-board-dts-from-device-k1x-evb-board.dts.patch
Patch10251: 0251-clean-compile-warning-in-arch-riscv-mm-init.c.patch
Patch10252: 0252-clean-compile-warning-in-display-driver.patch
Patch10253: 0253-clean-compile-warning-in-pcie-driver.patch
Patch10254: 0254-k1x-wdt-update-watchdog-driver.patch
Patch10255: 0255-clock-twsi8-clk-reset-reg-is-write-only-don-t-read-i.patch
Patch10256: 0256-k1x-reboot-fix-reboot-into-fastboot-mode-with-no-arg.patch
Patch10257: 0257-add-pwm-control-backlight.patch
Patch10258: 0258-k1x-pinctrl.dtsi-fix-some-pinctrl-error.patch
Patch10259: 0259-k1x-update-DTS-automatically-based-on-env.patch
Patch10260: 0260-mmc-sdhci-of-k1x-update-sdio-scan-interface.patch
Patch10261: 0261-add-tcm_override_readl-writel-for-access-tcm-overrid.patch
Patch10262: 0262-k1x-unique-mac-address-in-eeprom.patch
Patch10263: 0263-modify-compile-optimize-from-O2-to-Os.patch
Patch10264: 0264-clean-compile-waring-in-vpu-driver.patch
Patch10265: 0265-dts-add-apbc2-reg-base-for-clock-and-reset.patch
Patch10266: 0266-clock-add-apbc2-reg-base-clocks.patch
Patch10267: 0267-reset-add-apb2-reg-base-resets.patch
Patch10268: 0268-clock-add-CLK_IGNORE_UNUSED-flag-for-some-clocks.patch
Patch10269: 0269-vpu-can-use-when-RAM-2GB.patch
Patch10270: 0270-support-non-uniform-address-mapping-between-peripher.patch
Patch10271: 0271-add-nfsd-support.patch
Patch10272: 0272-add-exfat-fs-support.patch
Patch10273: 0273-add-xfs-support.patch
Patch10274: 0274-add-btrfs-support.patch
Patch10275: 0275-add-f2fs-support.patch
Patch10276: 0276-add-quota-used-by-ext4-support.patch
Patch10277: 0277-add-device-mapper-used-by-RAID-and-FS-crypto.patch
Patch10278: 0278-add-bridge-and-vlan-support-used-by-docker-vm.patch
Patch10279: 0279-add-ipv6-support.patch
Patch10280: 0280-add-ntfs-v3.1-same-with-win10-s-native-fs-support.patch
Patch10281: 0281-yk1x-thermal-support-thermal-driver.patch
Patch10282: 0282-k1x-dma-close-some-unnecessary-config.patch
Patch10283: 0283-k1x-dma-range-add-a-driver-for-devices-node-dram_ran.patch
Patch10284: 0284-k1x-dma-fix-compile-error-in-include-k1x-dmac.h.-def.patch
Patch10285: 0285-k1x-support-aes-crypto-engine.patch
Patch10286: 0286-k1x-kernel-support-afalg-engine.patch
Patch10287: 0287-support-camera-to-draw-when-use-2GB-DDR-dtsi-and-def.patch
Patch10288: 0288-clear-compile-warning.patch
Patch10289: 0289-clear-compile-warning.patch
Patch10290: 0290-sync-evb-board.dts-from-devices-k1x-evb.patch
Patch10291: 0291-camera-self-managed-ldo.patch
Patch10292: 0292-k1x-pm-domain-add-hdmi-domiain.patch
Patch10293: 0293-v2d-support-use-memory-2GB.patch
Patch10294: 0294-k1x-pmic-refine-some-code.patch
Patch10295: 0295-support-camera-to-draw-when-use-4GB-DDR.patch
Patch10296: 0296-display-phy-driver-has-been-registered-in-another-fu.patch
Patch10297: 0297-pci-add-initialization-phy-of-pcie-for-k1x.patch
Patch10298: 0298-k1x-pm-domain-the-IO-size-too-small-to-cover-the-HDM.patch
Patch10299: 0299-pcie-adding-dram_range1-for-pcie0-pcie1-pci2.patch
Patch10300: 0300-add-dts-and-config-for-deb2-board.patch
Patch10301: 0301-display-Support-spacemit-hdmi-driver.patch
Patch10302: 0302-target-add-task-management-values-and-overlapped-res.patch
Patch10303: 0303-usb-f_tcm-support-mutltiple-cmds-enhance-performance.patch
Patch10304: 0304-k1x-support-reboot-to-uboot-shell.patch
Patch10305: 0305-sync-evb-deb2-board-dts-from-devices.patch
Patch10306: 0306-fix-cpp-clk-timeout.patch
Patch10307: 0307-fix-gpu-memory-leak-when-launch-weston.patch
Patch10308: 0308-k1x-cpufreq-support-adjust-the-ace-tcm-s-frequency-a.patch
Patch10309: 0309-fix-dead-lock-bug-between-reset-and-clk.patch
Patch10310: 0310-k1x-cpu-cooling-support-cpu-cooling-device.patch
Patch10311: 0311-extcon-add-extcon-k1xci-driver-for-usb2.0-otg.patch
Patch10312: 0312-usb-otg-add-k1x-ci-otg-driver.patch
Patch10313: 0313-dtsi-k1-x-add-usb2-otg-support.patch
Patch10314: 0314-clock-add-apb-clk-enable-apb-axi-clk-when-init.patch
Patch10315: 0315-k1x-pmic-refine-the-pmic-code.patch
Patch10316: 0316-display-Support-hdmi-1080p.patch
Patch10317: 0317-clock-dead-lock-issue-may-happen.patch
Patch10318: 0318-mmc-dts-support-power-domain.patch
Patch10319: 0319-mmc-sdhci-of-k1x-add-pm_runtime_get_sync-during-prob.patch
Patch10320: 0320-pcie-Optimize-phy-initialization-code-for-k1x-pcie-d.patch
Patch10321: 0321-dts-modify-the-domain-id-of-pcie1-to-1.patch
Patch10322: 0322-k1x-pmic-support-power-key-driver.patch
Patch10323: 0323-k1x-pmic-rtc-support-spm8821-rtc-driver.patch
Patch10324: 0324-reshape-pinctrl-dtsi-and-platform-dtsi.patch
Patch10325: 0325-display-Fix-reset-control-deassert-and-assert.patch
Patch10326: 0326-clean-clk-driver-debug-info.patch
Patch10327: 0327-clean-drm-driver-debug-info.patch
Patch10328: 0328-clean-camera-driver-debug-info.patch
Patch10329: 0329-clean-dma-driver-debug-info.patch
Patch10330: 0330-clean-usb-driver-debug-info.patch
Patch10331: 0331-clean-tcm-driver-debug-info.patch
Patch10332: 0332-clean-qspi-driver-debug-info.patch
Patch10333: 0333-clean-crypto-driver-debug-info.patch
Patch10334: 0334-clean-i2c-driver-debug-info.patch
Patch10335: 0335-clean-reset-driver-debug-info.patch
Patch10336: 0336-clean-gmac-driver-debug-info.patch
Patch10337: 0337-clean-some-unused-driver-module.patch
Patch10338: 0338-add-gx09inx101-mipi-lcd-configuration.patch
Patch10339: 0339-k1x-crypto-1.handle-memleak-in-probe-2.ture-down-sel.patch
Patch10340: 0340-k1x-pmic-refactoring-code-to-support-new-dcdc.patch
Patch10341: 0341-defconfig-add-usb3.0-support-for-k1-x-evb2.patch
Patch10342: 0342-usb-misc-add-spacemit-onboard-hub-driver.patch
Patch10343: 0343-dtsi-k1-x-add-usb3.0-support.patch
Patch10344: 0344-usb-add-spacemit-k1x-dma-mask-setting.patch
Patch10345: 0345-phy-add-spacemit-pcie-usb3-combphy-driver.patch
Patch10346: 0346-spacemit-rf-add-wifi-platform-driver.patch
Patch10347: 0347-spacemit-rf-dts-enable-spacemit-rf-pwrseq.patch
Patch10348: 0348-k1x-cpuidle-support-cpu-power-down-only.patch
Patch10349: 0349-wireless-rtl8852bs-add-rtl8852bs-sdio-wifi-driver.patch
Patch10350: 0350-wifi-k1x-deb2-enable-rtl8852bs-wifi-defconfig.patch
Patch10351: 0351-k1x-cpufreq-support-adjust-the-voltage-when-the-cpu-.patch
Patch10352: 0352-display-Fix-hdmi-qos-control.patch
Patch10353: 0353-mmc-dts-alloc-index-from-alias-id.patch
Patch10354: 0354-disable-rtl8852bs-wifi-driver-there-is-too-much-warn.patch
Patch10355: 0355-update-evb-board-dts.patch
Patch10356: 0356-update-deb2-board-dts.patch
Patch10357: 0357-update-deb2-kernel-config.patch
Patch10358: 0358-sync-deb2-board-dts.patch
Patch10359: 0359-wifi-k1x-deb2-enable-aic8800dc-wifi-defconfig.patch
Patch10360: 0360-wifi-k1x-evb-enable-aic8800dc-wifi-defconfig.patch
Patch10361: 0361-audio-add-audio-driver.patch
Patch10362: 0362-dts-add-audio-snd-card-support.patch
Patch10363: 0363-enable-audio-driver-for-evb-board.patch
Patch10364: 0364-enable-audio-driver-for-deb2.patch
Patch10365: 0365-clear-compile-warning.patch
Patch10366: 0366-support-dvfs-for-evb-performance.patch
Patch10367: 0367-use-performance-governor-as-default.patch
Patch10368: 0368-audio-change-pcm-hw_params.patch
Patch10369: 0369-display-Support-kernel-logo.patch
Patch10370: 0370-display-update-kernel-logo.patch
Patch10371: 0371-disable-audio-and-adsp-driver.patch
Patch10372: 0372-disable-audio-and-adsp-driver.patch
Patch10373: 0373-display-fix-kernel-logo.patch
Patch10374: 0374-k1x-can-add-clk-reset-control-in-dma-driver.patch
Patch10375: 0375-clock-fix-can-func-clk-incorrect-issue.patch
Patch10376: 0376-reset-fix-reset-bit-of-aes.patch
Patch10377: 0377-k1x-deb1-support-deb1-project.patch
Patch10378: 0378-k1x-deb1-add-k1-x_deb1.dts-to-fix-compiling-error-wh.patch
Patch10379: 0379-k1x-pmic-support-pwr-key-rtc-pinctrl-function.patch
Patch10380: 0380-spacemit-rf-add-bluetooth-platform-driver.patch
Patch10381: 0381-wifi-k1x-deb2-enable-rtl8852bs-wifi-defconfig.patch
Patch10382: 0382-sync-board-dts-from-devices.patch
Patch10383: 0383-add-k1-universal-config-for-all-board.patch
Patch10384: 0384-fix-disable-CONFIG_INITRAMFS_SOURCE-which-may-overla.patch
Patch10385: 0385-wifi-k1x-deb1-enable-rtl8852bs-wifi-defconfig.patch
Patch10386: 0386-k1-x-crypto-speed-up-expand-single-encrypt-decrypt-s.patch
Patch10387: 0387-sync-board-dts-from-devices.patch
Patch10388: 0388-wireless-rtl8852be-add-wifi-driver.patch
Patch10389: 0389-k1x-cpu-cooling-add-the-cpuidle-cooling-function.patch
Patch10390: 0390-clock-reset-fix-pwm0-clk-reset-reg-bit.patch
Patch10391: 0391-add-cpu-model-name-showed-in-proc-cpuinfo.patch
Patch10392: 0392-k1x-adjust-i2c-driver-strength.patch
Patch10393: 0393-add-docker-required-configurations-1.-bridge-and-vla.patch
Patch10394: 0394-k1x-deb1-support-power-off-system.patch
Patch10395: 0395-display-Fix-dpu-reset-issue.patch
Patch10396: 0396-sync-board-dts-from-devices.patch
Patch10397: 0397-tools-perf-pmu-events-add-SpacemiT-X60-JSON-files.patch
Patch10398: 0398-k1x-add-zicboz-and-zicbop-to-dts.patch
Patch10399: 0399-modify-compile-optimize-from-size-to-performance.patch
Patch10400: 0400-display-disable-kernel-logo.patch
Patch10401: 0401-set-cma-alloc-range-from-0x40000000.patch
Patch10402: 0402-sync-board-dts-from-devices-configuration.patch
Patch10403: 0403-qspi-Correct-the-setting-clk-rate-of-k1x-qspi.patch
Patch10404: 0404-performance-optimize.patch
Patch10405: 0405-k1x-support-PCIE-SATA-JMB585-board.patch
Patch10406: 0406-Bluetooth-enable-bluez-stack.patch
Patch10407: 0407-uart-disable-bluesleep-hostwake-detect.patch
Patch10408: 0408-clock-uart-source-48M-and-14.7M-have-same-gate-bit-i.patch
Patch10409: 0409-k1x-uart-add-uart-parent-clk-gate-function.patch
Patch10410: 0410-sync-board-dts-with-devices.patch
Patch10411: 0411-display-Update-hdmi-phy-config.patch
Patch10412: 0412-k1-x-aes-prevent-writing-buffer-requests-in-the-mean.patch
Patch10413: 0413-k1x-aes-add-xts-cipher.patch
Patch10414: 0414-display-Support-dsi-and-hdmi-double-screens.patch
Patch10415: 0415-use-the-unified-defconfig-for-k1-5-5.patch
Patch10416: 0416-add-ramdisk-for-develop-branch.patch
Patch10417: 0417-k1-enable-usb-serial.patch
Patch10418: 0418-mmc-sdhci-of-k1x-improve-the-sd-tuning-process.patch
Patch10419: 0419-scatterlist-mask-out-GFP_DMA32-flag-when-call-kmallo.patch
Patch10420: 0420-target-alloc-scatterlist-with-GFP_DMA32-flag-on-spac.patch
Patch10421: 0421-k1-x-enable-ehci-for-deb1-and-deb2.patch
Patch10422: 0422-display-Remove-error-logs.patch
Patch10423: 0423-k1x-support-mailbox-driver.patch
Patch10424: 0424-k1x-remoteproc-support-remoteproc-driver.patch
Patch10425: 0425-k1x-rproc-launching-rcpu-during-the-system-startup-p.patch
Patch10426: 0426-k1x-defconfig-enable-mailbox-rproc-rpmsg_virtio-defc.patch
Patch10427: 0427-k1-rcpu-ipc-reserved-memory-for-rcpu-and-ipc.patch
Patch10428: 0428-k1x-adma-add-adma-driver-for-sspa.patch
Patch10429: 0429-audio-add-hdmi-audio-driver-and-remove-unused-code.patch
Patch10430: 0430-deconfig-enable-sound-support.patch
Patch10431: 0431-dts-add-hdmi-audio-config.patch
Patch10432: 0432-dts-modify-audio-config.patch
Patch10433: 0433-k1x-rporc-add-the-reference-of-mailbox-memory-region.patch
Patch10434: 0434-audio-modify-hdmi-audio-params-set-enable-ctrl-reg.patch
Patch10435: 0435-k1-support-CTP-driver.patch
Patch10436: 0436-display-Fixed-dtsi-warning.patch
Patch10437: 0437-dtb-adding-the-dts-of-linux-for-hs450-board.patch
Patch10438: 0438-k1-defconfig-enable-support-for-r8152.patch
Patch10439: 0439-disp-adjust-gpu-and-drm-initcall-sequence-for-fixed-.patch
Patch10440: 0440-gitignore-add-user_headers-generated-by-openwrt-to-g.patch
Patch10441: 0441-k1x-snd-fix-compile-warning-in-spacemit-snd-card.c.patch
Patch10442: 0442-img-rogue-fix-compile-warning.patch
Patch10443: 0443-k1x-display-fix-compile-warning.patch
Patch10444: 0444-gt9xx-fix-compile-warning.patch
Patch10445: 0445-eeprom-at24-fix-compile-warning.patch
Patch10446: 0446-k1x-hdmi-fix-compile-warning-because-of-unused-varia.patch
Patch10447: 0447-brtfs-fix-compile-warning.patch
Patch10448: 0448-sync-camera-code-from-Release-JINDIE-V3.8.patch
Patch10449: 0449-sync-camera-code-from-Release-JINDIE-V4.0.patch
Patch10450: 0450-mmc-sdhci-of-k1x-update-phy-dll-config.patch
Patch10451: 0451-aud-modify-hdmi-audio-period_size-fix-coding-issue.patch
Patch10452: 0452-k1-gpio-support-irq-controller-mode.patch
Patch10453: 0453-k1-open-hid-configs.patch
Patch10454: 0454-k1-support-touchpad-for-hs450-board.patch
Patch10455: 0455-aud-add-spi-i2s-driver.patch
Patch10456: 0456-dts-add-i2s-support.patch
Patch10457: 0457-dts-add-codec-es8326-support-i2s-pin-config.patch
Patch10458: 0458-config-enable-codec-es8326.patch
Patch10459: 0459-aud-add-es8326-sound-card-support.patch
Patch10460: 0460-k1_defconfig-enable-USB_NET_QMI_WWAN.patch
Patch10461: 0461-udma-open-failed-when-dma_dev-NULL.patch
Patch10462: 0462-k1x-dma-support-console-tx-rx-dma-mode.patch
Patch10463: 0463-dtb-adding-the-dts-of-linux-for-kx312-board.patch
Patch10464: 0464-Bluetooth-defconfig-support-hid-and-pan-profile.patch
Patch10465: 0465-gmac-Modify-gmac-pin-configuration-in-order-to-impro.patch
Patch10466: 0466-usb-misc-spacemit_onboard_hub-use-gpio-array.patch
Patch10467: 0467-dts-k1-x_kx312-enable-usbdrd3-and-usb3hub.patch
Patch10468: 0468-dtb-adding-the-dts-of-linux-for-MINI-PC-board.patch
Patch10469: 0469-add-kernel-image-itb-build-support.patch
Patch10470: 0470-perfect-camera-dts-gpio-config.patch
Patch10471: 0471-display-Fix-dpu-irqs-timeout.patch
Patch10472: 0472-k1-align-initial-state-for-audio.patch
Patch10473: 0473-k1-rpoc-using-a-RT-thread-to-process-the-virtio-msg.patch
Patch10474: 0474-k1-delete-undefined-pm-function.patch
Patch10475: 0475-dtb-adding-the-dts-of-linux-for-mingo-board.patch
Patch10476: 0476-kx312-fix-the-compile-error-that-it-can-t-find-dpu_o.patch
Patch10477: 0477-k1x-uart-fix-uart9-dts-config.patch
Patch10478: 0478-k1x-serial-fix-bug-of-pm-runtime-feature.patch
Patch10479: 0479-k1x-system_suspend-support-pmic-wakeup-source.patch
Patch10480: 0480-mmc-sdhci-of-k1x-optimize-sdcard-tuning-procedure.patch
Patch10481: 0481-k1-dts-update-dts.patch
Patch10482: 0482-vpu-update-vpu-driver-version-to-Release-JINDIE-V4.2.patch
Patch10483: 0483-v2d-mv-v2d-from-drivers-media-platform-spacemit-v2d-.patch
Patch10484: 0484-add-kernel-image-offset-configuration-which-would-be.patch
Patch10485: 0485-more-flexable-configuration-for-image-itb-build.patch
Patch10486: 0486-k1x-dts-enable-sdio-sdr104-mode.patch
Patch10487: 0487-mmc-sdhci-of-k1x-support-disable-caps.patch
Patch10488: 0488-add-compressed-gzip-kernel-itb-build.patch
Patch10489: 0489-k1-dts-disable-mipi-dsi-for-deb1.patch
Patch10490: 0490-display-Fix-dpu-irqs-error.patch
Patch10491: 0491-arch-riscv-Changed-default-target-to-Image.gz.itb-wh.patch
Patch10492: 0492-update-evb-dts.patch
Patch10493: 0493-display-add-hdmi-edid.patch
Patch10494: 0494-dts-dpu_reserved-move-dpu-reserved-memory-to-0x2ff40.patch
Patch10495: 0495-wireless-build-rtl8852be-module-into-kernel.patch
Patch10496: 0496-aud-limit-i2s-audio-params.patch
Patch10497: 0497-dts-config-codec-snd-card-support.patch
Patch10498: 0498-k1-system_suspend-enable-cpuidle-configuration-for-s.patch
Patch10499: 0499-k1-dma-add-suspend-resume-callback-for-dma-module.patch
Patch10500: 0500-display-Fix-read-hdmi-edid-data-error.patch
Patch10501: 0501-vpu-sync-Release-JINDIE-V4.3.1-on-2024-03-19-06-08.patch
Patch10502: 0502-mmc-sdhci-of-k1x-avoid-scan-sdio-during-start-host.patch
Patch10503: 0503-k1-cpufreq-fix-bug-that-the-system-do-not-update-the.patch
Patch10504: 0504-k1-cpu_cooling_device-add-the-mechanism-for-cpu-cool.patch
Patch10505: 0505-k1-cpu_cooling-add-the-function-that-hotpluging-core.patch
Patch10506: 0506-k1-thermal-enable-cpufreq-cooling-device.patch
Patch10507: 0507-mmc-sdhci-of-k1x-improve-the-tuning-window-select.patch
Patch10508: 0508-k1x-adjust-i2s-driver-strength.patch
Patch10509: 0509-dts-config-es8326-ADC-src-to-dmic.patch
Patch10510: 0510-eth-changing-the-dma-range-and-setting-dma-coherent-.patch
Patch10511: 0511-display-Fix-hdmi-read-edid-data-code-error.patch
Patch10512: 0512-phy-spacemit-k1x-combphy-get-shared-reset.patch
Patch10513: 0513-MINIPC-fix-pcie2-lane-config.patch
Patch10514: 0514-k1x-dts-update-mmc-tuning-config.patch
Patch10515: 0515-aud-fix-i2s-capture-issue.patch
Patch10516: 0516-mmc-sdhci-of-k1x-add-tx-delaycode-attr-for-sd-sdio.patch
Patch10517: 0517-leds-Support-hearbeat.patch
Patch10518: 0518-phy-k1x-ci-usb2-add-notify-callbacks-remove-unused-c.patch
Patch10519: 0519-usb-xhci-fix-spacemit-k1x-phy-disconnect-detect.patch
Patch10520: 0520-phy-spacemit-k1x-combphy-don-t-assert-when-use-share.patch
Patch10521: 0521-eth-change-the-range-of-dma-to-range1.patch
Patch10522: 0522-eth-improve-the-through-of-gmac.patch
Patch10523: 0523-display-Modify-hdmi-and-mipi-dsi-qos.patch
Patch10524: 0524-k1-kx312-add-touchpad-dts.patch
Patch10525: 0525-kx312-enable-es8326-sound-card-support.patch
Patch10526: 0526-clk-add-pll2-support-2800MHz.patch
Patch10527: 0527-eth-change-the-num-of-tx-rx-desc-buffer-to-1024-for-.patch
Patch10528: 0528-k1-sys-reboot-using-the-reset-function-of-pmic-rathe.patch
Patch10529: 0529-display-modify-mipi-dsi-dpu-bit-clock.patch
Patch10530: 0530-display-support-lt8911exb-driver.patch
Patch10531: 0531-pcie-getting-the-num-lanes-of-pcie-controller-in-phy.patch
Patch10532: 0532-pcie-change-the-dma-ranges-of-pcie-to-drma_range2.patch
Patch10533: 0533-kx312-modify-pcie1-to-1-lane.patch
Patch10534: 0534-scripts-Added-build_kernel.sh.patch
Patch10535: 0535-aud-fix-the-first-buffer-data-loss-issue.patch
Patch10536: 0536-i2s-fix-LR-channel-mapping-incorrect-issue.patch
Patch10537: 0537-usb-spacemit_onboard_hub-fix-bug-caused-by-no-delay-.patch
Patch10538: 0538-pcie-change-the-get_reset-method-of-pcie0-to-shared.patch
Patch10539: 0539-scripts-Fixed-build_kernel.sh-error.patch
Patch10540: 0540-config-enable-needed-config-checked-by-check-config..patch
Patch10541: 0541-k1x-i2c-update-i2c-driver.patch
Patch10542: 0542-display-Support-hdmi-hot-plug-detection.patch
Patch10543: 0543-display-Fix-pm-runtime-status.patch
Patch10544: 0544-dts-Enable-kx312-hdmi.patch
Patch10545: 0545-k1x-wdt-fix-timeout-setting-bug.patch
Patch10546: 0546-k1-cpufreq-cooling-refine-some-code-for-cpu-cooling.patch
Patch10547: 0547-plic-clear-irq-pending-when-init-plic.patch
Patch10548: 0548-k1-i2c-let-the-system-framework-dealing-with-suspend.patch
Patch10549: 0549-k1-spi-jion-the-pm-domain-framework-to-achieve-power.patch
Patch10550: 0550-k1-qspi-support-pm-runtime-system-suspend.patch
Patch10551: 0551-k1-rproc-support-system-suspend-callback-for-rcpu.patch
Patch10552: 0552-k1x-aes-add-aes-clk-reset-and-suspend-resume-callbac.patch
Patch10553: 0553-eth-support-suspend-and-resume-for-pm.patch
Patch10554: 0554-k1x-MINIPC-support-kernel-hdmi.patch
Patch10555: 0555-k1x-rcpu-support-suspend-resume-function-for-rcpu.patch
Patch10556: 0556-clock-add-audio-clocks.patch
Patch10557: 0557-display-Do-not-set-clock-rate-in-dts.patch
Patch10558: 0558-reset-add-audio-resets.patch
Patch10559: 0559-hdmiaudio-add-pm-runtime-and-reset.patch
Patch10560: 0560-i2s-add-pm-runtime-and-suspend-resume.patch
Patch10561: 0561-vpu-support-suspend-and-resume.patch
Patch10562: 0562-jpu-support-suspend-and-resume.patch
Patch10563: 0563-display-Fix-the-minimum-brightness-for-the-lcd.patch
Patch10564: 0564-vpu-remove-some-unuseful-log.patch
Patch10565: 0565-dtsi-k1-x-add-interconnects-to-ehci.patch
Patch10566: 0566-dts-k1-x_MINI-PC-change-usb0-mode-from-udc-to-ehci.patch
Patch10567: 0567-display-Support-no-edid-panel.patch
Patch10568: 0568-pcie-support-suspend-and-resume-for-pm.patch
Patch10569: 0569-dts-k1-x_MINI-PC-add-usb2hub-node.patch
Patch10570: 0570-k1_defconfig-enable-usb-serial-drivers-as-modules.patch
Patch10571: 0571-drm-fix-the-buffer-allocation-failed.patch
Patch10572: 0572-delete-camera-debug-code.patch
Patch10573: 0573-k1-pmic-increase-initialization-level-for-other-modu.patch
Patch10574: 0574-MINI-PC-Disable-mipi-dsi.patch
Patch10575: 0575-fix-gpu_clk-clock-setting-timeout.patch
Patch10576: 0576-k1_defconfig-change-dummy-device-default-to-module.patch
Patch10577: 0577-dts-k1-x_deb1-use-PAD_1V8_DS0-for-DVL1-and-GPIO_123.patch
Patch10578: 0578-dts-adding-module_usrload-for-loading-wifi-driver.patch
Patch10579: 0579-k1x-pinctrl-adjust-uart2-driver-strength.patch
Patch10580: 0580-usb-spacemit_onboard_hub-use-devm_gpiod_get_array_op.patch
Patch10581: 0581-swiotlb-Adjust-the-size-of-swiotlb-to-128M.patch
Patch10582: 0582-dram_range-change-the-mapping-range-for-dram_range2.patch
Patch10583: 0583-swiotlb-adjust-the-size-and-segsize-of-io-tlb.patch
Patch10584: 0584-display-Fix-card-order-for-mipi-dsi-and-hdmi.patch
Patch10585: 0585-fix-wdt-timeout-setting-use-max-timeout-if-timeout-o.patch
Patch10586: 0586-mmc-sdhci-of-k1x-add-get-aib-clk-avoid-disable-as-cl.patch
Patch10587: 0587-clock-fix-emac-ptp-clk-source.patch
Patch10588: 0588-k1x-rtc-fix-the-bug-that-setting-rtc-time-failed.patch
Patch10589: 0589-aud-support-snd-card-config-in-dts.patch
Patch10590: 0590-dts-change-hdmi-es8326-snd-card-config.patch
Patch10591: 0591-k1x-rproc-fix-bug-of-rproc-driver.patch
Patch10592: 0592-dtb-adding-the-dts-of-linux-for-MUSE-N1-board.patch
Patch10593: 0593-clear-compile-warning.patch
Patch10594: 0594-clean-compile-warning.patch
Patch10595: 0595-clean-compile-warning.patch
Patch10596: 0596-clean-compile-warning.patch
Patch10597: 0597-clear-compile-warning.patch
Patch10598: 0598-usb-ehci-k1x-ci-support-power-management.patch
Patch10599: 0599-usb-spacemit_onboard_hub-support-power-management.patch
Patch10600: 0600-display-Fix-the-issue-caused-by-alloc-pages-failed.patch
Patch10601: 0601-support-2lane-camera-to-draw-when-okay-frontsensor-n.patch
Patch10602: 0602-k1-add-kernel-dts-config-for-MUSE-Pi.patch
Patch10603: 0603-k1-rproc-fix-bug-in-system-shutdown-process.patch
Patch10604: 0604-spi-fix-the-bug-of-accessing-illegal-pointers-when-t.patch
Patch10605: 0605-clock-add-rcpu-can-clock.patch
Patch10606: 0606-reset-add-rcpu-can-reset.patch
Patch10607: 0607-k1-MUSE-Pi-update-card-detection-logic.patch
Patch10608: 0608-spi-adding-the-device-node-of-spi2-controller.patch
Patch10609: 0609-aud-fix-codec-persistent-noise-issue-when-switch-hdm.patch
Patch10610: 0610-v2d-fix-set-clock-rate-timeout.patch
Patch10611: 0611-display-fix-hdmi-compatibility-issues.patch
Patch10612: 0612-Move-GPU-alloc-page-from-DMA32-to-Normal-zone.patch
Patch10613: 0613-k1-pull-up-gpio70-71-for-SATA.patch
Patch10614: 0614-k1x-uart-check-uart-dma-function-before-release-uart.patch
Patch10615: 0615-nvme-change-the-segment-size-of-io-request-queue-for.patch
Patch10616: 0616-wirless-don-t-show-error-when-load-regulatory.db-fai.patch
Patch10617: 0617-clock-add-rcpu2-pwm-clock.patch
Patch10618: 0618-display-fix-dpu-under-run-issues.patch
Patch10619: 0619-reset-add-rcpu2-pwm-reset.patch
Patch10620: 0620-i2s-change-log-level.patch
Patch10621: 0621-display-clear-dpu-irq-and-status-after-bootlogo.patch
Patch10622: 0622-k1x-support-x60-operate-can-controller-in-rcpu.patch
Patch10623: 0623-k1x-deb1-support-rpwm2-for-fan.patch
Patch10624: 0624-dtb-k1-x_MUSE-N1-set-otg-mode-for-dwc3.patch
Patch10625: 0625-1.increase-command-line-buffer-size-to-2KB.patch
Patch10626: 0626-k1x-uart3-fix-compatible-error-in-dts.patch
Patch10627: 0627-k1x-wdt-adjust-reboot-handler-timeout.patch
Patch10628: 0628-display-add-drm-resume-and-suspend.patch
Patch10629: 0629-riscv-dts-correct-isa-string-for-Spacemit-K1.patch
Patch10630: 0630-pcie-modify-suspend_noirq-and-resume_noirq-of-k1-pci.patch
Patch10631: 0631-k1x-rtc-fix-the-issue-of-probabilistic-failure-on-se.patch
Patch10632: 0632-dtb-k1-x-update-quirks-for-usbdrd3.patch
Patch10633: 0633-k1-rtc-fix-stack-out-of-bounds-when-open-KASAN.patch
Patch10634: 0634-camera-switch-unknow-ioctl-print-level-to-warning.patch
Patch10635: 0635-Linux-Integrate-Battery-Driver.patch
Patch10636: 0636-USB-xhci-plat-fix-legacy-PHY-double-init.patch
Patch10637: 0637-display-add-hdmi-resume-and-suspend.patch
Patch10638: 0638-display-fix-hdmi-compatibility-issues.patch
Patch10639: 0639-1.change-license-statement-to-GPL-2.0-WITH-Linux-sys.patch
Patch10640: 0640-usb-k1x_udc_core-remove-req-from-queue-even-it-s-alr.patch
Patch10641: 0641-display-fix-build-warning.patch
Patch10642: 0642-display-fix-hdmi-compatibility-issues.patch
Patch10643: 0643-pcie-fix-the-compiler-warning.patch
Patch10644: 0644-aud-fix-hdmi-sound-card-create-fail-issue.patch
Patch10645: 0645-MUSE-N1-pull-down-GPIO-118-and-119-default-for-toggl.patch
Patch10646: 0646-add-reboot-mode-select-support-while-P1-reset-will-p.patch
Patch10647: 0647-aud-fix-global-out-of-bounds-when-open-KASAN.patch
Patch10648: 0648-k1x_MUSE-Pi-add-spi3-pinctrl-config.patch
Patch10649: 0649-qspi-fix-the-bug-the-actual-clk-frequency-not-equal-.patch
Patch10650: 0650-clock-remove-qspi_clk-fc-bit-setting.patch
Patch10651: 0651-rtc-fix-read-rtc-error-when-the-registers-of-pmic-ar.patch
Patch10652: 0652-k1-dts-rproc-delete-the-dma-range-property-which-wil.patch
Patch10653: 0653-pcie-modify-the-enable-phy-function-for-pcie-resume.patch
Patch10654: 0654-k1-i2c-fix-i2c-irq-mask-when-i2c-transfer-timeout.patch
Patch10655: 0655-k1-rproc-increase-initialization-level-of-rproc-driv.patch
Patch10656: 0656-pcie-supporting-the-link-enters-l2-state-when-suspen.patch
Patch10657: 0657-pcie-Add-a-timeout-to-do-while-to-prevent-an-infinit.patch
Patch10658: 0658-Linux-Separate-the-I2C-configuration-between-the-boa.patch
Patch10659: 0659-dts-enable-hdmi-sound-card-for-deb2-MINI-PC.patch
Patch10660: 0660-k1x-dma-fix-dma-tasklet-schedule-bug.patch
Patch10661: 0661-Linux-The-integration-of-the-laptop-lid-switch-drive.patch
Patch10662: 0662-display-fix-dpu-resume-and-suspend-issues.patch
Patch10663: 0663-1.change-kernel-entry-addr-to-0x20_0000.patch
Patch10664: 0664-audio-remove-SNDRV_PCM_INFO_PAUSE-support.patch
Patch10665: 0665-k1-wireless-disable-power-always-on.patch
Patch10666: 0666-display-modify-lcd-gx09inx101-pixel-clock.patch
Patch10667: 0667-gpu-fix-failed-to-import-external-image-from-highmem.patch
Patch10668: 0668-net-usb-add-asix-usb-nic-driver-ver-v3.1.0.patch
Patch10669: 0669-k1-usb-enable-parkmode_disable_ss_quirk-on-DWC3-cont.patch
Patch10670: 0670-k1-usb-update-quirks-for-usbdrd3-in-k1-x_MINI-PC.patch
Patch10671: 0671-k1-use-ax_usb_nic-instead-of-ax88179_178a.patch
Patch10672: 0672-k1-modify-sdio-rx-dline-configuration.patch
Patch10673: 0673-audio-fix-hdmiaudio-can-not-playback-after-suspend-r.patch
Patch10674: 0674-asix_usb-fix-compile-error.patch
Patch10675: 0675-do_trap_insn_illegal-bind-ai-cores-when-use-ai-instr.patch
Patch10676: 0676-k1-sync-k1-dtsi-from-linux6.1-dts.patch
Patch10677: 0677-k1-cpu-fix-compilation-errs.patch
Patch10678: 0678-k1-ccu-add-determine_rate-func.patch
Patch10679: 0679-k1-gt9xx-delete-i2c_device_id-args.patch
Patch10680: 0680-k1-camera-adjust-class_create.patch
Patch10681: 0681-k1-pmic-delect-i2c_device_id-agrs.patch
Patch10682: 0682-k1-dma-adjust-vm_flags_set-and-class_create-func.patch
Patch10683: 0683-k1-gpio-adjust-struct-gpio_chip.fwnode.patch
Patch10684: 0684-k1-usb-goto-valid-identifier.patch
Patch10685: 0685-k1-update-k1_defconfig-to-linux-6.6-bringup.patch
Patch10686: 0686-emac-change-the-function-of-adjusting-hardware-time-.patch
Patch10687: 0687-display-update-config-for-hdmi-compatibility.patch
Patch10688: 0688-display-drm-alloc-pages-from-highuser-zone.patch
Patch10689: 0689-usb-xhci-plat-read-reset-on-resume-from-device-prope.patch
Patch10690: 0690-usb-ehci-k1x-ci-support-reset-on-resume.patch
Patch10691: 0691-usb-dwc3-spacemit-add-reset-operation-at-standby-set.patch
Patch10692: 0692-k1-i2c-fix-i2c-irq-mask-when-i2c-transfer-timout.patch
Patch10693: 0693-k1-udma-add-pte_unmap-to-avoid-sleeping-function-cal.patch
Patch10694: 0694-k1-deassert-rpwm-reset-in-resume-ops.patch
Patch10695: 0695-pcie-change-the-dependence-of-PCI_K1X_HOST-to-PCI_MS.patch
Patch10696: 0696-k1-rproc-enable-rproc-module-to-avoid-bus-hangs-dead.patch
Patch10697: 0697-k1-vpu-fix-clk-warning-when-kernel-boot.patch
Patch10698: 0698-k1-jpu-fix-compile-error-on-6.6.patch
Patch10699: 0699-k1-jpu-enable-jpu.patch
Patch10700: 0700-es8326-support-hp-mic-detect-process.patch
Patch10701: 0701-sound-change-file-mode-from-0755-to-0644.patch
Patch10702: 0702-pm-rproc-adjusting-the-sleep-process-level-of-rproc.patch
Patch10703: 0703-pm-regulator-set-the-sleep-voltage-of-DCDC1-to-650mv.patch
Patch10704: 0704-rproc-do-not-automatically-load-and-start-rcpu.patch
Patch10705: 0705-k1-pm-domain-fix-error-in-deleting-qos-nodes-when-di.patch
Patch10706: 0706-k1-pm-set-the-sleep-voltage-of-DCDC1-to-650mv.patch
Patch10707: 0707-qspi-Fix-the-bug-of-data-transmission-failure-with-a.patch
Patch10708: 0708-k1_defconfig-build-cdc_ncm-as-module.patch
Patch10709: 0709-phy-k1x-ci-usb2-update-phy-init-sequence-report-erro.patch
Patch10710: 0710-usb-dwc3-spacemit-support-phy-setup.patch
Patch10711: 0711-k1-usb-setup-phy-in-dwc3-spacemit-instead-of-dwc3.patch
Patch10712: 0712-usb-xhci-add-clear-disconnect-for-spacemit-k1x-phy.patch
Patch10713: 0713-net-usb-promote-the-priority-of-ax_usb_nic-driver.patch
Patch10714: 0714-camera-fix-call_get_fmt-EINVAL-return-to-support-dra.patch
Patch10715: 0715-config-enable-kasan-to-memory-debug.patch
Patch10716: 0716-k1-ce-fix-ce-compile-errs-and-enable-ce-config.patch
Patch10717: 0717-gpu-enable-gpu-in-linux6.6.patch
Patch10718: 0718-spacemit-rf-add-missing-includes.patch
Patch10719: 0719-k1-enable-RTL8852BS-and-SPACEMIT_RFKILL.patch
Patch10720: 0720-mmc-sdhci-of-k1x-add-tuning-windows-type-configurati.patch
Patch10721: 0721-k1-change-sdio-max-clock-frequency-to-187MHz.patch
Patch10722: 0722-deconfig-enable-aes-engine-to-full-disk-encryption.patch
Patch10723: 0723-dts-modify-codec-card-name-config-and-add-mclk_fs-co.patch
Patch10724: 0724-muse-book-add-muse-book-board-dts-support.patch
Patch10725: 0725-k1-enable-USB_RTL8152.patch
Patch10726: 0726-k1-ce-fix-slab-out-of-bounds-by-KASAN-report.patch
Patch10727: 0727-display-Update-spacemit-drm-to-linux6.6.patch
Patch10728: 0728-v2d-Enable-v2d.patch
Patch10729: 0729-ax88179-change-file-mode-from-0755-to-0644.patch
Patch10730: 0730-clk-change-file-mode-from-0755-to-0644.patch
Patch10731: 0731-gmac-change-file-mode-from-0755-to-0644.patch
Patch10732: 0732-rf-change-file-mode-from-0755-to-0644.patch
Patch10733: 0733-usb-change-file-mode-from-0755-to-0644.patch
Patch10734: 0734-pinctrl-change-file-mode-from-0755-to-0644.patch
Patch10735: 0735-crypto-change-file-mode-0755-to-0644.patch
Patch10736: 0736-input-change-mode-from-0755-to-0644.patch
Patch10737: 0737-spi-change-file-mode-from-0755-to-0644.patch
Patch10738: 0738-pci-change-file-mode-from-0755-to-0644.patch
Patch10739: 0739-reset-change-file-mode-from-0755-to-0644.patch
Patch10740: 0740-adma-change-file-mode-from-0755-to-0644.patch
Patch10741: 0741-ir-chagne-file-mode-from-0755-to-0644.patch
Patch10742: 0742-pwm-change-file-mode-from-0755-to-0644.patch
Patch10743: 0743-wdt-change-file-mode-from-0755-to-0644.patch
Patch10744: 0744-reboot-change-file-mode-from-0755-to-0644.patch
Patch10745: 0745-dts-change-file-mode-from-0755-to-0644.patch
Patch10746: 0746-camera-change-file-mode-from-0755-to-0644.patch
Patch10747: 0747-k1-spm8821-enable-mask_unmask_non_inverted-property-.patch
Patch10748: 0748-dts-set-iomem-the-nomap-propertiers.patch
Patch10749: 0749-wireless-support-pcie-wifi-rtl8852be.patch
Patch10750: 0750-hdmiaudio-fix-no-sound-after-suspend-resume.patch
Patch10751: 0751-dts-change-i2s-target-rate.patch
Patch10752: 0752-clock-change-i2s-clock-parent-and-rate.patch
Patch10753: 0753-audio-add-mclk-config-flow.patch
Patch10754: 0754-dts-add-es8326-snd-card-support-for-MINI-PC.patch
Patch10755: 0755-audio-fix-audio-compile-error.patch
Patch10756: 0756-k1x-enable-audio-support.patch
Patch10757: 0757-audio-fix-i2s-audio-noise-due-to-dmabuffer-is-cached.patch
Patch10758: 0758-fix-regulator-do-not-load-the-driver-asynchronously-.patch
Patch10759: 0759-kconfig-add-config-ARCH_FORCE_MAX_ORDER-to-fix-defau.patch
Patch10760: 0760-riscv-show-reason-of-unaligned-access-speed-are-diff.patch
Patch10761: 0761-isa-modify-riscv-isa-format-definition.patch
Patch10762: 0762-deconfig-enable-CONFIG_DEBUG-to-more-debug-log.patch
Patch10763: 0763-aud-fix-i2s-pointer-pos-to-integer-multiple-of-perio.patch
Patch10764: 0764-arch-riscv-boot-dts-Fixed-MUSE-Book-model-to-M1-MUSE.patch
Patch10765: 0765-dts-add-orisetech-ota7290b-lcd-panel-1920-1200.patch
Patch10766: 0766-qspi-fix-the-warning-when-disable-the-clk-and-bus-cl.patch
Patch10767: 0767-k1x-6.6-support-flexcan-on-k1x-platform.patch
Patch10768: 0768-arch-riscv-k1_deb1-Added-pwm-fan.patch
Patch10769: 0769-dts-sync-the-k1-x_deb1-modify-to-the-k1-x_milkv-jupi.patch
Patch10770: 0770-dts-add-milkv-jupiter-board-of-M1.patch
Patch10771: 0771-dts-add-SiPEED-LPi3A-board-support.patch
Patch10772: 0772-at24-clean-compile-warning.patch
Patch10773: 0773-defconfig-update-defconfig.patch
Patch10774: 0774-defconfig-support-some-cpufreq-governor.patch
Patch10775: 0775-pm-pinctrl-support-edge-detect-wakeup-functoin.patch
Patch10776: 0776-spacemit-rf-support-wlan-irq-hostwake.patch
Patch10777: 0777-k1-modify-wlan-hostwake-to-pinctl.patch
Patch10778: 0778-deconfig-disable-kasan-debug.patch
Patch10779: 0779-k1-set-USB0-to-host-mode-for-MUSE-Book.patch
Patch10780: 0780-k1-add-wlan-hostwake-config-for-MINI-PC-and-milkv-ju.patch
Patch10781: 0781-display-fix-dsi-dphy-hs-prepare-and-hs-zero-cycle.patch
Patch10782: 0782-display-reserve-hdmi-compatibility-config-for-chips-.patch
Patch10783: 0783-display-modify-the-method-for-obtaining-hdmi-edid.patch
Patch10784: 0784-display-support-lt9711-for-mipi-dsi-to-dp.patch
Patch10785: 0785-display-remove-debug-log.patch
Patch10786: 0786-display-remove-useless-codes-and-fix-edp-driver.patch
Patch10787: 0787-display-support-dp-panel.patch
Patch10788: 0788-display-modify-edp-brightness-levels.patch
Patch10789: 0789-display-support-256-bytes-edid-data-for-hdmi.patch
Patch10790: 0790-display-detect-dp-plug-in-and-plug-out.patch
Patch10791: 0791-display-modify-the-order-of-the-backlight-for-the-lt.patch
Patch10792: 0792-display-do-not-operate-clock-during-the-pm-runtime.patch
Patch10793: 0793-display-modify-the-minimum-backlight-brightness-valu.patch
Patch10794: 0794-keep-bootloader-logo-on-and-release-backlight-first.patch
Patch10795: 0795-display-trun-off-lcd-power-domain-after-the-probe-fu.patch
Patch10796: 0796-ccu-fix-rpwm-clk-sel.patch
Patch10797: 0797-crypto-reset-and-clock-is-shared-between-crypto-engi.patch
Patch10798: 0798-efuse-add-spacemit-efuse-driver.patch
Patch10799: 0799-socinfo-add-spacemit-soc-information-driver.patch
Patch10800: 0800-dts-support-efuse-and-cpuinfo-module.patch
Patch10801: 0801-defconfig-enable-efuse-and-socinfo-module.patch
Patch10802: 0802-k1x-adjust-ddr-master-devices-dram_range.patch
Patch10803: 0803-dts-modify-pcie-bar-area-layout.patch
Patch10804: 0804-ccu-add-pll3-clk-frequency.patch
Patch10805: 0805-scripts-package-mkdebian.patch
Patch10806: 0806-efuse-add-nvmem-cells-according-to-the-dts.patch
Patch10807: 0807-dts-fix-the-error-of-cache-sets-number.patch
Patch10808: 0808-gpu-fix-workqueue-warning.patch
Patch10809: 0809-k1-support-mult-frequency-table-and-using-one-policy.patch
Patch10810: 0810-hdmiaudio-fix-no-sound-issue-on-some-hdmi-display-du.patch
Patch10811: 0811-pinctrl-fix-compile-warning.patch
Patch10812: 0812-mipi-fix-compile-warninng.patch
Patch10813: 0813-i2c-fix-warn_on-when-system-power-off.patch
Patch10814: 0814-aud-fix-can-not-play-record-issue-after-suspend-resu.patch
Patch10815: 0815-display-release-reserved-memory-for-bootlogo.patch
Patch10816: 0816-fs-enable-ubifs-jffs2-and-squashfs.patch
Patch10817: 0817-k1-thermal-separate-the-thermal-configuration-and-re.patch
Patch10818: 0818-k1x-add-MUSE-Card-dts-support.patch
Patch10819: 0819-k1x-add-MUSE-Paper-dts-support.patch
Patch10820: 0820-usb-dwc3-support-remote-wakeup.patch
Patch10821: 0821-usb-ehci-support-remote-wakeup.patch
Patch10822: 0822-usb-dwc3-enable-irqwake-in-dwc3_suspend-instead-of-s.patch
Patch10823: 0823-usb-dwc3-enable-linestate1-wakeup-mask.patch
Patch10824: 0824-usb-disable-remote-wakeup-default.patch
Patch10825: 0825-phy-k1x-ci-otg-adjust-Makefile-order.patch
Patch10826: 0826-bluetooth-use-kernel-btrtl-for-8852bu-instead-of-rtk.patch
Patch10827: 0827-phy-spacemit-k1x-combphy-add-suspend-term-quirk.patch
Patch10828: 0828-k1x-adjust-crypto-alloc-buffer-and-set-mask-turns.patch
Patch10829: 0829-riscv-dts-spacemit-fix-PCIe-lane-number-for-deb1.patch
Patch10830: 0830-pinctrl-modify-some-pins-pull-configurations.patch
Patch10831: 0831-spacemit-rf-modify-default-value-of-poweron-delay.patch
Patch10832: 0832-k1-MUSE-Pi-update-sdio-tx-delaycode.patch
Patch10833: 0833-mmc-sdhci-of-k1x-fix-cpufreq-while-execute-sw-tuning.patch
Patch10834: 0834-m1-milkv-jupiter-specify-cpufreq-during-sdio-rx-tuni.patch
Patch10835: 0835-camera-move-spacemit-bifmode-enable-from-dtsi-to-dts.patch
Patch10836: 0836-MUSE-Paper-remove-hdmiaudio-support.patch
Patch10837: 0837-k1-MUSE-Pi-update-sdio-tx-delaycode-to-0x30.patch
Patch10838: 0838-uart0-dts-add-uart-controller-configuration-for-open.patch
Patch10839: 0839-k1-cpufreq-using-the-default-vf-table-of-we-did-not-.patch
Patch10840: 0840-k1x-adjust-buck4-ldo1-7-suspend-voltage-to-0V.patch
Patch10841: 0841-k1x-MINIPC-adjust-ldo1-to-always-on-for-secjtag-TRST.patch
Patch10842: 0842-uart-clean-debug-info.patch
Patch10843: 0843-jpu-clean-debug-info.patch
Patch10844: 0844-pcie-clean-debug-info.patch
Patch10845: 0845-sound-clean-debug-info.patch
Patch10846: 0846-k1x-fix-dldo1-always-on-to-aldo1-always-on.patch
Patch10847: 0847-change-error-to-warning-when-frequency-table-is-full.patch
Patch10848: 0848-Add-support-for-ICM42607-sensor.patch
Patch10849: 0849-camera-sync-code-from-linux-6.1.patch
Patch10850: 0850-k1-pm-domain-disable-wakeup5-by-default.patch
Patch10851: 0851-k1-pm-close-some-dcdc-ldo-to-optimize-sleep-power-co.patch
Patch10852: 0852-Linux-Open-jffs2-and-squash-support.patch
Patch10853: 0853-Linux-For-the-Power-button-shutdown-add-support-for-.patch
Patch10854: 0854-To-ensure-a-better-user-experience-set-the-battery-l.patch
Patch10855: 0855-To-add-hall-sensor-support-for-Muse-Paper-report-SW_.patch
Patch10856: 0856-k1-hotplug-close-the-SCMI-configuration.patch
Patch10857: 0857-pcie-supporting-PCIe-interface-power-management.patch
Patch10858: 0858-clock-add-rcpu-i2c-clock.patch
Patch10859: 0859-reset-add-rcpu-i2c-reset.patch
Patch10860: 0860-gmac-supporting-ptp-with-hardware-timestamp.patch
Patch10861: 0861-display-modify-panel-backlight-level.patch
Patch10862: 0862-display-add-panel-notifier-event-for-spacemit.patch
Patch10863: 0863-display-add-mipi-lcd-icnl9951r.patch
Patch10864: 0864-display-support-mipi-lcd-avee-and-avdd.patch
Patch10865: 0865-display-add-resume-and-suspend-for-lt9711-driver.patch
Patch10866: 0866-k1-cpufreq-Support-dynamic-switching-of-1.6G-and-1.8.patch
Patch10867: 0867-k1-pm-domain-improve-the-detach-operation-of-the-pow.patch
Patch10868: 0868-gmac-fixed-the-bug-that-Ethernet-phy-cannot-enter-lo.patch
Patch10869: 0869-k1x-add-MUSE-Paper-mini-4g-dts-support.patch
Patch10870: 0870-clock-fix-can-not-get-correct-rate-issue.patch
Patch10871: 0871-pcie-modify-the-phy-initialization-for-pcie-controll.patch
Patch10872: 0872-k1-x_MUSE-Book-not-reset-usb-during-suspend.patch
Patch10873: 0873-k1-MUSE-Paper-update-dts-enable-usb-and-wifi.patch
Patch10874: 0874-k1-MUSE-Paper-enable-uart2-for-bluetooth.patch
Patch10875: 0875-k1-MUSE-Paper-update-card-detection-logic.patch
Patch10876: 0876-ehci-k1x-ci-fix-multiple-instance-debugfs-conflict.patch
Patch10877: 0877-mingo-change-u3-role-switch-default-mode-to-host.patch
Patch10878: 0878-spi-nor-supporting-FM25Q64AI3-spi-nor-flash.patch
Patch10879: 0879-k1x-i2c1-i2c6-apply-for-the-same-pin-delete-i2c1.patch
Patch10880: 0880-k1x-fix-crypto-buffer-data-copy-method.patch
Patch10881: 0881-dts-adding-the-power-switch-of-wifi-and-bt-on-kx312.patch
Patch10882: 0882-dts-adding-the-power-switch-of-wifi-and-bt-on-MUSE-B.patch
Patch10883: 0883-this-is-not-pcie-patch-Revert-pcie-clean-debug-info.patch
Patch10884: 0884-pcie-clean-debug-info.patch
Patch10885: 0885-pcie-fix-the-bug-that-Samsung-nvme-ssd-link-establis.patch
Patch10886: 0886-k1x-disable-watchdog.patch
Patch10887: 0887-arch-riscv-boot-dts-Enable-MUSE-Book-eeprom-by-defau.patch
Patch10888: 0888-k1-x_lpi3a.dts-change-usb2.0otg-port-to-device-mode.patch
Patch10889: 0889-k1-x_lpi3a.dts-fix-no-interrupt-of-ctp.patch
Patch10890: 0890-k1_deconfig-add-i2c-gpio-expander-PCA953X-driver.patch
Patch10891: 0891-codec-add-es7210-driver.patch
Patch10892: 0892-codec-add-es8156-driver.patch
Patch10893: 0893-dts-fix-JD9365DA-10.1-inch-lcd-cann-t-display-for-lp.patch
Patch10894: 0894-as1911-change-file-mode-to-0644.patch
Patch10895: 0895-k1-pm-rproc-put-the-de-assert-of-rproc-s-clock-into-.patch
Patch10896: 0896-dtsi-k1-add-otg1-support-add-wakeup_reg-reg.patch
Patch10897: 0897-k1x_udc_core-fix-global-variable-and-extcon.patch
Patch10898: 0898-phy-k1x-ci-otg-refactor-otg-logic-to-support-more-us.patch
Patch10899: 0899-ehci-k1x-ci-fix-otg-suspend-resume-and-pm_runtime.patch
Patch10900: 0900-k1_defconfig-enable-otg-support.patch
Patch10901: 0901-k1-milkv-jupiter-update-sdio-tx-delaycode-to-0x30.patch
Patch10902: 0902-Linux-Add-a-virtual-charger-driver.This-resolves-the.patch
Patch10903: 0903-display-fix-the-issue-of-bootlogo-flashing-screen.patch
Patch10904: 0904-gmac-set-mac_managed_pm-to-true-to-fix-mdio-resume-w.patch
Patch10905: 0905-MUSE-N1-u3-set-the-default-mode-to-host-1.so-2.5G-et.patch
Patch10906: 0906-adma-fix-compile-warning.patch
Patch10907: 0907-k1x-flexcan-do-ram-init-by-iowrite32-instead-of-mems.patch
Patch10908: 0908-thermal-add-hwmon-sysfs-node-for-some-debug-tools.patch
Patch10909: 0909-thermal-fix-compile-error-because-of-sysfs-register-.patch
Patch10910: 0910-k1x-support-cw2015-driver.patch
Patch10911: 0911-defconfig-update-kernel-default-configuration.patch
Patch10912: 0912-clock-add-rcpu-ir-uart0-uart1-ssp-clocks.patch
Patch10913: 0913-reset-add-rcpu-ir-uart0-uart1-ssp-resets.patch
Patch10914: 0914-display-fix-compile-warning.patch
Patch10915: 0915-camera-fix-compile-warning.patch
Patch10916: 0916-crypto-fix-compile-warning.patch
Patch10917: 0917-vpu-fix-compile-warning.patch
Patch10918: 0918-reset-fix-compile-warning.patch
Patch10919: 0919-cpufreq-fix-compile-warning.patch
Patch10920: 0920-spi-fix-compile-warning.patch
Patch10921: 0921-usb-fix-compiler-warning.patch
Patch10922: 0922-clock-fix-compile-warning.patch
Patch10923: 0923-gmac-fix-compiler-warning.patch
Patch10924: 0924-codec-fix-compile-warning.patch
Patch10925: 0925-k1-muse_book-support-hall-to-wakeup-system.patch
Patch10926: 0926-usb-typec-husb239-support-hynetek-husb239.patch
Patch10927: 0927-k1-defconfig-support-husb239-typec-controller.patch
Patch10928: 0928-k1x-x60-can-and-rcpu-can-separate.patch
Patch10929: 0929-k1-MUSE-Paper-support-husb239-typec-controller.patch
Patch10930: 0930-ai-fix-error-in-bind-ai-task-to-ai-core.patch
Patch10931: 0931-phy-k1x-ci-usb2-add-set_suspend-op.patch
Patch10932: 0932-phy-k1x-ci-otg-set-role-to-default-role-in-probe.patch
Patch10933: 0933-k1-x_MUSE-Pi-enable-otg1-and-set-dwc3-to-drd-mode.patch
Patch10934: 0934-k1-x_MUSE-Book-enable-otg-for-usb0.patch
Patch10935: 0935-k1x-support-rcpu-uart1-function-through-x60.patch
Patch10936: 0936-k1-i2c-support-i2c-driver-of-rcpu-domain.patch
Patch10937: 0937-spacemit_onboard_hub-add-pm-domain-support.patch
Patch10938: 0938-dwc3-spacemit-add-pm-domain-support.patch
Patch10939: 0939-dtsi-k1-update-usb-power-domain-settings.patch
Patch10940: 0940-display-fix-the-issue-while-the-i2c-communication-is.patch
Patch10941: 0941-insmod-simplify-section-header-process-for-optimize-.patch
Patch10942: 0942-k1-pinctrl-we-d-better-clean-the-edge-detect-pending.patch
Patch10943: 0943-k1x-i2c-add-one-callback-of-power-off.patch
Patch10944: 0944-k1-x_MUSE-Paper-mini-4g-camera-verify-ok.patch
Patch10945: 0945-display-add-mipi-lcd-jd9365dah3.patch
Patch10946: 0946-display-add-hdmi-notifier-event-for-spacemit.patch
Patch10947: 0947-k1-power-key-don-t-report-the-event-of-power-key-whe.patch
Patch10948: 0948-k1-MUSE-Paper-mini-4g-update-dts-enable-typec-and-wi.patch
Patch10949: 0949-usb-typec-husb239-fix-possible-NULL-pointer-derefere.patch
Patch10950: 0950-k1-serial-register-freeze-restore-callback-for-hiber.patch
Patch10951: 0951-MUSE-Paper-mini-4g-enable-codec-snd-card-support.patch
Patch10952: 0952-clear-some-boot-error-without-including-these-dtsi.patch
Patch10953: 0953-pcie-Add-request-operation-before-gpio-operation.patch
Patch10954: 0954-k1x-flexcan-fix-clock-frequency-config-and-clk-set.patch
Patch10955: 0955-arch-riscv-configs-Update-k1_defconfig.patch
Patch10956: 0956-k1x-support-rcpu-ir.patch
Patch10957: 0957-asix_usb-fix-netdev-dev_addr_shadow-not-set.patch
Patch10958: 0958-k1-MUSE-Paper-mini-4g-update-modules_usrload.patch
Patch10959: 0959-mmc-sdhci-of-k1x-use-remove_new-instead-of-remove.patch
Patch10960: 0960-phy-k1x-ci-otg-fix-shared-reset-assert-warning.patch
Patch10961: 0961-spacemit-rf-introduce-spacemit-rfkill-driver.patch
Patch10962: 0962-k1-x_MUSE-Paper-mini-4g-add-4g-module-support.patch
Patch10963: 0963-pcie-Set-the-vendor-id-and-device-id-of-k1x-pcie-rc.patch
Patch10964: 0964-qmi_wwan_f-add-fibocom-qmi-modem-driver.patch
Patch10965: 0965-k1_defconfig-enable-qmi_wwan_f-as-module.patch
Patch10966: 0966-defconfig-enable-CONFIG_MTD_CMDLINE_PARTS.patch
Patch10967: 0967-k1x-turn-on-ir-spacemit-defconfig.patch
Patch10968: 0968-sbs-charger-change-file-mode-0755-0644.patch
Patch10969: 0969-k1-cpufreq-using-on-v-f-table-to-support-k1-m1-chip.patch
Patch10970: 0970-k1-cpufreq-delete-the-boost-related-node-for-k1.patch
Patch10971: 0971-k1-thermal-using-one-thermal-table-for-both-m1-k1.patch
Patch10972: 0972-k1_defconfig-add-USB-Audio-UAC-devices-support.patch
Patch10973: 0973-k1-alsa-alsa-driver-adds-audio-data-dump.patch
Patch10974: 0974-spacemit_onboard_hub-fix-Kconfig-dependancy.patch
Patch10975: 0975-gpu-Fix-building-error-with-FORTIFY_SOURCE-enabled.patch
Patch10976: 0976-k1-thermal-fix-the-issue-where-the-frequency-cannot-.patch
Patch10977: 0977-pcie-print-MSIX_AFIFO_FULL-information-once.patch
Patch10978: 0978-deconfig-enable-spinlock_debug.patch
Patch10979: 0979-MUSE-Paper-mini-support-battery-profile.patch
Patch10980: 0980-MUSE-Paper-mini-support-some-sensor.patch
Patch10981: 0981-k1x_udc_core-fix-missing-STATUS-IN-in-control-out-tr.patch
Patch10982: 0982-k1x_udc_core-fix-enable-after-disable-may-fail.patch
Patch10983: 0983-k1x_udc_core-fix-high-bandwidth-isoc-endpoint-transf.patch
Patch10984: 0984-k1x_udc_core-cleanup-info-print.patch
Patch10985: 0985-usb-typec-husb239-support-mic-switch.patch
Patch10986: 0986-usb-typec-husb239-update-pd-contract.patch
Patch10987: 0987-display-reduce-panel-lt8911exb-resume-time.patch
Patch10988: 0988-lpi3a-add-aic8800-wifi-support.patch
Patch10989: 0989-camera-fix-unknown-type-compile-error-and-comment-sl.patch
Patch10990: 0990-spacemit-rf-use-gpiod_set_value_cansleep-instead-of-.patch
Patch10991: 0991-display-fix-the-issue-of-bootlogo-flashing-screen.patch
Patch10992: 0992-k1-pm_domain-lcd-don-t-open-the-power-switch-again-i.patch
Patch10993: 0993-camera-perfect-open-close-node-in-pinmulti-mode.patch
Patch10994: 0994-k1-update-sd-sdio-tx-delaycode.patch
Patch10995: 0995-usb-f_uvc-use-GFP_DMA32-for-vb2_queue-at-spacemit-k1.patch
Patch10996: 0996-k1x-adc-p1-supprt-adc-driver-for-k1x.patch
Patch10997: 0997-display-add-plane-cursor-type-and-support-crop.patch
Patch10998: 0998-add-baton-camera-solution.patch
Patch10999: 0999-dts-add-k1-x_FusionOne-for-eli-NAS.patch
Patch11000: 1000-k1-suspend-skip-system-sync-in-kernel.patch
Patch11001: 1001-k1x-support-touchscreen-chipone-tddi.patch
Patch11002: 1002-k1x-support-sgm41515-charger-driver.patch
Patch11003: 1003-k1-reboot-add-a-flag-indicating-whether-to-shutdown-.patch
Patch11004: 1004-MUSE-Paper-support-volume-up-dowm-key-event.patch
Patch11005: 1005-hung-task-set-hung-timeout-120s.patch
Patch11006: 1006-add-new-pinctrl-node-for-FusionOne-to-support-wifi-s.patch
Patch11007: 1007-soc-support-notifier-among-modules.patch
Patch11008: 1008-usb-typec-husb239-add-notifier-event-for-typec-heads.patch
Patch11009: 1009-cpuidle-delete-the-dts-node-for-cpuidle.patch
Patch11010: 1010-clock-add-dpll-and-ddr-clocks.patch
Patch11011: 1011-usb-typec-husb239-add-vdd-supply-and-usb2-switch.patch
Patch11012: 1012-mmc-sdhci-of-k1x-avoid-recovery-sdr104-while-dts-dis.patch
Patch11013: 1013-enable-typec-for-FusionOne.patch
Patch11014: 1014-muse-paper-sync-camera-draw-dts-configuration.patch
Patch11015: 1015-k1-dts-add-all-disabled-usb-nodes.patch
Patch11016: 1016-blk-add-request-completion-flags-for-debug.patch
Patch11017: 1017-deconfig-enable-CONFIG_LOCKDEP-for-debug.patch
Patch11018: 1018-display-fix-the-issue-of-trace-during-system-sleep-a.patch
Patch11019: 1019-sound-support-build-module.patch
Patch11020: 1020-defconfig-add-audio-config.patch
Patch11021: 1021-Bluetooth-btrtl-fix-oops-in-btrtl_vendor_read_reg16.patch
Patch11022: 1022-k1-pm_domain-fix-bug-when-device-detach-from-pm-doma.patch
Patch11023: 1023-serial-fix-lockdep_assert-warning.patch
Patch11024: 1024-nvme-expose-allocation-or-mapping-failure-reports.patch
Patch11025: 1025-Fix-dma_buf-warning-with-enabled-lockdep.patch
Patch11026: 1026-camera-Fix-dma_buf-warning-with-enabled-lockdep.patch
Patch11027: 1027-vpu-Fix-dma_buf-warning-with-enabled-lockdep.patch
Patch11028: 1028-jpu-Fix-dma_buf-warning-with-enabled-lockdep.patch
Patch11029: 1029-v2d-fix-dmabuf-warning-with-enabled-lockdep.patch
Patch11030: 1030-display-modify-the-initcall-sequence-of-the-hdmi-dri.patch
Patch11031: 1031-dts-modify-hdmiaudio-config.patch
Patch11032: 1032-sound-change-from-late_initcall_sync-to-late_initcal.patch
Patch11033: 1033-hdmiaudio-support-hot-plug.patch
Patch11034: 1034-display-adjust-resolution-to-60Hz.patch
Patch11035: 1035-ir-fix-global-out-of-bounds-when-KASAN-enable.patch
Patch11036: 1036-k1x-chipone-tddi-reduce-init-log-level.patch
Patch11037: 1037-disable-the-function-that-auto-switch-usb-mode-at-Fu.patch
Patch11038: 1038-dts-add-orangepi-rv2-solution.patch
Patch11039: 1039-orangepi-rv2-add-usb-ctl-adaptation.patch
Patch11040: 1040-k1-hall-support-separating-wake-up-interrupts-from-n.patch
Patch11041: 1041-k1-pwr-key-support-wakeup-count.patch
Patch11042: 1042-k1x-fix-xts-aes-key2-error.patch
Patch11043: 1043-mmc-sdhci-of-k1x-support-MMC1-debug-as-uart0.patch
Patch11044: 1044-k1-MUSE-Paper-add-SD-debug-pinctrl.patch
Patch11045: 1045-stacktrace-delect-KASAN-warning.patch
Patch11046: 1046-gpu-fix-slab-use-after-free-err.patch
Patch11047: 1047-k1x-support-ddr-bandwidth-tool-driver.patch
Patch11048: 1048-dts-MUSE-Pi-remove-cd-inverted-of-sdhci0.patch
Patch11049: 1049-k1x-clean-uart-useless-info.patch
Patch11050: 1050-add-ili9881c-mipi-to-orangepi-rv2.patch
Patch11051: 1051-camera-verify-camera-success.patch
Patch11052: 1052-orangepi-rv2-add-es8323-config-and-modify-sound-code.patch
Patch11053: 1053-defconfig-support-codec-es8323.patch
Patch11054: 1054-usb-typec-husb239-enable-Try.SNK-mechanism.patch
Patch11055: 1055-display-fix-mmu-configuration-error-while-tbu-id-is-.patch
Patch11056: 1056-k1x-stop-watchdog-before-the-system-suspend-and-reco.patch
Patch11057: 1057-k1x-remove-cw2015-useless-info.patch
Patch11058: 1058-k1-MUSE-Paper-fix-the-mistake-about-sd-sdio-tx-delay.patch
Patch11059: 1059-camera-sync-V5.7-code-and-verify-single_online_test.patch
Patch11060: 1060-k1x-update-MUSE-Paper-cw2015-profile.patch
Patch11061: 1061-k1x-add-ZT001H-dts-support.patch
Patch11062: 1062-vpu-Fix-circular-lock-warning-with-enabled-lockdep.patch
Patch11063: 1063-vpu-Fix-amvx-build-error-when-building-amvx-as-modul.patch
Patch11064: 1064-k1-add-fanghang-k1-x_uav-dts.patch
Patch11065: 1065-riscv-Flush-the-icache-of-all-cores-related-to-the-c.patch
Patch11066: 1066-clock-reset-add-rcpu-pwm-clocks-and-resets.patch
Patch11067: 1067-k1x-1.fix-gpio74-function2-pwm9-rpwm9-2.add-rpwm0-9-.patch
Patch11068: 1068-dts-modify-the-address-space-allocation-of-pcie2_rc.patch
Patch11069: 1069-PCI-Add-arch_can_pci_mmap_wc-macro-on-spacemit-k1-so.patch
Patch11070: 1070-k1x-support-chsc5xxx-touchpad-driver.patch
Patch11071: 1071-k1x-MUSE-Paper-mini-4g-support-charger.patch
Patch11072: 1072-k1-x_uav-camera-verify-imx415-okay.patch
Patch11073: 1073-defconfig-add-real-time-linux-defconfig.patch
Patch11074: 1074-k1_uav-enable-uart-ports.patch
Patch11075: 1075-drm-radeon-mask-MSI-on-K1x.patch
Patch11076: 1076-radeon-amdgpu-force-32-bit-dma.patch
Patch11077: 1077-Radeon-modify-cached-mapping-to-writecombine.patch
Patch11078: 1078-k1-add-radeon-module-in-k1_defconfig.patch
Patch11079: 1079-camera-Fix-isp-and-cpp-build-error-when-building-the.patch
Patch11080: 1080-defconfig-disable-LOCKDEP-config.patch
Patch11081: 1081-rt-defconfig-config-CONFIG_PREEMPT_RT.patch
Patch11082: 1082-mmc-sdhci-of-k1x-fix-bug-about-get-invalid-cpufreq_p.patch
Patch11083: 1083-dts-update-k1-x_uav-disabled-some-no-used-moduels-fi.patch
Patch11084: 1084-k1-support-decompression-of-zstd-format-file.patch
Patch11085: 1085-1.add-clk-reset-to-i2c3-2.enable-rpwm9.patch
Patch11086: 1086-cpuinfo-add-uarch-information.patch
Patch11087: 1087-k1x-clear-charger-useless-info.patch
Patch11088: 1088-es8326-support-headphone-notifier-call-chain.patch
Patch11089: 1089-es8326-fix-es8326-no-sound-due-to-data-length-settin.patch
Patch11090: 1090-es8326-fix-no-sound-issue-after-suspend-resume.patch
Patch11091: 1091-es8326-cleanup-unused-code.patch
Patch11092: 1092-es8326-reset-jack-status-when-suspend.patch
Patch11093: 1093-riscv-rwonce-add-__READ_ONCE-implementation-for-risc.patch
Patch11094: 1094-riscv-spackemit-add-of-node-get-for-process-cpuinfo-.patch
Patch11095: 1095-sound-adapt-linux-kernel-new-vision.patch
Patch11096: 1096-usb-phy-modify-prototype-of-device-remove-function.patch
Patch11097: 1097-usb-dwc3-modify-prototype-of-device-remove-function.patch
Patch11098: 1098-usb-udc-modify-prototype-of-device-remove-function.patch
Patch11099: 1099-usb-host-modify-prototype-of-device-remove-function.patch
Patch11100: 1100-usb-misc-modify-prototype-of-device-remove-function.patch
Patch11101: 1101-spi-spacemit-modify-prototype-of-device-remove-funct.patch
Patch11102: 1102-qspi-spacemit-modify-prototype-of-device-remove-func.patch
Patch11103: 1103-crypto-spacemit-replace-strlcpy-with-strscpy.patch
Patch11104: 1104-dma-spacemit-adma-modify-prototype-of-device-remove-.patch
Patch11105: 1105-dma-spacemit-modify-prototype-of-device-remove-funct.patch
Patch11106: 1106-spacemit-v2d-modify-prototype-of-device-remove-funct.patch
Patch11107: 1107-soc-spacemit-modify-prototype-of-device-remove-funct.patch
Patch11108: 1108-soc-spacemit-pm-fix-error-when-save-context-for-lowp.patch
Patch11109: 1109-spacemit-jpu-modify-prototype-of-device-remove-funct.patch
Patch11110: 1110-spacemit-ddrbw-clear-compile-warnings.patch
Patch11111: 1111-remoteproc-spacemit-modify-prototype-of-device-remov.patch
Patch11112: 1112-i2c-k1x-modify-prototype-of-device-remove-function.patch
Patch11113: 1113-plic-fix-error-on-some-offset-macro-definition.patch
Patch11114: 1114-mailbox-spacemit-modify-prototype-of-device-remove-f.patch
Patch11115: 1115-extcon-k1x-modify-prototype-of-device-remove-functio.patch
Patch11116: 1116-camera-spacemit-modify-prototype-of-device-remove-fu.patch
Patch11117: 1117-vpu-spacemit-modify-prototype-of-device-remove-funct.patch
Patch11118: 1118-ir-spacemit-modify-prototype-of-device-remove-functi.patch
Patch11119: 1119-wdt-k1x-modify-prototype-of-device-remove-function.patch
Patch11120: 1120-thermal-k1x-modify-prototype-of-device-remove-functi.patch
Patch11121: 1121-phy-combphy-clean-compile-warning-because-of-prototy.patch
Patch11122: 1122-pxa-k1x-adapt-to-linux-kernel-new-version.patch
Patch11123: 1123-power-supply-sbs-modify-prototype-of-device-remove-f.patch
Patch11124: 1124-pcie-k1x-porting-to-linux-6.12.patch
Patch11125: 1125-nvme-remove-segment-buffer-size-limit.patch
Patch11126: 1126-tcm-spacemit-modify-prototype-of-device-remove-funct.patch
Patch11127: 1127-flexcan-fix-error-in-flexcan-core-probe-function.patch
Patch11128: 1128-emac-k1x-fix-compile-warning-on-function-prototype.patch
Patch11129: 1129-stmmac-modify-prototype-of-device-remove-function.patch
Patch11130: 1130-ax88179a-porting-to-linux-6.12.patch
Patch11131: 1131-usb-qmi_wwan_f-replace-strlcpy-by-strscpy.patch
Patch11132: 1132-spi-nor-porting-fmsh-device-driver-to-linux-6.12.patch
Patch11133: 1133-drm-spacemit-porting-drm-driver-to-linux-6.12.patch
Patch11134: 1134-gpio-k1x-porting-gpio-driver-to-linux-6.12.patch
Patch11135: 1135-build-disable-character-output-display-during-the-ke.patch
Patch11136: 1136-riscv-restore-vmlinux-target-building-command.patch
Patch11137: 1137-wireless-rtl8852be-porting-to-linux-6.12.patch
Patch11138: 1138-wireless-rtl8852bs-porting-to-linux-6.12.patch
Patch11139: 1139-defconfig-disable-some-modules-which-not-ready.patch
Patch11140: 1140-k1-mainline-update-head-files-for-compile-errors.patch
Patch11141: 1141-k1-mainline-defconfig-enable-spacemit-ir-driver.patch
Patch11142: 1142-k1-mainline-defconfig-enable-codec-es8326-support.patch
Patch11143: 1143-k1-mainline-es8326-fix-es8326-compile-and-work-issue.patch
Patch11144: 1144-k1-regulator-enable-the-driver-of-regulator.patch
Patch11145: 1145-display-resolve-the-issue-of-no-display-on-HDMI.patch
Patch11146: 1146-i2c-spacemit-k1-fix-strcpy-func-in-i2c-driver.patch
Patch11147: 1147-riscv-k1-defconfig-support-i2c-driver.patch
Patch11148: 1148-plic-spacemit-k1-declare-irqchip-of-plic-riscv0.patch
Patch11149: 1149-watchdog-spacemit-k1-fix-suspend-enable-judge.patch
Patch11150: 1150-gpu-upgrade-to-24.2.patch
Patch11151: 1151-gpu-img-rogue-add-judgment-of-linux-version-and-keep.patch
Patch11152: 1152-gpu-make-sure-gpu-probe-before-display.patch
Patch11153: 1153-drm-img-rogue-porting-gpu-driver-to-linux-6.12.patch
Patch11154: 1154-gpu-img-rogue-update-to-linux-6.12-fix-pvr_drm_fops.patch
Patch11155: 1155-soc-spacemit-add-prototype-define-for-multi-modules.patch
Patch11156: 1156-clk-spacemit-clean-compile-warnings.patch
Patch11157: 1157-pinctrl-spacemit-p1-support-pmic-pins.patch
Patch11158: 1158-spi-k1-spi-porting-to-linux-6.12.patch
Patch11159: 1159-spi-k1-qspi-porting-to-linux-6.12.patch
Patch11160: 1160-dwc3-spacemit-fix-compile-warning.patch
Patch11161: 1161-usb-gadget-fix-compile-warning.patch
Patch11162: 1162-usb-xhci-hub-fix-compile-warnings.patch
Patch11163: 1163-wdt-k1-fix-compile-warning.patch
Patch11164: 1164-wireless-rtl8852bs-porting-to-linux-6.12.patch
Patch11165: 1165-cpufreq-k1-fix-compile-warning.patch
Patch11166: 1166-crypto-k1-fix-compile-warning.patch
Patch11167: 1167-usbnet-fix-compile-warning.patch
Patch11168: 1168-mmc-k1x-fix-compile-warning.patch
Patch11169: 1169-v2d-spacemit-fix-compile-warning.patch
Patch11170: 1170-power-sgm4154x-reshape-file-style.patch
Patch11171: 1171-media-k1x-vpu-porting-to-linux-6.12.patch
Patch11172: 1172-media-k1x-camera-porting-to-linux-6.12.patch
Patch11173: 1173-drm-k1x-fix-compile-warning.patch
Patch11174: 1174-drm-k1x-gpu-fix-compile-warning.patch
Patch11175: 1175-riscv-k1-kconfig-update-kernel-configuration.patch
Patch11176: 1176-media-k1-vpu-fix-error-on-MODULE_IMPORT_NS-using.patch
Patch11177: 1177-mmc-k1-fix-error-of-driver.remove.patch
Patch11178: 1178-soc-spacemit-v2d-fix-error-on-MODULE_IMPORT_NS-using.patch
Patch11179: 1179-usb-spacemit-k1-fix-compile-error.patch
Patch11180: 1180-sound-k1-fix-compile-error.patch
Patch11181: 1181-opp-k1-fix-compile-error.patch
Patch11182: 1182-can-k1-flexcan-fix-error-on-driver.remove.patch
Patch11183: 1183-wireless-rtl8852bs-porting-to-linux-6.13.patch
Patch11184: 1184-drm-img-rogue-fix-error-on-MODULE_IMPORT_NS-using.patch
Patch11185: 1185-drm-spacemit-porting-to-linux-6.13.patch
Patch11186: 1186-camera-fix-compilation-problems-and-run-imx415-in-de.patch
Patch11187: 1187-wdt-k1x-fix-MODULE_LICENSE-announce-error.patch
Patch11188: 1188-soc-k1-jpu-fix-MODULE_LICENSE-announce-error.patch
Patch11189: 1189-thermal-k1-Correct-a-typo-in-the-code.patch
Patch11190: 1190-dma-dw-axi-dmac-Correct-a-typo-in-the-code.patch
Patch11191: 1191-media-k1-camera-fix-some-compile-warnings.patch
Patch11192: 1192-riscv-k1-dts-remove-some-reserved-memory-region.patch
Patch11193: 1193-Revert-riscv-Fix-IPIs-usage-in-kfence_protect_page.patch
Patch11194: 1194-k1x_rproc-avoid-creating-busy-looping-mailbox-thread.patch
Patch11195: 1195-fix-module-dma_buf-ns.patch
Patch11196: 1196-fix-wrong-style-comments.patch
Patch11197: 1197-Remove-depends-so-PWM_PXA-can-be-enabled.patch
Patch11198: 1198-remove-trace_printk.patch
Patch11199: 1199-remove-unused-var.patch
Patch11200: 1200-Remove-depends-so-SERIAL_8250_PXA-can-be-enabled.patch
Patch11201: 1201-fix-includes-for-timestamp.patch
Patch11202: 1202-remove-debug-rdinit-from-m1-bpi.patch
Patch11203: 1203-6.14-fixes-to-spacemit_drm-and-pvr_drm.patch
Patch11204: 1204-Add-bit-brick-k1-devicetree-from-bianbu.patch
Patch11205: 1205-Add-minimal-hacked-up-OrangePI-RV2-devicetree.patch
Patch11206: 1206-6.15-fixes.patch
Patch11207: 1207-Add-distinct-compatibles-for-boards-currently-used-f.patch
Patch11208: 1208-fix-build-issue-k1x_cpp.c-1453-18-error-expected-or-.patch
Patch11209: 1209-fix-issue-https-github.com-jmontleon-linux-bianbu-is.patch
Patch11210: 1210-RTL8852-6.15-fixes.patch
Patch11211: 1211-Add-minimal-hacked-up-OrangePi-R2S-devicetree.patch





%endif

# empty final patch to facilitate testing of kernel patches
Patch999999: linux-kernel-test.patch

# END OF PATCH DEFINITIONS

%description
The kernel meta package

#
# This macro does requires, provides, conflicts, obsoletes for a kernel package.
#	%%kernel_reqprovconf [-o] <subpackage>
# It uses any kernel_<subpackage>_conflicts and kernel_<subpackage>_obsoletes
# macros defined above.
#
%define kernel_reqprovconf(o) \
%if %{-o:0}%{!-o:1}\
Provides: kernel = %{specversion}-%{pkg_release}\
%endif\
Provides: kernel-%{_target_cpu} = %{specrpmversion}-%{pkg_release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires(pre): %{kernel_prereq}\
Requires(pre): %{initrd_prereq}\
Requires(pre): ((linux-firmware >= 20150904-56.git6ebf5d57) if linux-firmware)\
Recommends: linux-firmware\
Requires(preun): systemd >= 200\
Conflicts: xfsprogs < 4.3.0-1\
Conflicts: xorg-x11-drv-vmmouse < 13.0.99\
%{expand:%%{?kernel%{?1:_%{1}}_conflicts:Conflicts: %%{kernel%{?1:_%{1}}_conflicts}}}\
%{expand:%%{?kernel%{?1:_%{1}}_obsoletes:Obsoletes: %%{kernel%{?1:_%{1}}_obsoletes}}}\
%{expand:%%{?kernel%{?1:_%{1}}_provides:Provides: %%{kernel%{?1:_%{1}}_provides}}}\
# We can't let RPM do the dependencies automatic because it'll then pick up\
# a correct but undesirable perl dependency from the module headers which\
# isn't required for the kernel proper to function\
AutoReq: no\
AutoProv: yes\
%{nil}


%package doc
Summary: Various documentation bits found in the kernel source
Group: Documentation
%description doc
This package contains documentation files from the kernel
source. Various bits of information about the Linux kernel and the
device drivers shipped with it are documented in these files.

You'll want to install this package if you need a reference to the
options that can be passed to Linux kernel modules at load time.


%package headers
Summary: Header files for the Linux kernel for use by glibc
Obsoletes: glibc-kernheaders < 3.0-46
Provides: glibc-kernheaders = 3.0-46
%if 0%{?gemini}
Provides: kernel-headers = %{specversion}-%{release}
Obsoletes: kernel-headers < %{specversion}
%endif
%description headers
Kernel-headers includes the C header files that specify the interface
between the Linux kernel and userspace libraries and programs.  The
header files define structures and constants that are needed for
building most standard programs and are also needed for rebuilding the
glibc package.

%package cross-headers
Summary: Header files for the Linux kernel for use by cross-glibc
%if 0%{?gemini}
Provides: kernel-cross-headers = %{specversion}-%{release}
Obsoletes: kernel-cross-headers < %{specversion}
%endif
%description cross-headers
Kernel-cross-headers includes the C header files that specify the interface
between the Linux kernel and userspace libraries and programs.  The
header files define structures and constants that are needed for
building most standard programs and are also needed for rebuilding the
cross-glibc package.

%package debuginfo-common-%{_target_cpu}
Summary: Kernel source files used by %{name}-debuginfo packages
Provides: installonlypkg(kernel)
%description debuginfo-common-%{_target_cpu}
This package is required by %{name}-debuginfo subpackages.
It provides the kernel source files common to all builds.

%if %{with_perf}
%package -n perf
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Performance monitoring for the Linux kernel
Requires: bzip2
%description -n perf
This package contains the perf tool, which enables performance monitoring
of the Linux kernel.

%package -n perf-debuginfo
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Debug information for package perf
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}
AutoReqProv: no
%description -n perf-debuginfo
This package provides debug information for the perf package.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_bindir}/perf(\.debug)?|.*%%{_libexecdir}/perf-core/.*|.*%%{_libdir}/libperf-jvmti.so(\.debug)?|XXX' -o perf-debuginfo.list}

%package -n python3-perf
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Python bindings for apps which will manipulate perf events
%description -n python3-perf
The python3-perf package contains a module that permits applications
written in the Python programming language to use the interface
to manipulate perf events.

%package -n python3-perf-debuginfo
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Debug information for package perf python bindings
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}
AutoReqProv: no
%description -n python3-perf-debuginfo
This package provides debug information for the perf python bindings.

# the python_sitearch macro should already be defined from above
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{python3_sitearch}/perf.*so(\.debug)?|XXX' -o python3-perf-debuginfo.list}

# with_perf
%endif

%if %{with_libperf}
%package -n libperf
Summary: The perf library from kernel source
%description -n libperf
This package contains the kernel source perf library.

%package -n libperf-devel
Summary: Developement files for the perf library from kernel source
Requires: libperf = %{version}-%{release}
%description -n libperf-devel
This package includes libraries and header files needed for development
of applications which use perf library from kernel source.

%package -n libperf-debuginfo
Summary: Debug information for package libperf
Group: Development/Debug
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{version}-%{release}
AutoReqProv: no
%description -n libperf-debuginfo
This package provides debug information for the libperf package.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_libdir}/libperf.so.*(\.debug)?|XXX' -o libperf-debuginfo.list}
# with_libperf
%endif

%if %{with_tools}
%package -n %{package_name}-tools
Summary: Assortment of tools for the Linux kernel
%ifarch %{cpupowerarchs}
Provides:  cpupowerutils = 1:009-0.6.p1
Obsoletes: cpupowerutils < 1:009-0.6.p1
Provides:  cpufreq-utils = 1:009-0.6.p1
Provides:  cpufrequtils = 1:009-0.6.p1
Obsoletes: cpufreq-utils < 1:009-0.6.p1
Obsoletes: cpufrequtils < 1:009-0.6.p1
Obsoletes: cpuspeed < 1:1.5-16
Requires: %{package_name}-tools-libs = %{specrpmversion}-%{release}
%endif
%define __requires_exclude ^%{_bindir}/python
%description -n %{package_name}-tools
This package contains the tools/ directory from the kernel source
and the supporting documentation.

%package -n %{package_name}-tools-libs
Summary: Libraries for the kernels-tools
%description -n %{package_name}-tools-libs
This package contains the libraries built from the tools/ directory
from the kernel source.

%package -n %{package_name}-tools-libs-devel
Summary: Assortment of tools for the Linux kernel
Requires: %{package_name}-tools = %{version}-%{release}
%ifarch %{cpupowerarchs}
Provides:  cpupowerutils-devel = 1:009-0.6.p1
Obsoletes: cpupowerutils-devel < 1:009-0.6.p1
%endif
Requires: %{package_name}-tools-libs = %{version}-%{release}
Provides: %{package_name}-tools-devel
%description -n %{package_name}-tools-libs-devel
This package contains the development files for the tools/ directory from
the kernel source.

%package -n %{package_name}-tools-debuginfo
Summary: Debug information for package %{package_name}-tools
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{version}-%{release}
AutoReqProv: no
%description -n %{package_name}-tools-debuginfo
This package provides debug information for package %{package_name}-tools.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_bindir}/bootconfig(\.debug)?|.*%%{_bindir}/centrino-decode(\.debug)?|.*%%{_bindir}/powernow-k8-decode(\.debug)?|.*%%{_bindir}/cpupower(\.debug)?|.*%%{_libdir}/libcpupower.*|.*%%{_bindir}/turbostat(\.debug)?|.*%%{_bindir}/x86_energy_perf_policy(\.debug)?|.*%%{_bindir}/tmon(\.debug)?|.*%%{_bindir}/lsgpio(\.debug)?|.*%%{_bindir}/gpio-hammer(\.debug)?|.*%%{_bindir}/gpio-event-mon(\.debug)?|.*%%{_bindir}/gpio-watch(\.debug)?|.*%%{_bindir}/iio_event_monitor(\.debug)?|.*%%{_bindir}/iio_generic_buffer(\.debug)?|.*%%{_bindir}/lsiio(\.debug)?|.*%%{_bindir}/intel-speed-select(\.debug)?|.*%%{_bindir}/page_owner_sort(\.debug)?|.*%%{_bindir}/slabinfo(\.debug)?|.*%%{_sbindir}/intel_sdsi(\.debug)?|XXX' -o %{package_name}-tools-debuginfo.list}

%package -n rtla
%if 0%{gemini}
Epoch: %{gemini}
%endif
Summary: Real-Time Linux Analysis tools
Requires: libtraceevent
Requires: libtracefs
Requires: libbpf
%ifarch %{cpupowerarchs}
Requires: %{package_name}-tools-libs = %{version}-%{release}
%endif
%description -n rtla
The rtla meta-tool includes a set of commands that aims to analyze
the real-time properties of Linux. Instead of testing Linux as a black box,
rtla leverages kernel tracing capabilities to provide precise information
about the properties and root causes of unexpected results.

%package -n rv
Summary: RV: Runtime Verification
%description -n rv
Runtime Verification (RV) is a lightweight (yet rigorous) method that
complements classical exhaustive verification techniques (such as model
checking and theorem proving) with a more practical approach for
complex systems.
The rv tool is the interface for a collection of monitors that aim
analysing the logical and timing behavior of Linux.

# with_tools
%endif

%if %{with_selftests}

%package selftests-internal
Summary: Kernel samples and selftests
Requires: binutils, bpftool, fuse-libs, iproute-tc, iputils, keyutils, nmap-ncat, python3
%description selftests-internal
Kernel sample programs and selftests.

# Note that this pattern only works right to match the .build-id
# symlinks because of the trailing nonmatching alternation and
# the leading .*, because of find-debuginfo.sh's buggy handling
# of matching the pattern against the symlinks file.
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} -p '.*%%{_libexecdir}/(ksamples|kselftests)/.*|XXX' -o selftests-debuginfo.list}

%define __requires_exclude ^liburandom_read.so.*$

# with_selftests
%endif

%define kernel_gcov_package() \
%package %{?1:%{1}-}gcov\
Summary: gcov graph and source files for coverage data collection.\
%description %{?1:%{1}-}gcov\
%{?1:%{1}-}gcov includes the gcov graph and source files for gcov coverage collection.\
%{nil}

%package -n %{package_name}-abi-stablelists
Summary: The Red Hat Enterprise Linux kernel ABI symbol stablelists
AutoReqProv: no
%description -n %{package_name}-abi-stablelists
The kABI package contains information pertaining to the Red Hat Enterprise
Linux kernel ABI, including lists of kernel symbols that are needed by
external Linux kernel modules, and a yum plugin to aid enforcement.

%if %{with_kabidw_base}
%package kernel-kabidw-base-internal
Summary: The baseline dataset for kABI verification using DWARF data
Group: System Environment/Kernel
AutoReqProv: no
%description kernel-kabidw-base-internal
The package contains data describing the current ABI of the Red Hat Enterprise
Linux kernel, suitable for the kabi-dw tool.
%endif

#
# This macro creates a kernel-<subpackage>-debuginfo package.
#	%%kernel_debuginfo_package <subpackage>
#
# Explanation of the find_debuginfo_opts: We build multiple kernels (debug,
# rt, 64k etc.) so the regex filters those kernels appropriately. We also
# have to package several binaries as part of kernel-devel but getting
# unique build-ids is tricky for these userspace binaries. We don't really
# care about debugging those so we just filter those out and remove it.
%define kernel_debuginfo_package() \
%package %{?1:%{1}-}debuginfo\
Summary: Debug information for package %{name}%{?1:-%{1}}\
Requires: %{name}-debuginfo-common-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: %{name}%{?1:-%{1}}-debuginfo-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: installonlypkg(kernel)\
AutoReqProv: no\
%description %{?1:%{1}-}debuginfo\
This package provides debug information for package %{name}%{?1:-%{1}}.\
This is required to use SystemTap with %{name}%{?1:-%{1}}-%{KVERREL}.\
%{expand:%%global _find_debuginfo_opts %{?_find_debuginfo_opts} --keep-section '.BTF' -p '.*\/usr\/src\/kernels/.*|XXX' -o ignored-debuginfo.list -p '/.*/%%{KVERREL_RE}%{?1:[+]%{1}}/.*|/.*%%{KVERREL_RE}%{?1:\+%{1}}(\.debug)?' -o debuginfo%{?1}.list}\
%{nil}

#
# This macro creates a kernel-<subpackage>-devel package.
#	%%kernel_devel_package [-m] <subpackage> <pretty-name>
#
%define kernel_devel_package(m) \
%package %{?1:%{1}-}devel\
Summary: Development package for building kernel modules to match the %{?2:%{2} }kernel\
Provides: kernel%{?1:-%{1}}-devel-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel-devel-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-devel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel)\
AutoReqProv: no\
Requires(pre): findutils\
Requires: findutils\
Requires: perl-interpreter\
Requires: openssl-devel\
Requires: elfutils-libelf-devel\
Requires: bison\
Requires: flex\
Requires: make\
Requires: gcc\
%if %{-m:1}%{!-m:0}\
Requires: kernel-devel-uname-r = %{KVERREL}%{uname_variant %{?1:%{1}}}\
%endif\
%description %{?1:%{1}-}devel\
This package provides kernel headers and makefiles sufficient to build modules\
against the %{?2:%{2} }kernel package.\
%{nil}

#
# This macro creates an empty kernel-<subpackage>-devel-matched package that
# requires both the core and devel packages locked on the same version.
#	%%kernel_devel_matched_package [-m] <subpackage> <pretty-name>
#
%define kernel_devel_matched_package(m) \
%package %{?1:%{1}-}devel-matched\
Summary: Meta package to install matching core and devel packages for a given %{?2:%{2} }kernel\
Requires: %{package_name}%{?1:-%{1}}-devel = %{specrpmversion}-%{release}\
Requires: %{package_name}%{?1:-%{1}}-core = %{specrpmversion}-%{release}\
%description %{?1:%{1}-}devel-matched\
This meta package is used to install matching core and devel packages for a given %{?2:%{2} }kernel.\
%{nil}

%define kernel_modules_extra_matched_package(m) \
%package modules-extra-matched\
Summary: Meta package which requires modules-extra to be installed for all kernels.\
%description modules-extra-matched\
This meta package provides a single reference that other packages can Require to have modules-extra installed for all kernels.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-internal package.
#	%%kernel_modules_internal_package <subpackage> <pretty-name>
#
%define kernel_modules_internal_package() \
%package %{?1:%{1}-}modules-internal\
Summary: Extra kernel modules to match the %{?2:%{2} }kernel\
Group: System Environment/Kernel\
Provides: kernel%{?1:-%{1}}-modules-internal-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel%{?1:-%{1}}-modules-internal-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel%{?1:-%{1}}-modules-internal = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-internal-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-internal\
This package provides kernel modules for the %{?2:%{2} }kernel package for Red Hat internal usage.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-extra package.
#	%%kernel_modules_extra_package [-m] <subpackage> <pretty-name>
#
%define kernel_modules_extra_package(m) \
%package %{?1:%{1}-}modules-extra\
Summary: Extra kernel modules to match the %{?2:%{2} }kernel\
Provides: kernel%{?1:-%{1}}-modules-extra-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel%{?1:-%{1}}-modules-extra-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel%{?1:-%{1}}-modules-extra = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-extra-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
%if %{-m:1}%{!-m:0}\
Requires: kernel-modules-extra-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-extra\
This package provides less commonly used kernel modules for the %{?2:%{2} }kernel package.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules package.
#	%%kernel_modules_package [-m] <subpackage> <pretty-name>
#
%define kernel_modules_package(m) \
%package %{?1:%{1}-}modules\
Summary: kernel modules to match the %{?2:%{2}-}core kernel\
Provides: kernel%{?1:-%{1}}-modules-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel-modules-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-modules = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
%if %{-m:1}%{!-m:0}\
Requires: kernel-modules-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules\
This package provides commonly used kernel modules for the %{?2:%{2}-}core kernel package.\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-core package.
#	%%kernel_modules_core_package [-m] <subpackage> <pretty-name>
#
%define kernel_modules_core_package(m) \
%package %{?1:%{1}-}modules-core\
Summary: Core kernel modules to match the %{?2:%{2}-}core kernel\
Provides: kernel%{?1:-%{1}}-modules-core-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel-modules-core-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel-modules-core = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
%if %{-m:1}%{!-m:0}\
Requires: kernel-modules-core-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-core\
This package provides essential kernel modules for the %{?2:%{2}-}core kernel package.\
%{nil}

#
# this macro creates a kernel-<subpackage> meta package.
#	%%kernel_meta_package <subpackage>
#
%define kernel_meta_package() \
%package %{1}\
summary: kernel meta-package for the %{1} kernel\
Requires: kernel-%{1}-core-uname-r = %{KVERREL}%{uname_suffix %{1}}\
Requires: kernel-%{1}-modules-uname-r = %{KVERREL}%{uname_suffix %{1}}\
Requires: kernel-%{1}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{1}}\
Requires: ((kernel-%{1}-modules-extra-uname-r = %{KVERREL}%{uname_suffix %{1}}) if kernel-modules-extra-matched)\
%if "%{1}" == "rt" || "%{1}" == "rt-debug" || "%{1}" == "rt-64k" || "%{1}" == "rt-64k-debug"\
Requires: realtime-setup\
%endif\
Provides: installonlypkg(kernel)\
%description %{1}\
The meta-package for the %{1} kernel\
%{nil}

#
# This macro creates a kernel-<subpackage> and its -devel and -debuginfo too.
#	%%define variant_summary The Linux kernel compiled for <configuration>
#	%%kernel_variant_package [-n <pretty-name>] [-m] [-o] <subpackage>
#
%define kernel_variant_package(n:mo) \
%package %{?1:%{1}-}core\
Summary: %{variant_summary}\
Provides: kernel-%{?1:%{1}-}core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel)\
%if %{-m:1}%{!-m:0}\
Requires: kernel-core-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
Requires: kernel-%{?1:%{1}-}-modules-core-uname-r = %{KVERREL}%{uname_variant %{?1:+%{1}}}\
%endif\
%{expand:%%kernel_reqprovconf %{?1:%{1}} %{-o:%{-o}}}\
%if %{?1:1} %{!?1:0} \
%{expand:%%kernel_meta_package %{?1:%{1}}}\
%endif\
%{expand:%%kernel_devel_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_devel_matched_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_modules_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_modules_core_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%{expand:%%kernel_modules_extra_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}} %{-m:%{-m}}}\
%if %{-m:0}%{!-m:1}\
%{expand:%%kernel_modules_internal_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}}}\
%if 0%{!?fedora:1}\
%{expand:%%kernel_modules_partner_package %{?1:%{1}} %{!?{-n}:%{1}}%{?{-n}:%{-n*}}}\
%endif\
%{expand:%%kernel_debuginfo_package %{?1:%{1}}}\
%endif\
%if %{with_efiuki} && ("%{1}" != "rt" && "%{1}" != "rt-debug" && "%{1}" != "rt-64k" && "%{1}" != "rt-64k-debug")\
%package %{?1:%{1}-}uki-virt\
Summary: %{variant_summary} unified kernel image for virtual machines\
Provides: installonlypkg(kernel)\
Provides: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires(pre): %{kernel_prereq}\
Requires(pre): systemd >= 254-1\
Recommends: uki-direct\
%package %{?1:%{1}-}uki-virt-addons\
Summary: %{variant_summary} unified kernel image addons for virtual machines\
Provides: installonlypkg(kernel)\
Requires: kernel%{?1:-%{1}}-uki-virt = %{specrpmversion}-%{release}\
Requires(pre): systemd >= 254-1\
%endif\
%if %{with_gcov}\
%{expand:%%kernel_gcov_package %{?1:%{1}}}\
%endif\
%{nil}

#
# This macro creates a kernel-<subpackage>-modules-partner package.
#	%%kernel_modules_partner_package <subpackage> <pretty-name>
#
%define kernel_modules_partner_package() \
%package %{?1:%{1}-}modules-partner\
Summary: Extra kernel modules to match the %{?2:%{2} }kernel\
Group: System Environment/Kernel\
Provides: kernel%{?1:-%{1}}-modules-partner-%{_target_cpu} = %{specrpmversion}-%{release}\
Provides: kernel%{?1:-%{1}}-modules-partner-%{_target_cpu} = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: kernel%{?1:-%{1}}-modules-partner = %{specrpmversion}-%{release}%{uname_suffix %{?1:+%{1}}}\
Provides: installonlypkg(kernel-module)\
Provides: kernel%{?1:-%{1}}-modules-partner-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
Requires: kernel%{?1:-%{1}}-modules-core-uname-r = %{KVERREL}%{uname_suffix %{?1:+%{1}}}\
AutoReq: no\
AutoProv: yes\
%description %{?1:%{1}-}modules-partner\
This package provides kernel modules for the %{?2:%{2} }kernel package for Red Hat partners usage.\
%{nil}

# Now, each variant package.
%if %{with_zfcpdump}
%define variant_summary The Linux kernel compiled for zfcpdump usage
%kernel_variant_package -o zfcpdump
%description zfcpdump-core
The kernel package contains the Linux kernel (vmlinuz) for use by the
zfcpdump infrastructure.
# with_zfcpdump
%endif

%if %{with_arm64_16k_base}
%define variant_summary The Linux kernel compiled for 16k pagesize usage
%kernel_variant_package 16k
%description 16k-core
The kernel package contains a variant of the ARM64 Linux kernel using
a 16K page size.
%endif

%if %{with_arm64_16k} && %{with_debug}
%define variant_summary The Linux kernel compiled with extra debugging enabled
%if !%{debugbuildsenabled}
%kernel_variant_package -m 16k-debug
%else
%kernel_variant_package 16k-debug
%endif
%description 16k-debug-core
The debug kernel package contains a variant of the ARM64 Linux kernel using
a 16K page size.
This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_arm64_64k_base}
%define variant_summary The Linux kernel compiled for 64k pagesize usage
%kernel_variant_package 64k
%description 64k-core
The kernel package contains a variant of the ARM64 Linux kernel using
a 64K page size.
%endif

%if %{with_arm64_64k} && %{with_debug}
%define variant_summary The Linux kernel compiled with extra debugging enabled
%if !%{debugbuildsenabled}
%kernel_variant_package -m 64k-debug
%else
%kernel_variant_package 64k-debug
%endif
%description 64k-debug-core
The debug kernel package contains a variant of the ARM64 Linux kernel using
a 64K page size.
This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_debug} && %{with_realtime}
%define variant_summary The Linux PREEMPT_RT kernel compiled with extra debugging enabled
%kernel_variant_package rt-debug
%description rt-debug-core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system:  memory allocation, process allocation, device
input and output, etc.

This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_realtime_base}
%define variant_summary The Linux kernel compiled with PREEMPT_RT enabled
%kernel_variant_package rt
%description rt-core
This package includes a version of the Linux kernel compiled with the
PREEMPT_RT real-time preemption support
%endif

%if %{with_realtime_arm64_64k_base}
%define variant_summary The Linux PREEMPT_RT kernel compiled for 64k pagesize usage
%kernel_variant_package rt-64k
%description rt-64k-core
The kernel package contains a variant of the ARM64 Linux PREEMPT_RT kernel using
a 64K page size.
%endif

%if %{with_realtime_arm64_64k} && %{with_debug}
%define variant_summary The Linux PREEMPT_RT kernel compiled with extra debugging enabled
%if !%{debugbuildsenabled}
%kernel_variant_package -m rt-64k-debug
%else
%kernel_variant_package rt-64k-debug
%endif
%description rt-64k-debug-core
The debug kernel package contains a variant of the ARM64 Linux PREEMPT_RT kernel using
a 64K page size.
This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_debug} && %{with_automotive}
%define variant_summary The Linux Automotive kernel compiled with extra debugging enabled
%kernel_variant_package automotive-debug
%description automotive-debug-core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system:  memory allocation, process allocation, device
input and output, etc.

This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_automotive_base}
%define variant_summary The Linux kernel compiled with PREEMPT_RT enabled
%kernel_variant_package automotive
%description automotive-core
This package includes a version of the Linux kernel compiled with the
PREEMPT_RT real-time preemption support, targeted for Automotive platforms
%endif

%if %{with_up} && %{with_debug}
%if !%{debugbuildsenabled}
%kernel_variant_package -m debug
%else
%kernel_variant_package debug
%endif
%description debug-core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system:  memory allocation, process allocation, device
input and output, etc.

This variant of the kernel has numerous debugging options enabled.
It should only be installed when trying to gather additional information
on kernel bugs, as some of these options impact performance noticably.
%endif

%if %{with_up_base}
# And finally the main -core package

%define variant_summary The Linux kernel
%kernel_variant_package
%description core
The kernel package contains the Linux kernel (vmlinuz), the core of any
Linux operating system.  The kernel handles the basic functions
of the operating system: memory allocation, process allocation, device
input and output, etc.
%endif

%if %{with_up} && %{with_debug} && %{with_efiuki}
%description debug-uki-virt
Prebuilt debug unified kernel image for virtual machines.

%description debug-uki-virt-addons
Prebuilt debug unified kernel image addons for virtual machines.
%endif

%if %{with_up_base} && %{with_efiuki}
%description uki-virt
Prebuilt default unified kernel image for virtual machines.

%description uki-virt-addons
Prebuilt default unified kernel image addons for virtual machines.
%endif

%if %{with_arm64_16k} && %{with_debug} && %{with_efiuki}
%description 16k-debug-uki-virt
Prebuilt 16k debug unified kernel image for virtual machines.

%description 16k-debug-uki-virt-addons
Prebuilt 16k debug unified kernel image addons for virtual machines.
%endif

%if %{with_arm64_16k_base} && %{with_efiuki}
%description 16k-uki-virt
Prebuilt 16k unified kernel image for virtual machines.

%description 16k-uki-virt-addons
Prebuilt 16k unified kernel image addons for virtual machines.
%endif

%if %{with_arm64_64k} && %{with_debug} && %{with_efiuki}
%description 64k-debug-uki-virt
Prebuilt 64k debug unified kernel image for virtual machines.

%description 64k-debug-uki-virt-addons
Prebuilt 64k debug unified kernel image addons for virtual machines.
%endif

%if %{with_arm64_64k_base} && %{with_efiuki}
%description 64k-uki-virt
Prebuilt 64k unified kernel image for virtual machines.

%description 64k-uki-virt-addons
Prebuilt 64k unified kernel image addons for virtual machines.
%endif

%kernel_modules_extra_matched_package

%define log_msg() \
	{ set +x; } 2>/dev/null \
	_log_msglineno=$(grep -n %{*} %{_specdir}/${RPM_PACKAGE_NAME}.spec | grep log_msg | cut -d":" -f1) \
	echo "kernel.spec:${_log_msglineno}: %{*}" \
	set -x

%prep
%{log_msg "Start of prep stage"}

%{log_msg "Sanity checks"}

# do a few sanity-checks for --with *only builds
%if %{with_baseonly}
%if !%{with_up}
%{log_msg "Cannot build --with baseonly, up build is disabled"}
exit 1
%endif
%endif

# more sanity checking; do it quietly
if [ "%{patches}" != "%%{patches}" ] ; then
  for patch in %{patches} ; do
    if [ ! -f $patch ] ; then
	%{log_msg "ERROR: Patch  ${patch##/*/}  listed in specfile but is missing"}
      exit 1
    fi
  done
fi 2>/dev/null

patch_command='git --work-tree=. apply'
ApplyPatch()
{
  local patch=$1
  shift
  if [ ! -f $RPM_SOURCE_DIR/$patch ]; then
    exit 1
  fi
  if ! grep -E "^Patch[0-9]+: $patch\$" %{_specdir}/${RPM_PACKAGE_NAME}.spec ; then
    if [ "${patch:0:8}" != "patch-%{kversion}." ] ; then
	%{log_msg "ERROR: Patch  $patch  not listed as a source patch in specfile"}
      exit 1
    fi
  fi 2>/dev/null
  case "$patch" in
  *.bz2) bunzip2 < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *.gz)  gunzip  < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *.xz)  unxz    < "$RPM_SOURCE_DIR/$patch" | $patch_command ${1+"$@"} ;;
  *) $patch_command ${1+"$@"} < "$RPM_SOURCE_DIR/$patch" ;;
  esac
}

# don't apply patch if it's empty
ApplyOptionalPatch()
{
  local patch=$1
  shift
  %{log_msg "ApplyOptionalPatch: $1"}
  if [ ! -f $RPM_SOURCE_DIR/$patch ]; then
    exit 1
  fi
  local C=$(wc -l $RPM_SOURCE_DIR/$patch | awk '{print $1}')
  if [ "$C" -gt 9 ]; then
    ApplyPatch $patch ${1+"$@"}
  fi
}

%{log_msg "Untar kernel tarball"}
%setup -q -n kernel-%{tarfile_release} -c
mv linux-%{tarfile_release} linux-%{KVERREL}

cd linux-%{KVERREL}
cp -a %{SOURCE1} .

%{log_msg "Start of patch applications"}
%if !%{nopatches}

ApplyOptionalPatch patch-%{patchversion}-redhat.patch





ApplyOptionalPatch 0001-add-k1-pro-base-platform-support.patch
ApplyOptionalPatch 0002-media-support-a-new-vpu-driver-which-use-V4L2-standa.patch
ApplyOptionalPatch 0003-add-SOC_SPACEMIT_K1-for-spacemit-k1-serial-SOCs.patch
ApplyOptionalPatch 0004-update-kernel-configuration-for-qemu-board.patch
ApplyOptionalPatch 0005-kernel-config-add-SOC_SPACEMIT_K1_FPGA-option-for-fp.patch
ApplyOptionalPatch 0006-fpga-kconfig-update-kernel-configuration-for-k1-pro-.patch
ApplyOptionalPatch 0007-qemu-kconfig-update-kernel-configuration-for-k1-pro-.patch
ApplyOptionalPatch 0008-sim-kconfig-update-kernel-configuration-for-k1-pro-s.patch
ApplyOptionalPatch 0009-add-k1pro-ccu-driver-and-config.patch
ApplyOptionalPatch 0010-add-k1pro-reset-controller-driver-and-config.patch
ApplyOptionalPatch 0011-update-kernel-config-add-FPGA-label-and-enable-debug.patch
ApplyOptionalPatch 0012-dtsi-enable-zicbom.patch
ApplyOptionalPatch 0013-change-dtb-configuration-to-k1-pro-SOC-1.-ddr-uart-p.patch
ApplyOptionalPatch 0014-dts-add-tcm-node-kernel-add-tcm-driver.patch
ApplyOptionalPatch 0015-add-.h-for-clock-reset-and-change-reg.patch
ApplyOptionalPatch 0016-pwm-dwc-driver-loaded-by-platform-changes-in-Makefil.patch
ApplyOptionalPatch 0017-sync-clk-reset-V1.1-spec-and-use-CLK_OF_DECLARE-for-.patch
ApplyOptionalPatch 0018-spi-adding-the-driver-for-Designware-enhanced-spi-co.patch
ApplyOptionalPatch 0019-riscv-support-svpbmt.patch
ApplyOptionalPatch 0020-usb-dwc3-support-spacemit-platform.patch
ApplyOptionalPatch 0021-dts-dwc3-add-dts-config-for-k1-pro.patch
ApplyOptionalPatch 0022-usb-update-usb-kernel-configuration.patch
ApplyOptionalPatch 0023-usb-dwc3-avoid-suspend-phy.patch
ApplyOptionalPatch 0024-riscv-mm-fix-reserve-cma-for-platform-not-having-ZON.patch
ApplyOptionalPatch 0025-kconfig-enable-cma-for-k1-pro-board.patch
ApplyOptionalPatch 0026-ethernet-adding-the-driver-of-the-Designware-gmac-co.patch
ApplyOptionalPatch 0027-reset-reset-driver-handle-all-global-soft-reset-sing.patch
ApplyOptionalPatch 0028-dma-dw-axi-dma-support-handshake-num-more-than-16.patch
ApplyOptionalPatch 0029-usb-dwc3-modify-reset-control-for-usb31.patch
ApplyOptionalPatch 0030-usb-dwc3-modify-DMA-capability.patch
ApplyOptionalPatch 0031-dma-fix-an-error-burst_trans_len-undeclare-in-dma-dr.patch
ApplyOptionalPatch 0032-mmc-support-spacemit-k1-pro-platform.patch
ApplyOptionalPatch 0033-mmc-dts-support-emmc-and-sdcard.patch
ApplyOptionalPatch 0034-reset-add-spinlock-for-timing-issue.patch
ApplyOptionalPatch 0035-mmc-modify-reset-card-only-once.patch
ApplyOptionalPatch 0036-reshape-dtsi-format-use-table-to-replace-space.patch
ApplyOptionalPatch 0037-k1-pro.dtsi-add-pmu-configs.patch
ApplyOptionalPatch 0038-pcie-support-spacemit-k1-pro-pcie-controller-RC-mode.patch
ApplyOptionalPatch 0039-usb-xhci-modify-DMA-capability-for-k1-pro-platform.patch
ApplyOptionalPatch 0040-change-dts-for-I2C-support.patch
ApplyOptionalPatch 0041-can-add-can-device-driver-and-kernel-config.patch
ApplyOptionalPatch 0042-ccu-add-mcu-clocks.patch
ApplyOptionalPatch 0043-fs-support-nfs.patch
ApplyOptionalPatch 0044-spi-support-spi-nor-and-correct-the-params-of-the-sp.patch
ApplyOptionalPatch 0045-mmc-enable-host-version-4-mode.patch
ApplyOptionalPatch 0046-mmc-deattach-clk-400k-during-mmc_rescan.patch
ApplyOptionalPatch 0047-add-script-for-extract-generate-rootfs.cpio.gz.patch
ApplyOptionalPatch 0048-mmc-increase-date-timeout-counter-value-to-max.patch
ApplyOptionalPatch 0049-remoteproc-support-bringup-esos-for-spacemit-k1-pro_.patch
ApplyOptionalPatch 0050-media-support-usb-media-enable-uvc-and-f_uvc.patch
ApplyOptionalPatch 0051-vpu-fix-vpu-compile-error-for-linux6.1.patch
ApplyOptionalPatch 0052-vpu-add-vpu-dts-config.patch
ApplyOptionalPatch 0053-can-update-kernel-defconfig-IPMS_CAN-y.patch
ApplyOptionalPatch 0054-clk-add-spinlock-and-mailbox-clock-for-mcu-system.patch
ApplyOptionalPatch 0055-reset-add-spinlock-and-mailbox-reset-for-mcu-system.patch
ApplyOptionalPatch 0056-mailbox-enable-spacemit-mailbox-driver.patch
ApplyOptionalPatch 0057-scmi-support-arm-s-scmi-protocol-for-spacemit-platfo.patch
ApplyOptionalPatch 0058-rproc-change-compatible-name-for-rproc-driver.patch
ApplyOptionalPatch 0059-pinctrl-support-the-driver-of-spacemit-pinctrl-contr.patch
ApplyOptionalPatch 0060-dts-add-the-table-of-pin-functions.patch
ApplyOptionalPatch 0061-vpu-add-reset-control-logic.patch
ApplyOptionalPatch 0062-vpu-add-device-caps-config.patch
ApplyOptionalPatch 0063-vpu-remove-severity-and-drain-file-node-for-probe-er.patch
ApplyOptionalPatch 0064-vpu-enable-debug-mode.patch
ApplyOptionalPatch 0065-arm_scmi-regulator-enable-an-dummy-regulator-using-s.patch
ApplyOptionalPatch 0066-dts-disable-vpu-as-some-bitfiles-have-no-vpu.patch
ApplyOptionalPatch 0067-ethernet-support-ethernet-qos.patch
ApplyOptionalPatch 0068-scmi-enable-scmi-power-domain-protocol.patch
ApplyOptionalPatch 0069-scmi-voltage_domain-add-vlittle-vgpu-nodes-in-scmi-d.patch
ApplyOptionalPatch 0070-cpufreq-support-scmi-cpufreq-driver-spacemit-platfor.patch
ApplyOptionalPatch 0071-wifi-cfg80211-enable-wireless-LAN-configuration-API.patch
ApplyOptionalPatch 0072-mmc-dts-support-sdio-interface.patch
ApplyOptionalPatch 0073-GMAC-support-IEEE_1588-hwtimestamp.patch
ApplyOptionalPatch 0074-usb-dts-add-dwc2-dts-for-k1-pro-fpga.patch
ApplyOptionalPatch 0075-usb-kconfig-enable-dwc2-configuration.patch
ApplyOptionalPatch 0076-usb-dwc2-add-params-for-k1-pro-fpga.patch
ApplyOptionalPatch 0077-pinctrl-change-the-format-of-pin-config.patch
ApplyOptionalPatch 0078-spi-nand-support-2x-4x-8x-for-spi-nand-tx-and-rx.patch
ApplyOptionalPatch 0079-ubi-kconfig-enable-ubi-configuration.patch
ApplyOptionalPatch 0080-usb-dwc2-modify-gadget-DMA-capability.patch
ApplyOptionalPatch 0081-add-k1-x-device-support.patch
ApplyOptionalPatch 0082-update-vpu-driver.patch
ApplyOptionalPatch 0083-cpu-support-cpu-hotplug.patch
ApplyOptionalPatch 0084-pinctrl-modify-the-format-of-the-pinctrl-group-name.patch
ApplyOptionalPatch 0085-update-dts-for-k1-x-platform.patch
ApplyOptionalPatch 0086-add-pxa_k1x-driver-for-k1x-platform.patch
ApplyOptionalPatch 0087-k1pro-enable-first-can-use-version-of-cpuidle.patch
ApplyOptionalPatch 0088-k1x-multi-core-modify-the-configurations-related-to-.patch
ApplyOptionalPatch 0089-k1pro-add-i2c-configuration.patch
ApplyOptionalPatch 0090-disable-pm-power-management-is-not-support-now.patch
ApplyOptionalPatch 0091-k1-x-add-mmp_pdma-driver-support.patch
ApplyOptionalPatch 0092-k1x-add-k1-x_fpga-1x4-2x2-proj.patch
ApplyOptionalPatch 0093-k1-x-support-pxa-uart-driver-dts-configs-pm-amend-in.patch
ApplyOptionalPatch 0094-ethernet-adding-gmac-driver-for-k1-x.patch
ApplyOptionalPatch 0095-mmc-support-spacemit-k1x-platform.patch
ApplyOptionalPatch 0096-ethernet-change-the-phy-mode-config-from-device-tree.patch
ApplyOptionalPatch 0097-hotplug-we-d-better-flush-the-local-l2-cache-when-on.patch
ApplyOptionalPatch 0098-mmc-update-dts-remove-axi-node.patch
ApplyOptionalPatch 0099-turn-off-CONFIG_PM-for-debug.patch
ApplyOptionalPatch 0100-config-support-gmac-driver-for-k1-x-1x4-and-2x2.patch
ApplyOptionalPatch 0101-support-tcm-for-k1x.patch
ApplyOptionalPatch 0102-add-udma-driver-for-userspace.patch
ApplyOptionalPatch 0103-dma-copy-use-vaddr.patch
ApplyOptionalPatch 0104-rm-udma-log.patch
ApplyOptionalPatch 0105-update-defconfig-for-support-sdmmc-udma.patch
ApplyOptionalPatch 0106-add-mutex-va2pa-fix-tcm_discontinuous_malloc.patch
ApplyOptionalPatch 0107-update-for-support-tcm.patch
ApplyOptionalPatch 0108-usb-gadget-support-k1x-udc.patch
ApplyOptionalPatch 0109-pcie-adding-pcie-driver-for-k1x.patch
ApplyOptionalPatch 0110-usb-dwc3-support-k1x-platform.patch
ApplyOptionalPatch 0111-k1x-add-pwm-pxa-driver-support.patch
ApplyOptionalPatch 0112-update-vpu-driver.patch
ApplyOptionalPatch 0113-k1pro-adjust-pwm-driver-config-name.patch
ApplyOptionalPatch 0114-k1x-add-soc-timer-driver-support.patch
ApplyOptionalPatch 0115-k1pro-deconfig-axi-dma-driver-Y.patch
ApplyOptionalPatch 0116-support-I2C-for-k1x.patch
ApplyOptionalPatch 0117-media-k1x-vpu-reshape-file-style.patch
ApplyOptionalPatch 0118-update-kernel-default-config.patch
ApplyOptionalPatch 0119-reset-update-reset-controller-driver.patch
ApplyOptionalPatch 0120-ccu-update-clock-controller-driver.patch
ApplyOptionalPatch 0121-fix-config-PCIE_SPACEMIT-depends-on-CONFIG_SOC_SPACE.patch
ApplyOptionalPatch 0122-k1x-switch-pwm-deconfig-Y-on-1x4-2x2-board.patch
ApplyOptionalPatch 0123-k1pro-cpuidle-support-cpuidle.patch
ApplyOptionalPatch 0124-k1pro-add-k1pro-fpga_1x4-k1pro-fpga_2x2-proj.patch
ApplyOptionalPatch 0125-k1-x-add-k1x-gpio-driver-support.patch
ApplyOptionalPatch 0126-riscv-spacemit-remove-k1pro-configuration-it-is-just.patch
ApplyOptionalPatch 0127-yk1x-add-the-first-version-of-pm-domain.patch
ApplyOptionalPatch 0128-k1-x-add-gmac-PTP-support.patch
ApplyOptionalPatch 0129-usb-dwc2-update-fifo-and-reset-config-for-k1-pro.patch
ApplyOptionalPatch 0130-k1x-enable-dmabuf.patch
ApplyOptionalPatch 0131-qspi-adding-driver-for-k1x-qspi-controller.patch
ApplyOptionalPatch 0132-qspi-fix-typo-cause-compilation-errors.patch
ApplyOptionalPatch 0133-add-spacemit-ir-rx-driver.patch
ApplyOptionalPatch 0134-k1x-dts-modify-the-actual-reference-clock-for-sdhci.patch
ApplyOptionalPatch 0135-k1pro-cpuidle-support-cpu0-cluster0-go-deepidle.patch
ApplyOptionalPatch 0136-cpuidle-adapt-code-for-CPUidle-functionality.patch
ApplyOptionalPatch 0137-update-k1x-vpu-driver.patch
ApplyOptionalPatch 0138-k1x-cpuidle-synchronize-relevant-patches-from-k1pro.patch
ApplyOptionalPatch 0139-k1x-support-cpufreq-driver.patch
ApplyOptionalPatch 0140-reset-add-reset-controller-driver-for-k1x.patch
ApplyOptionalPatch 0141-clock-add-clock-controller-driver-for-k1x.patch
ApplyOptionalPatch 0142-dts-fix-worng-and-warning-for-k1x-clk-reset.patch
ApplyOptionalPatch 0143-clock-fix-k1x-clock-id.patch
ApplyOptionalPatch 0144-pinctrl-adding-pinctrl-config-for-k1x-soc.patch
ApplyOptionalPatch 0145-reset-modify-reset-driver-file-name-of-k1pro.patch
ApplyOptionalPatch 0146-clock-modify-clock-driver-file-name-of-k1pro.patch
ApplyOptionalPatch 0147-pm_domain-move-the-pm_domain-driver-to-the-directy-s.patch
ApplyOptionalPatch 0148-v2d-Add-v2d-driver.patch
ApplyOptionalPatch 0149-add-tcm_cfg_save-restore.patch
ApplyOptionalPatch 0150-add-tcm-sync-malloc-code-clean.patch
ApplyOptionalPatch 0151-update-k1-x_fpga.dts-with-device-k1-x-board.dts.patch
ApplyOptionalPatch 0152-mmc-sdhci-of-k1x-support-configure-reset-and-clk-fro.patch
ApplyOptionalPatch 0153-usb-add-reset-and-clk-configurations.patch
ApplyOptionalPatch 0154-pinctrl-supports-the-allocation-of-GPIOs-with-the-sa.patch
ApplyOptionalPatch 0155-pcie-update-the-operations-of-clk-and-reset.patch
ApplyOptionalPatch 0156-display-Add-spacemit-drm-driver.patch
ApplyOptionalPatch 0157-gpu-Add-spacemit-gpu-driver.patch
ApplyOptionalPatch 0158-gpio-update-the-operation-of-clk-for-gpio.patch
ApplyOptionalPatch 0159-pmic-add-the-first-version-of-pmic-driver.patch
ApplyOptionalPatch 0160-pmic-spm8821-pinctrl-first-version-to-support-pinctr.patch
ApplyOptionalPatch 0161-fix-some-warning-when-building-dts.patch
ApplyOptionalPatch 0162-add-configurations-for-k1-x-evb-board.patch
ApplyOptionalPatch 0163-ethernet-update-driver-of-k1x-emac-driver.patch
ApplyOptionalPatch 0164-pm-domain-correction-of-previous-driver-errors-and-a.patch
ApplyOptionalPatch 0165-add-ranges-property-for-some-nodes-which-contain-som.patch
ApplyOptionalPatch 0166-qspi-update-the-opertions-of-clk-and-reset-for-k1x-q.patch
ApplyOptionalPatch 0167-pm_domain-improve-the-execution-process-of-this-driv.patch
ApplyOptionalPatch 0168-pm_domain-move-the-pm-domain-dts-node-to-k1-x.dtsi-f.patch
ApplyOptionalPatch 0169-gpu-Compatible-with-gpu-umd-driver.patch
ApplyOptionalPatch 0170-camera-init-version-of-camera-driver-on-k1.patch
ApplyOptionalPatch 0171-display-Add-spacemit-drm-debugfs-node.patch
ApplyOptionalPatch 0172-k1x-dma-add-clk-reset-control-in-dma-driver.patch
ApplyOptionalPatch 0173-qspi-adding-resets-for-k1-x-qspi.patch
ApplyOptionalPatch 0174-fix-cpu-node-properties-defined-by-linux-6.x.y.patch
ApplyOptionalPatch 0175-spi-add-the-driver-for-k1x-spi-controller.patch
ApplyOptionalPatch 0176-pmic-pm853-support-regulator-driver-and-compatible-w.patch
ApplyOptionalPatch 0177-k1x-uart-add-clock-reset-in-uart-driver.patch
ApplyOptionalPatch 0178-clock-fix-clock-driver-issues-of-k1x.patch
ApplyOptionalPatch 0179-pm-domain-add-new-feature.patch
ApplyOptionalPatch 0180-update-dts-for-support-i2c0.patch
ApplyOptionalPatch 0181-k1x-pwm-driver-adds-clk-reset-control.patch
ApplyOptionalPatch 0182-update-kconfig-to-support-spacemit-k1x-timer-configu.patch
ApplyOptionalPatch 0183-fix-uart-board-configuration-for-asic.patch
ApplyOptionalPatch 0184-clock-reset-fix-pwm-clk-reset-reg-bit.patch
ApplyOptionalPatch 0185-pm853-support-the-regulator-func-in-asic.patch
ApplyOptionalPatch 0186-pmic-open-the-configuration-of-pmic-driver.patch
ApplyOptionalPatch 0187-update-dts-for-i2c-to-support-clk-operation.patch
ApplyOptionalPatch 0188-k1x-i2c-driver-add-clk-reset.patch
ApplyOptionalPatch 0189-k1x-pm-domain-add-gnss-domain.patch
ApplyOptionalPatch 0190-gmac-modify-the-config-for-k1x-gmac-controller.patch
ApplyOptionalPatch 0191-usb-udc-k1x_udc-fix-udc-disconnect.patch
ApplyOptionalPatch 0192-k1x-usb-fix-reset-and-clk-configuration.patch
ApplyOptionalPatch 0193-update-evb-board-dts.patch
ApplyOptionalPatch 0194-remove-some-unused-kernel-module.patch
ApplyOptionalPatch 0195-k1-x-pinctrl-add-fast-config-for-sdcard.patch
ApplyOptionalPatch 0196-update-board-dts-for-evb-and-fpga-boards.patch
ApplyOptionalPatch 0197-display-Add-lcd-gc9503v_mipi.patch
ApplyOptionalPatch 0198-support-jpu-driver-for-k1x.patch
ApplyOptionalPatch 0199-clock-fix-the-result-of-set_rate-is-not-the-closest-.patch
ApplyOptionalPatch 0200-clock-enable-some-clocks.patch
ApplyOptionalPatch 0201-remove-clint-timer.patch
ApplyOptionalPatch 0202-update-dtsi-for-k1-x-platform.patch
ApplyOptionalPatch 0203-config-adding-spacemit-k1x-spi-driver.patch
ApplyOptionalPatch 0204-qspi-fix-the-bus_num-for-k1x-qspi-controller.patch
ApplyOptionalPatch 0205-k1x-vpu-update-driver.patch
ApplyOptionalPatch 0206-k1x-dtsi-linlon-vpu-update-config.patch
ApplyOptionalPatch 0207-usb-k1x_udc-deassert-reset-before-phy-init.patch
ApplyOptionalPatch 0208-k1x-dma-1.add-pm-func-in-dma-driver-2.modify-dma-Kco.patch
ApplyOptionalPatch 0209-k1x-uart-driver-add-pm-func.patch
ApplyOptionalPatch 0210-k1x-i2c-driver-add-pm-domains-revision.patch
ApplyOptionalPatch 0211-qspi-support-pm-runtime-for-qspi-driver.patch
ApplyOptionalPatch 0212-dts-adding-power-domains-for-k1x-qspi.patch
ApplyOptionalPatch 0213-k1x-pm-open-the-configuration-of-pm-domain-driver.patch
ApplyOptionalPatch 0214-k1x-dtsi-jpu-update-config.patch
ApplyOptionalPatch 0215-k1x-evb-defconfig-enable-CHIP_MEDIA_JPU.patch
ApplyOptionalPatch 0216-add-some-debug-configuration.patch
ApplyOptionalPatch 0217-feat-gpu-Support-gpu-for-k1x-evb-board.patch
ApplyOptionalPatch 0218-mmc-k1x-add-host-capability-MMC_CAP_NEED_RSP_BUSY.patch
ApplyOptionalPatch 0219-k1x-dtsi-jpu-add-reset-config.patch
ApplyOptionalPatch 0220-k1x-uart-add-reference-to-pm-domain.patch
ApplyOptionalPatch 0221-k1x-dma-add-reference-to-pm-domain.patch
ApplyOptionalPatch 0222-k1x-cpufreq-support-cpufreq-function.patch
ApplyOptionalPatch 0223-usb-phy-k1x-ci-usb2-update-phy-init-parameters-fix-h.patch
ApplyOptionalPatch 0224-usb-ehci-add-support-for-k1-x-ehci-driver.patch
ApplyOptionalPatch 0225-dts-k1-x-add-ehci-usb-host-support.patch
ApplyOptionalPatch 0226-config-enable-k1x-ehci-host-driver.patch
ApplyOptionalPatch 0227-update-evb-board-dts.patch
ApplyOptionalPatch 0228-disable-cpufreq-it-will-crash-kernel.patch
ApplyOptionalPatch 0229-config-k1-x-enable-more-usb-functions.patch
ApplyOptionalPatch 0230-clock-fix-camm2-no-clock-issue-change-enable-bit.patch
ApplyOptionalPatch 0231-clock-fix-set_rate-function-it-change-rate-by-div-an.patch
ApplyOptionalPatch 0232-clock-enable-some-clocks-for-cpu-remove-cpu-core-clk.patch
ApplyOptionalPatch 0233-k1x-cpufreq-don-t-need-to-set-parent-when-set-the-fr.patch
ApplyOptionalPatch 0234-display-Support-lcd-icnl9911c-mipi.patch
ApplyOptionalPatch 0235-sync-dts-with-device-board.dts.patch
ApplyOptionalPatch 0236-usb-hid-enable-raw-HID-device-support.patch
ApplyOptionalPatch 0237-clock-fix-qspi_clk-issue-only-set-fc-bit-when-settin.patch
ApplyOptionalPatch 0238-k1x-pm-domain-change-the-log-level-of-debug-info.patch
ApplyOptionalPatch 0239-display-fix-dpu-reset-control.patch
ApplyOptionalPatch 0240-config-k1x-enable-usb-webcam-support.patch
ApplyOptionalPatch 0241-k1x-add-watchdog-driver-support.patch
ApplyOptionalPatch 0242-k1x-add-reboot-with-args-support.patch
ApplyOptionalPatch 0243-fix-gpu-move-loading-firmware-later.patch
ApplyOptionalPatch 0244-k1x-spacemit-timer-driver-add-clk-reset-interface.patch
ApplyOptionalPatch 0245-k1x-timer-clk-reset-dts-config.patch
ApplyOptionalPatch 0246-mmc-sdhci-of-k1x-add-quirks2-SDHCI_QUIRK2_BROKEN_64_.patch
ApplyOptionalPatch 0247-reserved-2GB-4GB-area-from-memory-space-it-should-be.patch
ApplyOptionalPatch 0248-k1x-pm_domain-using-hw-mode-to-power-on-off-audio-s-.patch
ApplyOptionalPatch 0249-k1x-add-k1x-soc-rtc-driver-and-clk-reset-interface.patch
ApplyOptionalPatch 0250-sync-evb-board-dts-from-device-k1x-evb-board.dts.patch
ApplyOptionalPatch 0251-clean-compile-warning-in-arch-riscv-mm-init.c.patch
ApplyOptionalPatch 0252-clean-compile-warning-in-display-driver.patch
ApplyOptionalPatch 0253-clean-compile-warning-in-pcie-driver.patch
ApplyOptionalPatch 0254-k1x-wdt-update-watchdog-driver.patch
ApplyOptionalPatch 0255-clock-twsi8-clk-reset-reg-is-write-only-don-t-read-i.patch
ApplyOptionalPatch 0256-k1x-reboot-fix-reboot-into-fastboot-mode-with-no-arg.patch
ApplyOptionalPatch 0257-add-pwm-control-backlight.patch
ApplyOptionalPatch 0258-k1x-pinctrl.dtsi-fix-some-pinctrl-error.patch
ApplyOptionalPatch 0259-k1x-update-DTS-automatically-based-on-env.patch
ApplyOptionalPatch 0260-mmc-sdhci-of-k1x-update-sdio-scan-interface.patch
ApplyOptionalPatch 0261-add-tcm_override_readl-writel-for-access-tcm-overrid.patch
ApplyOptionalPatch 0262-k1x-unique-mac-address-in-eeprom.patch
ApplyOptionalPatch 0263-modify-compile-optimize-from-O2-to-Os.patch
ApplyOptionalPatch 0264-clean-compile-waring-in-vpu-driver.patch
ApplyOptionalPatch 0265-dts-add-apbc2-reg-base-for-clock-and-reset.patch
ApplyOptionalPatch 0266-clock-add-apbc2-reg-base-clocks.patch
ApplyOptionalPatch 0267-reset-add-apb2-reg-base-resets.patch
ApplyOptionalPatch 0268-clock-add-CLK_IGNORE_UNUSED-flag-for-some-clocks.patch
ApplyOptionalPatch 0269-vpu-can-use-when-RAM-2GB.patch
ApplyOptionalPatch 0270-support-non-uniform-address-mapping-between-peripher.patch
ApplyOptionalPatch 0271-add-nfsd-support.patch
ApplyOptionalPatch 0272-add-exfat-fs-support.patch
ApplyOptionalPatch 0273-add-xfs-support.patch
ApplyOptionalPatch 0274-add-btrfs-support.patch
ApplyOptionalPatch 0275-add-f2fs-support.patch
ApplyOptionalPatch 0276-add-quota-used-by-ext4-support.patch
ApplyOptionalPatch 0277-add-device-mapper-used-by-RAID-and-FS-crypto.patch
ApplyOptionalPatch 0278-add-bridge-and-vlan-support-used-by-docker-vm.patch
ApplyOptionalPatch 0279-add-ipv6-support.patch
ApplyOptionalPatch 0280-add-ntfs-v3.1-same-with-win10-s-native-fs-support.patch
ApplyOptionalPatch 0281-yk1x-thermal-support-thermal-driver.patch
ApplyOptionalPatch 0282-k1x-dma-close-some-unnecessary-config.patch
ApplyOptionalPatch 0283-k1x-dma-range-add-a-driver-for-devices-node-dram_ran.patch
ApplyOptionalPatch 0284-k1x-dma-fix-compile-error-in-include-k1x-dmac.h.-def.patch
ApplyOptionalPatch 0285-k1x-support-aes-crypto-engine.patch
ApplyOptionalPatch 0286-k1x-kernel-support-afalg-engine.patch
ApplyOptionalPatch 0287-support-camera-to-draw-when-use-2GB-DDR-dtsi-and-def.patch
ApplyOptionalPatch 0288-clear-compile-warning.patch
ApplyOptionalPatch 0289-clear-compile-warning.patch
ApplyOptionalPatch 0290-sync-evb-board.dts-from-devices-k1x-evb.patch
ApplyOptionalPatch 0291-camera-self-managed-ldo.patch
ApplyOptionalPatch 0292-k1x-pm-domain-add-hdmi-domiain.patch
ApplyOptionalPatch 0293-v2d-support-use-memory-2GB.patch
ApplyOptionalPatch 0294-k1x-pmic-refine-some-code.patch
ApplyOptionalPatch 0295-support-camera-to-draw-when-use-4GB-DDR.patch
ApplyOptionalPatch 0296-display-phy-driver-has-been-registered-in-another-fu.patch
ApplyOptionalPatch 0297-pci-add-initialization-phy-of-pcie-for-k1x.patch
ApplyOptionalPatch 0298-k1x-pm-domain-the-IO-size-too-small-to-cover-the-HDM.patch
ApplyOptionalPatch 0299-pcie-adding-dram_range1-for-pcie0-pcie1-pci2.patch
ApplyOptionalPatch 0300-add-dts-and-config-for-deb2-board.patch
ApplyOptionalPatch 0301-display-Support-spacemit-hdmi-driver.patch
ApplyOptionalPatch 0302-target-add-task-management-values-and-overlapped-res.patch
ApplyOptionalPatch 0303-usb-f_tcm-support-mutltiple-cmds-enhance-performance.patch
ApplyOptionalPatch 0304-k1x-support-reboot-to-uboot-shell.patch
ApplyOptionalPatch 0305-sync-evb-deb2-board-dts-from-devices.patch
ApplyOptionalPatch 0306-fix-cpp-clk-timeout.patch
ApplyOptionalPatch 0307-fix-gpu-memory-leak-when-launch-weston.patch
ApplyOptionalPatch 0308-k1x-cpufreq-support-adjust-the-ace-tcm-s-frequency-a.patch
ApplyOptionalPatch 0309-fix-dead-lock-bug-between-reset-and-clk.patch
ApplyOptionalPatch 0310-k1x-cpu-cooling-support-cpu-cooling-device.patch
ApplyOptionalPatch 0311-extcon-add-extcon-k1xci-driver-for-usb2.0-otg.patch
ApplyOptionalPatch 0312-usb-otg-add-k1x-ci-otg-driver.patch
ApplyOptionalPatch 0313-dtsi-k1-x-add-usb2-otg-support.patch
ApplyOptionalPatch 0314-clock-add-apb-clk-enable-apb-axi-clk-when-init.patch
ApplyOptionalPatch 0315-k1x-pmic-refine-the-pmic-code.patch
ApplyOptionalPatch 0316-display-Support-hdmi-1080p.patch
ApplyOptionalPatch 0317-clock-dead-lock-issue-may-happen.patch
ApplyOptionalPatch 0318-mmc-dts-support-power-domain.patch
ApplyOptionalPatch 0319-mmc-sdhci-of-k1x-add-pm_runtime_get_sync-during-prob.patch
ApplyOptionalPatch 0320-pcie-Optimize-phy-initialization-code-for-k1x-pcie-d.patch
ApplyOptionalPatch 0321-dts-modify-the-domain-id-of-pcie1-to-1.patch
ApplyOptionalPatch 0322-k1x-pmic-support-power-key-driver.patch
ApplyOptionalPatch 0323-k1x-pmic-rtc-support-spm8821-rtc-driver.patch
ApplyOptionalPatch 0324-reshape-pinctrl-dtsi-and-platform-dtsi.patch
ApplyOptionalPatch 0325-display-Fix-reset-control-deassert-and-assert.patch
ApplyOptionalPatch 0326-clean-clk-driver-debug-info.patch
ApplyOptionalPatch 0327-clean-drm-driver-debug-info.patch
ApplyOptionalPatch 0328-clean-camera-driver-debug-info.patch
ApplyOptionalPatch 0329-clean-dma-driver-debug-info.patch
ApplyOptionalPatch 0330-clean-usb-driver-debug-info.patch
ApplyOptionalPatch 0331-clean-tcm-driver-debug-info.patch
ApplyOptionalPatch 0332-clean-qspi-driver-debug-info.patch
ApplyOptionalPatch 0333-clean-crypto-driver-debug-info.patch
ApplyOptionalPatch 0334-clean-i2c-driver-debug-info.patch
ApplyOptionalPatch 0335-clean-reset-driver-debug-info.patch
ApplyOptionalPatch 0336-clean-gmac-driver-debug-info.patch
ApplyOptionalPatch 0337-clean-some-unused-driver-module.patch
ApplyOptionalPatch 0338-add-gx09inx101-mipi-lcd-configuration.patch
ApplyOptionalPatch 0339-k1x-crypto-1.handle-memleak-in-probe-2.ture-down-sel.patch
ApplyOptionalPatch 0340-k1x-pmic-refactoring-code-to-support-new-dcdc.patch
ApplyOptionalPatch 0341-defconfig-add-usb3.0-support-for-k1-x-evb2.patch
ApplyOptionalPatch 0342-usb-misc-add-spacemit-onboard-hub-driver.patch
ApplyOptionalPatch 0343-dtsi-k1-x-add-usb3.0-support.patch
ApplyOptionalPatch 0344-usb-add-spacemit-k1x-dma-mask-setting.patch
ApplyOptionalPatch 0345-phy-add-spacemit-pcie-usb3-combphy-driver.patch
ApplyOptionalPatch 0346-spacemit-rf-add-wifi-platform-driver.patch
ApplyOptionalPatch 0347-spacemit-rf-dts-enable-spacemit-rf-pwrseq.patch
ApplyOptionalPatch 0348-k1x-cpuidle-support-cpu-power-down-only.patch
ApplyOptionalPatch 0349-wireless-rtl8852bs-add-rtl8852bs-sdio-wifi-driver.patch
ApplyOptionalPatch 0350-wifi-k1x-deb2-enable-rtl8852bs-wifi-defconfig.patch
ApplyOptionalPatch 0351-k1x-cpufreq-support-adjust-the-voltage-when-the-cpu-.patch
ApplyOptionalPatch 0352-display-Fix-hdmi-qos-control.patch
ApplyOptionalPatch 0353-mmc-dts-alloc-index-from-alias-id.patch
ApplyOptionalPatch 0354-disable-rtl8852bs-wifi-driver-there-is-too-much-warn.patch
ApplyOptionalPatch 0355-update-evb-board-dts.patch
ApplyOptionalPatch 0356-update-deb2-board-dts.patch
ApplyOptionalPatch 0357-update-deb2-kernel-config.patch
ApplyOptionalPatch 0358-sync-deb2-board-dts.patch
ApplyOptionalPatch 0359-wifi-k1x-deb2-enable-aic8800dc-wifi-defconfig.patch
ApplyOptionalPatch 0360-wifi-k1x-evb-enable-aic8800dc-wifi-defconfig.patch
ApplyOptionalPatch 0361-audio-add-audio-driver.patch
ApplyOptionalPatch 0362-dts-add-audio-snd-card-support.patch
ApplyOptionalPatch 0363-enable-audio-driver-for-evb-board.patch
ApplyOptionalPatch 0364-enable-audio-driver-for-deb2.patch
ApplyOptionalPatch 0365-clear-compile-warning.patch
ApplyOptionalPatch 0366-support-dvfs-for-evb-performance.patch
ApplyOptionalPatch 0367-use-performance-governor-as-default.patch
ApplyOptionalPatch 0368-audio-change-pcm-hw_params.patch
ApplyOptionalPatch 0369-display-Support-kernel-logo.patch
ApplyOptionalPatch 0370-display-update-kernel-logo.patch
ApplyOptionalPatch 0371-disable-audio-and-adsp-driver.patch
ApplyOptionalPatch 0372-disable-audio-and-adsp-driver.patch
ApplyOptionalPatch 0373-display-fix-kernel-logo.patch
ApplyOptionalPatch 0374-k1x-can-add-clk-reset-control-in-dma-driver.patch
ApplyOptionalPatch 0375-clock-fix-can-func-clk-incorrect-issue.patch
ApplyOptionalPatch 0376-reset-fix-reset-bit-of-aes.patch
ApplyOptionalPatch 0377-k1x-deb1-support-deb1-project.patch
ApplyOptionalPatch 0378-k1x-deb1-add-k1-x_deb1.dts-to-fix-compiling-error-wh.patch
ApplyOptionalPatch 0379-k1x-pmic-support-pwr-key-rtc-pinctrl-function.patch
ApplyOptionalPatch 0380-spacemit-rf-add-bluetooth-platform-driver.patch
ApplyOptionalPatch 0381-wifi-k1x-deb2-enable-rtl8852bs-wifi-defconfig.patch
ApplyOptionalPatch 0382-sync-board-dts-from-devices.patch
ApplyOptionalPatch 0383-add-k1-universal-config-for-all-board.patch
ApplyOptionalPatch 0384-fix-disable-CONFIG_INITRAMFS_SOURCE-which-may-overla.patch
ApplyOptionalPatch 0385-wifi-k1x-deb1-enable-rtl8852bs-wifi-defconfig.patch
ApplyOptionalPatch 0386-k1-x-crypto-speed-up-expand-single-encrypt-decrypt-s.patch
ApplyOptionalPatch 0387-sync-board-dts-from-devices.patch
ApplyOptionalPatch 0388-wireless-rtl8852be-add-wifi-driver.patch
ApplyOptionalPatch 0389-k1x-cpu-cooling-add-the-cpuidle-cooling-function.patch
ApplyOptionalPatch 0390-clock-reset-fix-pwm0-clk-reset-reg-bit.patch
ApplyOptionalPatch 0391-add-cpu-model-name-showed-in-proc-cpuinfo.patch
ApplyOptionalPatch 0392-k1x-adjust-i2c-driver-strength.patch
ApplyOptionalPatch 0393-add-docker-required-configurations-1.-bridge-and-vla.patch
ApplyOptionalPatch 0394-k1x-deb1-support-power-off-system.patch
ApplyOptionalPatch 0395-display-Fix-dpu-reset-issue.patch
ApplyOptionalPatch 0396-sync-board-dts-from-devices.patch
ApplyOptionalPatch 0397-tools-perf-pmu-events-add-SpacemiT-X60-JSON-files.patch
ApplyOptionalPatch 0398-k1x-add-zicboz-and-zicbop-to-dts.patch
ApplyOptionalPatch 0399-modify-compile-optimize-from-size-to-performance.patch
ApplyOptionalPatch 0400-display-disable-kernel-logo.patch
ApplyOptionalPatch 0401-set-cma-alloc-range-from-0x40000000.patch
ApplyOptionalPatch 0402-sync-board-dts-from-devices-configuration.patch
ApplyOptionalPatch 0403-qspi-Correct-the-setting-clk-rate-of-k1x-qspi.patch
ApplyOptionalPatch 0404-performance-optimize.patch
ApplyOptionalPatch 0405-k1x-support-PCIE-SATA-JMB585-board.patch
ApplyOptionalPatch 0406-Bluetooth-enable-bluez-stack.patch
ApplyOptionalPatch 0407-uart-disable-bluesleep-hostwake-detect.patch
ApplyOptionalPatch 0408-clock-uart-source-48M-and-14.7M-have-same-gate-bit-i.patch
ApplyOptionalPatch 0409-k1x-uart-add-uart-parent-clk-gate-function.patch
ApplyOptionalPatch 0410-sync-board-dts-with-devices.patch
ApplyOptionalPatch 0411-display-Update-hdmi-phy-config.patch
ApplyOptionalPatch 0412-k1-x-aes-prevent-writing-buffer-requests-in-the-mean.patch
ApplyOptionalPatch 0413-k1x-aes-add-xts-cipher.patch
ApplyOptionalPatch 0414-display-Support-dsi-and-hdmi-double-screens.patch
ApplyOptionalPatch 0415-use-the-unified-defconfig-for-k1-5-5.patch
ApplyOptionalPatch 0416-add-ramdisk-for-develop-branch.patch
ApplyOptionalPatch 0417-k1-enable-usb-serial.patch
ApplyOptionalPatch 0418-mmc-sdhci-of-k1x-improve-the-sd-tuning-process.patch
ApplyOptionalPatch 0419-scatterlist-mask-out-GFP_DMA32-flag-when-call-kmallo.patch
ApplyOptionalPatch 0420-target-alloc-scatterlist-with-GFP_DMA32-flag-on-spac.patch
ApplyOptionalPatch 0421-k1-x-enable-ehci-for-deb1-and-deb2.patch
ApplyOptionalPatch 0422-display-Remove-error-logs.patch
ApplyOptionalPatch 0423-k1x-support-mailbox-driver.patch
ApplyOptionalPatch 0424-k1x-remoteproc-support-remoteproc-driver.patch
ApplyOptionalPatch 0425-k1x-rproc-launching-rcpu-during-the-system-startup-p.patch
ApplyOptionalPatch 0426-k1x-defconfig-enable-mailbox-rproc-rpmsg_virtio-defc.patch
ApplyOptionalPatch 0427-k1-rcpu-ipc-reserved-memory-for-rcpu-and-ipc.patch
ApplyOptionalPatch 0428-k1x-adma-add-adma-driver-for-sspa.patch
ApplyOptionalPatch 0429-audio-add-hdmi-audio-driver-and-remove-unused-code.patch
ApplyOptionalPatch 0430-deconfig-enable-sound-support.patch
ApplyOptionalPatch 0431-dts-add-hdmi-audio-config.patch
ApplyOptionalPatch 0432-dts-modify-audio-config.patch
ApplyOptionalPatch 0433-k1x-rporc-add-the-reference-of-mailbox-memory-region.patch
ApplyOptionalPatch 0434-audio-modify-hdmi-audio-params-set-enable-ctrl-reg.patch
ApplyOptionalPatch 0435-k1-support-CTP-driver.patch
ApplyOptionalPatch 0436-display-Fixed-dtsi-warning.patch
ApplyOptionalPatch 0437-dtb-adding-the-dts-of-linux-for-hs450-board.patch
ApplyOptionalPatch 0438-k1-defconfig-enable-support-for-r8152.patch
ApplyOptionalPatch 0439-disp-adjust-gpu-and-drm-initcall-sequence-for-fixed-.patch
ApplyOptionalPatch 0440-gitignore-add-user_headers-generated-by-openwrt-to-g.patch
ApplyOptionalPatch 0441-k1x-snd-fix-compile-warning-in-spacemit-snd-card.c.patch
ApplyOptionalPatch 0442-img-rogue-fix-compile-warning.patch
ApplyOptionalPatch 0443-k1x-display-fix-compile-warning.patch
ApplyOptionalPatch 0444-gt9xx-fix-compile-warning.patch
ApplyOptionalPatch 0445-eeprom-at24-fix-compile-warning.patch
ApplyOptionalPatch 0446-k1x-hdmi-fix-compile-warning-because-of-unused-varia.patch
ApplyOptionalPatch 0447-brtfs-fix-compile-warning.patch
ApplyOptionalPatch 0448-sync-camera-code-from-Release-JINDIE-V3.8.patch
ApplyOptionalPatch 0449-sync-camera-code-from-Release-JINDIE-V4.0.patch
ApplyOptionalPatch 0450-mmc-sdhci-of-k1x-update-phy-dll-config.patch
ApplyOptionalPatch 0451-aud-modify-hdmi-audio-period_size-fix-coding-issue.patch
ApplyOptionalPatch 0452-k1-gpio-support-irq-controller-mode.patch
ApplyOptionalPatch 0453-k1-open-hid-configs.patch
ApplyOptionalPatch 0454-k1-support-touchpad-for-hs450-board.patch
ApplyOptionalPatch 0455-aud-add-spi-i2s-driver.patch
ApplyOptionalPatch 0456-dts-add-i2s-support.patch
ApplyOptionalPatch 0457-dts-add-codec-es8326-support-i2s-pin-config.patch
ApplyOptionalPatch 0458-config-enable-codec-es8326.patch
ApplyOptionalPatch 0459-aud-add-es8326-sound-card-support.patch
ApplyOptionalPatch 0460-k1_defconfig-enable-USB_NET_QMI_WWAN.patch
ApplyOptionalPatch 0461-udma-open-failed-when-dma_dev-NULL.patch
ApplyOptionalPatch 0462-k1x-dma-support-console-tx-rx-dma-mode.patch
ApplyOptionalPatch 0463-dtb-adding-the-dts-of-linux-for-kx312-board.patch
ApplyOptionalPatch 0464-Bluetooth-defconfig-support-hid-and-pan-profile.patch
ApplyOptionalPatch 0465-gmac-Modify-gmac-pin-configuration-in-order-to-impro.patch
ApplyOptionalPatch 0466-usb-misc-spacemit_onboard_hub-use-gpio-array.patch
ApplyOptionalPatch 0467-dts-k1-x_kx312-enable-usbdrd3-and-usb3hub.patch
ApplyOptionalPatch 0468-dtb-adding-the-dts-of-linux-for-MINI-PC-board.patch
ApplyOptionalPatch 0469-add-kernel-image-itb-build-support.patch
ApplyOptionalPatch 0470-perfect-camera-dts-gpio-config.patch
ApplyOptionalPatch 0471-display-Fix-dpu-irqs-timeout.patch
ApplyOptionalPatch 0472-k1-align-initial-state-for-audio.patch
ApplyOptionalPatch 0473-k1-rpoc-using-a-RT-thread-to-process-the-virtio-msg.patch
ApplyOptionalPatch 0474-k1-delete-undefined-pm-function.patch
ApplyOptionalPatch 0475-dtb-adding-the-dts-of-linux-for-mingo-board.patch
ApplyOptionalPatch 0476-kx312-fix-the-compile-error-that-it-can-t-find-dpu_o.patch
ApplyOptionalPatch 0477-k1x-uart-fix-uart9-dts-config.patch
ApplyOptionalPatch 0478-k1x-serial-fix-bug-of-pm-runtime-feature.patch
ApplyOptionalPatch 0479-k1x-system_suspend-support-pmic-wakeup-source.patch
ApplyOptionalPatch 0480-mmc-sdhci-of-k1x-optimize-sdcard-tuning-procedure.patch
ApplyOptionalPatch 0481-k1-dts-update-dts.patch
ApplyOptionalPatch 0482-vpu-update-vpu-driver-version-to-Release-JINDIE-V4.2.patch
ApplyOptionalPatch 0483-v2d-mv-v2d-from-drivers-media-platform-spacemit-v2d-.patch
ApplyOptionalPatch 0484-add-kernel-image-offset-configuration-which-would-be.patch
ApplyOptionalPatch 0485-more-flexable-configuration-for-image-itb-build.patch
ApplyOptionalPatch 0486-k1x-dts-enable-sdio-sdr104-mode.patch
ApplyOptionalPatch 0487-mmc-sdhci-of-k1x-support-disable-caps.patch
ApplyOptionalPatch 0488-add-compressed-gzip-kernel-itb-build.patch
ApplyOptionalPatch 0489-k1-dts-disable-mipi-dsi-for-deb1.patch
ApplyOptionalPatch 0490-display-Fix-dpu-irqs-error.patch
ApplyOptionalPatch 0491-arch-riscv-Changed-default-target-to-Image.gz.itb-wh.patch
ApplyOptionalPatch 0492-update-evb-dts.patch
ApplyOptionalPatch 0493-display-add-hdmi-edid.patch
ApplyOptionalPatch 0494-dts-dpu_reserved-move-dpu-reserved-memory-to-0x2ff40.patch
ApplyOptionalPatch 0495-wireless-build-rtl8852be-module-into-kernel.patch
ApplyOptionalPatch 0496-aud-limit-i2s-audio-params.patch
ApplyOptionalPatch 0497-dts-config-codec-snd-card-support.patch
ApplyOptionalPatch 0498-k1-system_suspend-enable-cpuidle-configuration-for-s.patch
ApplyOptionalPatch 0499-k1-dma-add-suspend-resume-callback-for-dma-module.patch
ApplyOptionalPatch 0500-display-Fix-read-hdmi-edid-data-error.patch
ApplyOptionalPatch 0501-vpu-sync-Release-JINDIE-V4.3.1-on-2024-03-19-06-08.patch
ApplyOptionalPatch 0502-mmc-sdhci-of-k1x-avoid-scan-sdio-during-start-host.patch
ApplyOptionalPatch 0503-k1-cpufreq-fix-bug-that-the-system-do-not-update-the.patch
ApplyOptionalPatch 0504-k1-cpu_cooling_device-add-the-mechanism-for-cpu-cool.patch
ApplyOptionalPatch 0505-k1-cpu_cooling-add-the-function-that-hotpluging-core.patch
ApplyOptionalPatch 0506-k1-thermal-enable-cpufreq-cooling-device.patch
ApplyOptionalPatch 0507-mmc-sdhci-of-k1x-improve-the-tuning-window-select.patch
ApplyOptionalPatch 0508-k1x-adjust-i2s-driver-strength.patch
ApplyOptionalPatch 0509-dts-config-es8326-ADC-src-to-dmic.patch
ApplyOptionalPatch 0510-eth-changing-the-dma-range-and-setting-dma-coherent-.patch
ApplyOptionalPatch 0511-display-Fix-hdmi-read-edid-data-code-error.patch
ApplyOptionalPatch 0512-phy-spacemit-k1x-combphy-get-shared-reset.patch
ApplyOptionalPatch 0513-MINIPC-fix-pcie2-lane-config.patch
ApplyOptionalPatch 0514-k1x-dts-update-mmc-tuning-config.patch
ApplyOptionalPatch 0515-aud-fix-i2s-capture-issue.patch
ApplyOptionalPatch 0516-mmc-sdhci-of-k1x-add-tx-delaycode-attr-for-sd-sdio.patch
ApplyOptionalPatch 0517-leds-Support-hearbeat.patch
ApplyOptionalPatch 0518-phy-k1x-ci-usb2-add-notify-callbacks-remove-unused-c.patch
ApplyOptionalPatch 0519-usb-xhci-fix-spacemit-k1x-phy-disconnect-detect.patch
ApplyOptionalPatch 0520-phy-spacemit-k1x-combphy-don-t-assert-when-use-share.patch
ApplyOptionalPatch 0521-eth-change-the-range-of-dma-to-range1.patch
ApplyOptionalPatch 0522-eth-improve-the-through-of-gmac.patch
ApplyOptionalPatch 0523-display-Modify-hdmi-and-mipi-dsi-qos.patch
ApplyOptionalPatch 0524-k1-kx312-add-touchpad-dts.patch
ApplyOptionalPatch 0525-kx312-enable-es8326-sound-card-support.patch
ApplyOptionalPatch 0526-clk-add-pll2-support-2800MHz.patch
ApplyOptionalPatch 0527-eth-change-the-num-of-tx-rx-desc-buffer-to-1024-for-.patch
ApplyOptionalPatch 0528-k1-sys-reboot-using-the-reset-function-of-pmic-rathe.patch
ApplyOptionalPatch 0529-display-modify-mipi-dsi-dpu-bit-clock.patch
ApplyOptionalPatch 0530-display-support-lt8911exb-driver.patch
ApplyOptionalPatch 0531-pcie-getting-the-num-lanes-of-pcie-controller-in-phy.patch
ApplyOptionalPatch 0532-pcie-change-the-dma-ranges-of-pcie-to-drma_range2.patch
ApplyOptionalPatch 0533-kx312-modify-pcie1-to-1-lane.patch
ApplyOptionalPatch 0534-scripts-Added-build_kernel.sh.patch
ApplyOptionalPatch 0535-aud-fix-the-first-buffer-data-loss-issue.patch
ApplyOptionalPatch 0536-i2s-fix-LR-channel-mapping-incorrect-issue.patch
ApplyOptionalPatch 0537-usb-spacemit_onboard_hub-fix-bug-caused-by-no-delay-.patch
ApplyOptionalPatch 0538-pcie-change-the-get_reset-method-of-pcie0-to-shared.patch
ApplyOptionalPatch 0539-scripts-Fixed-build_kernel.sh-error.patch
ApplyOptionalPatch 0540-config-enable-needed-config-checked-by-check-config..patch
ApplyOptionalPatch 0541-k1x-i2c-update-i2c-driver.patch
ApplyOptionalPatch 0542-display-Support-hdmi-hot-plug-detection.patch
ApplyOptionalPatch 0543-display-Fix-pm-runtime-status.patch
ApplyOptionalPatch 0544-dts-Enable-kx312-hdmi.patch
ApplyOptionalPatch 0545-k1x-wdt-fix-timeout-setting-bug.patch
ApplyOptionalPatch 0546-k1-cpufreq-cooling-refine-some-code-for-cpu-cooling.patch
ApplyOptionalPatch 0547-plic-clear-irq-pending-when-init-plic.patch
ApplyOptionalPatch 0548-k1-i2c-let-the-system-framework-dealing-with-suspend.patch
ApplyOptionalPatch 0549-k1-spi-jion-the-pm-domain-framework-to-achieve-power.patch
ApplyOptionalPatch 0550-k1-qspi-support-pm-runtime-system-suspend.patch
ApplyOptionalPatch 0551-k1-rproc-support-system-suspend-callback-for-rcpu.patch
ApplyOptionalPatch 0552-k1x-aes-add-aes-clk-reset-and-suspend-resume-callbac.patch
ApplyOptionalPatch 0553-eth-support-suspend-and-resume-for-pm.patch
ApplyOptionalPatch 0554-k1x-MINIPC-support-kernel-hdmi.patch
ApplyOptionalPatch 0555-k1x-rcpu-support-suspend-resume-function-for-rcpu.patch
ApplyOptionalPatch 0556-clock-add-audio-clocks.patch
ApplyOptionalPatch 0557-display-Do-not-set-clock-rate-in-dts.patch
ApplyOptionalPatch 0558-reset-add-audio-resets.patch
ApplyOptionalPatch 0559-hdmiaudio-add-pm-runtime-and-reset.patch
ApplyOptionalPatch 0560-i2s-add-pm-runtime-and-suspend-resume.patch
ApplyOptionalPatch 0561-vpu-support-suspend-and-resume.patch
ApplyOptionalPatch 0562-jpu-support-suspend-and-resume.patch
ApplyOptionalPatch 0563-display-Fix-the-minimum-brightness-for-the-lcd.patch
ApplyOptionalPatch 0564-vpu-remove-some-unuseful-log.patch
ApplyOptionalPatch 0565-dtsi-k1-x-add-interconnects-to-ehci.patch
ApplyOptionalPatch 0566-dts-k1-x_MINI-PC-change-usb0-mode-from-udc-to-ehci.patch
ApplyOptionalPatch 0567-display-Support-no-edid-panel.patch
ApplyOptionalPatch 0568-pcie-support-suspend-and-resume-for-pm.patch
ApplyOptionalPatch 0569-dts-k1-x_MINI-PC-add-usb2hub-node.patch
ApplyOptionalPatch 0570-k1_defconfig-enable-usb-serial-drivers-as-modules.patch
ApplyOptionalPatch 0571-drm-fix-the-buffer-allocation-failed.patch
ApplyOptionalPatch 0572-delete-camera-debug-code.patch
ApplyOptionalPatch 0573-k1-pmic-increase-initialization-level-for-other-modu.patch
ApplyOptionalPatch 0574-MINI-PC-Disable-mipi-dsi.patch
ApplyOptionalPatch 0575-fix-gpu_clk-clock-setting-timeout.patch
ApplyOptionalPatch 0576-k1_defconfig-change-dummy-device-default-to-module.patch
ApplyOptionalPatch 0577-dts-k1-x_deb1-use-PAD_1V8_DS0-for-DVL1-and-GPIO_123.patch
ApplyOptionalPatch 0578-dts-adding-module_usrload-for-loading-wifi-driver.patch
ApplyOptionalPatch 0579-k1x-pinctrl-adjust-uart2-driver-strength.patch
ApplyOptionalPatch 0580-usb-spacemit_onboard_hub-use-devm_gpiod_get_array_op.patch
ApplyOptionalPatch 0581-swiotlb-Adjust-the-size-of-swiotlb-to-128M.patch
ApplyOptionalPatch 0582-dram_range-change-the-mapping-range-for-dram_range2.patch
ApplyOptionalPatch 0583-swiotlb-adjust-the-size-and-segsize-of-io-tlb.patch
ApplyOptionalPatch 0584-display-Fix-card-order-for-mipi-dsi-and-hdmi.patch
ApplyOptionalPatch 0585-fix-wdt-timeout-setting-use-max-timeout-if-timeout-o.patch
ApplyOptionalPatch 0586-mmc-sdhci-of-k1x-add-get-aib-clk-avoid-disable-as-cl.patch
ApplyOptionalPatch 0587-clock-fix-emac-ptp-clk-source.patch
ApplyOptionalPatch 0588-k1x-rtc-fix-the-bug-that-setting-rtc-time-failed.patch
ApplyOptionalPatch 0589-aud-support-snd-card-config-in-dts.patch
ApplyOptionalPatch 0590-dts-change-hdmi-es8326-snd-card-config.patch
ApplyOptionalPatch 0591-k1x-rproc-fix-bug-of-rproc-driver.patch
ApplyOptionalPatch 0592-dtb-adding-the-dts-of-linux-for-MUSE-N1-board.patch
ApplyOptionalPatch 0593-clear-compile-warning.patch
ApplyOptionalPatch 0594-clean-compile-warning.patch
ApplyOptionalPatch 0595-clean-compile-warning.patch
ApplyOptionalPatch 0596-clean-compile-warning.patch
ApplyOptionalPatch 0597-clear-compile-warning.patch
ApplyOptionalPatch 0598-usb-ehci-k1x-ci-support-power-management.patch
ApplyOptionalPatch 0599-usb-spacemit_onboard_hub-support-power-management.patch
ApplyOptionalPatch 0600-display-Fix-the-issue-caused-by-alloc-pages-failed.patch
ApplyOptionalPatch 0601-support-2lane-camera-to-draw-when-okay-frontsensor-n.patch
ApplyOptionalPatch 0602-k1-add-kernel-dts-config-for-MUSE-Pi.patch
ApplyOptionalPatch 0603-k1-rproc-fix-bug-in-system-shutdown-process.patch
ApplyOptionalPatch 0604-spi-fix-the-bug-of-accessing-illegal-pointers-when-t.patch
ApplyOptionalPatch 0605-clock-add-rcpu-can-clock.patch
ApplyOptionalPatch 0606-reset-add-rcpu-can-reset.patch
ApplyOptionalPatch 0607-k1-MUSE-Pi-update-card-detection-logic.patch
ApplyOptionalPatch 0608-spi-adding-the-device-node-of-spi2-controller.patch
ApplyOptionalPatch 0609-aud-fix-codec-persistent-noise-issue-when-switch-hdm.patch
ApplyOptionalPatch 0610-v2d-fix-set-clock-rate-timeout.patch
ApplyOptionalPatch 0611-display-fix-hdmi-compatibility-issues.patch
ApplyOptionalPatch 0612-Move-GPU-alloc-page-from-DMA32-to-Normal-zone.patch
ApplyOptionalPatch 0613-k1-pull-up-gpio70-71-for-SATA.patch
ApplyOptionalPatch 0614-k1x-uart-check-uart-dma-function-before-release-uart.patch
ApplyOptionalPatch 0615-nvme-change-the-segment-size-of-io-request-queue-for.patch
ApplyOptionalPatch 0616-wirless-don-t-show-error-when-load-regulatory.db-fai.patch
ApplyOptionalPatch 0617-clock-add-rcpu2-pwm-clock.patch
ApplyOptionalPatch 0618-display-fix-dpu-under-run-issues.patch
ApplyOptionalPatch 0619-reset-add-rcpu2-pwm-reset.patch
ApplyOptionalPatch 0620-i2s-change-log-level.patch
ApplyOptionalPatch 0621-display-clear-dpu-irq-and-status-after-bootlogo.patch
ApplyOptionalPatch 0622-k1x-support-x60-operate-can-controller-in-rcpu.patch
ApplyOptionalPatch 0623-k1x-deb1-support-rpwm2-for-fan.patch
ApplyOptionalPatch 0624-dtb-k1-x_MUSE-N1-set-otg-mode-for-dwc3.patch
ApplyOptionalPatch 0625-1.increase-command-line-buffer-size-to-2KB.patch
ApplyOptionalPatch 0626-k1x-uart3-fix-compatible-error-in-dts.patch
ApplyOptionalPatch 0627-k1x-wdt-adjust-reboot-handler-timeout.patch
ApplyOptionalPatch 0628-display-add-drm-resume-and-suspend.patch
ApplyOptionalPatch 0629-riscv-dts-correct-isa-string-for-Spacemit-K1.patch
ApplyOptionalPatch 0630-pcie-modify-suspend_noirq-and-resume_noirq-of-k1-pci.patch
ApplyOptionalPatch 0631-k1x-rtc-fix-the-issue-of-probabilistic-failure-on-se.patch
ApplyOptionalPatch 0632-dtb-k1-x-update-quirks-for-usbdrd3.patch
ApplyOptionalPatch 0633-k1-rtc-fix-stack-out-of-bounds-when-open-KASAN.patch
ApplyOptionalPatch 0634-camera-switch-unknow-ioctl-print-level-to-warning.patch
ApplyOptionalPatch 0635-Linux-Integrate-Battery-Driver.patch
ApplyOptionalPatch 0636-USB-xhci-plat-fix-legacy-PHY-double-init.patch
ApplyOptionalPatch 0637-display-add-hdmi-resume-and-suspend.patch
ApplyOptionalPatch 0638-display-fix-hdmi-compatibility-issues.patch
ApplyOptionalPatch 0639-1.change-license-statement-to-GPL-2.0-WITH-Linux-sys.patch
ApplyOptionalPatch 0640-usb-k1x_udc_core-remove-req-from-queue-even-it-s-alr.patch
ApplyOptionalPatch 0641-display-fix-build-warning.patch
ApplyOptionalPatch 0642-display-fix-hdmi-compatibility-issues.patch
ApplyOptionalPatch 0643-pcie-fix-the-compiler-warning.patch
ApplyOptionalPatch 0644-aud-fix-hdmi-sound-card-create-fail-issue.patch
ApplyOptionalPatch 0645-MUSE-N1-pull-down-GPIO-118-and-119-default-for-toggl.patch
ApplyOptionalPatch 0646-add-reboot-mode-select-support-while-P1-reset-will-p.patch
ApplyOptionalPatch 0647-aud-fix-global-out-of-bounds-when-open-KASAN.patch
ApplyOptionalPatch 0648-k1x_MUSE-Pi-add-spi3-pinctrl-config.patch
ApplyOptionalPatch 0649-qspi-fix-the-bug-the-actual-clk-frequency-not-equal-.patch
ApplyOptionalPatch 0650-clock-remove-qspi_clk-fc-bit-setting.patch
ApplyOptionalPatch 0651-rtc-fix-read-rtc-error-when-the-registers-of-pmic-ar.patch
ApplyOptionalPatch 0652-k1-dts-rproc-delete-the-dma-range-property-which-wil.patch
ApplyOptionalPatch 0653-pcie-modify-the-enable-phy-function-for-pcie-resume.patch
ApplyOptionalPatch 0654-k1-i2c-fix-i2c-irq-mask-when-i2c-transfer-timeout.patch
ApplyOptionalPatch 0655-k1-rproc-increase-initialization-level-of-rproc-driv.patch
ApplyOptionalPatch 0656-pcie-supporting-the-link-enters-l2-state-when-suspen.patch
ApplyOptionalPatch 0657-pcie-Add-a-timeout-to-do-while-to-prevent-an-infinit.patch
ApplyOptionalPatch 0658-Linux-Separate-the-I2C-configuration-between-the-boa.patch
ApplyOptionalPatch 0659-dts-enable-hdmi-sound-card-for-deb2-MINI-PC.patch
ApplyOptionalPatch 0660-k1x-dma-fix-dma-tasklet-schedule-bug.patch
ApplyOptionalPatch 0661-Linux-The-integration-of-the-laptop-lid-switch-drive.patch
ApplyOptionalPatch 0662-display-fix-dpu-resume-and-suspend-issues.patch
ApplyOptionalPatch 0663-1.change-kernel-entry-addr-to-0x20_0000.patch
ApplyOptionalPatch 0664-audio-remove-SNDRV_PCM_INFO_PAUSE-support.patch
ApplyOptionalPatch 0665-k1-wireless-disable-power-always-on.patch
ApplyOptionalPatch 0666-display-modify-lcd-gx09inx101-pixel-clock.patch
ApplyOptionalPatch 0667-gpu-fix-failed-to-import-external-image-from-highmem.patch
ApplyOptionalPatch 0668-net-usb-add-asix-usb-nic-driver-ver-v3.1.0.patch
ApplyOptionalPatch 0669-k1-usb-enable-parkmode_disable_ss_quirk-on-DWC3-cont.patch
ApplyOptionalPatch 0670-k1-usb-update-quirks-for-usbdrd3-in-k1-x_MINI-PC.patch
ApplyOptionalPatch 0671-k1-use-ax_usb_nic-instead-of-ax88179_178a.patch
ApplyOptionalPatch 0672-k1-modify-sdio-rx-dline-configuration.patch
ApplyOptionalPatch 0673-audio-fix-hdmiaudio-can-not-playback-after-suspend-r.patch
ApplyOptionalPatch 0674-asix_usb-fix-compile-error.patch
ApplyOptionalPatch 0675-do_trap_insn_illegal-bind-ai-cores-when-use-ai-instr.patch
ApplyOptionalPatch 0676-k1-sync-k1-dtsi-from-linux6.1-dts.patch
ApplyOptionalPatch 0677-k1-cpu-fix-compilation-errs.patch
ApplyOptionalPatch 0678-k1-ccu-add-determine_rate-func.patch
ApplyOptionalPatch 0679-k1-gt9xx-delete-i2c_device_id-args.patch
ApplyOptionalPatch 0680-k1-camera-adjust-class_create.patch
ApplyOptionalPatch 0681-k1-pmic-delect-i2c_device_id-agrs.patch
ApplyOptionalPatch 0682-k1-dma-adjust-vm_flags_set-and-class_create-func.patch
ApplyOptionalPatch 0683-k1-gpio-adjust-struct-gpio_chip.fwnode.patch
ApplyOptionalPatch 0684-k1-usb-goto-valid-identifier.patch
ApplyOptionalPatch 0685-k1-update-k1_defconfig-to-linux-6.6-bringup.patch
ApplyOptionalPatch 0686-emac-change-the-function-of-adjusting-hardware-time-.patch
ApplyOptionalPatch 0687-display-update-config-for-hdmi-compatibility.patch
ApplyOptionalPatch 0688-display-drm-alloc-pages-from-highuser-zone.patch
ApplyOptionalPatch 0689-usb-xhci-plat-read-reset-on-resume-from-device-prope.patch
ApplyOptionalPatch 0690-usb-ehci-k1x-ci-support-reset-on-resume.patch
ApplyOptionalPatch 0691-usb-dwc3-spacemit-add-reset-operation-at-standby-set.patch
ApplyOptionalPatch 0692-k1-i2c-fix-i2c-irq-mask-when-i2c-transfer-timout.patch
ApplyOptionalPatch 0693-k1-udma-add-pte_unmap-to-avoid-sleeping-function-cal.patch
ApplyOptionalPatch 0694-k1-deassert-rpwm-reset-in-resume-ops.patch
ApplyOptionalPatch 0695-pcie-change-the-dependence-of-PCI_K1X_HOST-to-PCI_MS.patch
ApplyOptionalPatch 0696-k1-rproc-enable-rproc-module-to-avoid-bus-hangs-dead.patch
ApplyOptionalPatch 0697-k1-vpu-fix-clk-warning-when-kernel-boot.patch
ApplyOptionalPatch 0698-k1-jpu-fix-compile-error-on-6.6.patch
ApplyOptionalPatch 0699-k1-jpu-enable-jpu.patch
ApplyOptionalPatch 0700-es8326-support-hp-mic-detect-process.patch
ApplyOptionalPatch 0701-sound-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0702-pm-rproc-adjusting-the-sleep-process-level-of-rproc.patch
ApplyOptionalPatch 0703-pm-regulator-set-the-sleep-voltage-of-DCDC1-to-650mv.patch
ApplyOptionalPatch 0704-rproc-do-not-automatically-load-and-start-rcpu.patch
ApplyOptionalPatch 0705-k1-pm-domain-fix-error-in-deleting-qos-nodes-when-di.patch
ApplyOptionalPatch 0706-k1-pm-set-the-sleep-voltage-of-DCDC1-to-650mv.patch
ApplyOptionalPatch 0707-qspi-Fix-the-bug-of-data-transmission-failure-with-a.patch
ApplyOptionalPatch 0708-k1_defconfig-build-cdc_ncm-as-module.patch
ApplyOptionalPatch 0709-phy-k1x-ci-usb2-update-phy-init-sequence-report-erro.patch
ApplyOptionalPatch 0710-usb-dwc3-spacemit-support-phy-setup.patch
ApplyOptionalPatch 0711-k1-usb-setup-phy-in-dwc3-spacemit-instead-of-dwc3.patch
ApplyOptionalPatch 0712-usb-xhci-add-clear-disconnect-for-spacemit-k1x-phy.patch
ApplyOptionalPatch 0713-net-usb-promote-the-priority-of-ax_usb_nic-driver.patch
ApplyOptionalPatch 0714-camera-fix-call_get_fmt-EINVAL-return-to-support-dra.patch
ApplyOptionalPatch 0715-config-enable-kasan-to-memory-debug.patch
ApplyOptionalPatch 0716-k1-ce-fix-ce-compile-errs-and-enable-ce-config.patch
ApplyOptionalPatch 0717-gpu-enable-gpu-in-linux6.6.patch
ApplyOptionalPatch 0718-spacemit-rf-add-missing-includes.patch
ApplyOptionalPatch 0719-k1-enable-RTL8852BS-and-SPACEMIT_RFKILL.patch
ApplyOptionalPatch 0720-mmc-sdhci-of-k1x-add-tuning-windows-type-configurati.patch
ApplyOptionalPatch 0721-k1-change-sdio-max-clock-frequency-to-187MHz.patch
ApplyOptionalPatch 0722-deconfig-enable-aes-engine-to-full-disk-encryption.patch
ApplyOptionalPatch 0723-dts-modify-codec-card-name-config-and-add-mclk_fs-co.patch
ApplyOptionalPatch 0724-muse-book-add-muse-book-board-dts-support.patch
ApplyOptionalPatch 0725-k1-enable-USB_RTL8152.patch
ApplyOptionalPatch 0726-k1-ce-fix-slab-out-of-bounds-by-KASAN-report.patch
ApplyOptionalPatch 0727-display-Update-spacemit-drm-to-linux6.6.patch
ApplyOptionalPatch 0728-v2d-Enable-v2d.patch
ApplyOptionalPatch 0729-ax88179-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0730-clk-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0731-gmac-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0732-rf-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0733-usb-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0734-pinctrl-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0735-crypto-change-file-mode-0755-to-0644.patch
ApplyOptionalPatch 0736-input-change-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0737-spi-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0738-pci-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0739-reset-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0740-adma-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0741-ir-chagne-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0742-pwm-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0743-wdt-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0744-reboot-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0745-dts-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0746-camera-change-file-mode-from-0755-to-0644.patch
ApplyOptionalPatch 0747-k1-spm8821-enable-mask_unmask_non_inverted-property-.patch
ApplyOptionalPatch 0748-dts-set-iomem-the-nomap-propertiers.patch
ApplyOptionalPatch 0749-wireless-support-pcie-wifi-rtl8852be.patch
ApplyOptionalPatch 0750-hdmiaudio-fix-no-sound-after-suspend-resume.patch
ApplyOptionalPatch 0751-dts-change-i2s-target-rate.patch
ApplyOptionalPatch 0752-clock-change-i2s-clock-parent-and-rate.patch
ApplyOptionalPatch 0753-audio-add-mclk-config-flow.patch
ApplyOptionalPatch 0754-dts-add-es8326-snd-card-support-for-MINI-PC.patch
ApplyOptionalPatch 0755-audio-fix-audio-compile-error.patch
ApplyOptionalPatch 0756-k1x-enable-audio-support.patch
ApplyOptionalPatch 0757-audio-fix-i2s-audio-noise-due-to-dmabuffer-is-cached.patch
ApplyOptionalPatch 0758-fix-regulator-do-not-load-the-driver-asynchronously-.patch
ApplyOptionalPatch 0759-kconfig-add-config-ARCH_FORCE_MAX_ORDER-to-fix-defau.patch
ApplyOptionalPatch 0760-riscv-show-reason-of-unaligned-access-speed-are-diff.patch
ApplyOptionalPatch 0761-isa-modify-riscv-isa-format-definition.patch
ApplyOptionalPatch 0762-deconfig-enable-CONFIG_DEBUG-to-more-debug-log.patch
ApplyOptionalPatch 0763-aud-fix-i2s-pointer-pos-to-integer-multiple-of-perio.patch
ApplyOptionalPatch 0764-arch-riscv-boot-dts-Fixed-MUSE-Book-model-to-M1-MUSE.patch
ApplyOptionalPatch 0765-dts-add-orisetech-ota7290b-lcd-panel-1920-1200.patch
ApplyOptionalPatch 0766-qspi-fix-the-warning-when-disable-the-clk-and-bus-cl.patch
ApplyOptionalPatch 0767-k1x-6.6-support-flexcan-on-k1x-platform.patch
ApplyOptionalPatch 0768-arch-riscv-k1_deb1-Added-pwm-fan.patch
ApplyOptionalPatch 0769-dts-sync-the-k1-x_deb1-modify-to-the-k1-x_milkv-jupi.patch
ApplyOptionalPatch 0770-dts-add-milkv-jupiter-board-of-M1.patch
ApplyOptionalPatch 0771-dts-add-SiPEED-LPi3A-board-support.patch
ApplyOptionalPatch 0772-at24-clean-compile-warning.patch
ApplyOptionalPatch 0773-defconfig-update-defconfig.patch
ApplyOptionalPatch 0774-defconfig-support-some-cpufreq-governor.patch
ApplyOptionalPatch 0775-pm-pinctrl-support-edge-detect-wakeup-functoin.patch
ApplyOptionalPatch 0776-spacemit-rf-support-wlan-irq-hostwake.patch
ApplyOptionalPatch 0777-k1-modify-wlan-hostwake-to-pinctl.patch
ApplyOptionalPatch 0778-deconfig-disable-kasan-debug.patch
ApplyOptionalPatch 0779-k1-set-USB0-to-host-mode-for-MUSE-Book.patch
ApplyOptionalPatch 0780-k1-add-wlan-hostwake-config-for-MINI-PC-and-milkv-ju.patch
ApplyOptionalPatch 0781-display-fix-dsi-dphy-hs-prepare-and-hs-zero-cycle.patch
ApplyOptionalPatch 0782-display-reserve-hdmi-compatibility-config-for-chips-.patch
ApplyOptionalPatch 0783-display-modify-the-method-for-obtaining-hdmi-edid.patch
ApplyOptionalPatch 0784-display-support-lt9711-for-mipi-dsi-to-dp.patch
ApplyOptionalPatch 0785-display-remove-debug-log.patch
ApplyOptionalPatch 0786-display-remove-useless-codes-and-fix-edp-driver.patch
ApplyOptionalPatch 0787-display-support-dp-panel.patch
ApplyOptionalPatch 0788-display-modify-edp-brightness-levels.patch
ApplyOptionalPatch 0789-display-support-256-bytes-edid-data-for-hdmi.patch
ApplyOptionalPatch 0790-display-detect-dp-plug-in-and-plug-out.patch
ApplyOptionalPatch 0791-display-modify-the-order-of-the-backlight-for-the-lt.patch
ApplyOptionalPatch 0792-display-do-not-operate-clock-during-the-pm-runtime.patch
ApplyOptionalPatch 0793-display-modify-the-minimum-backlight-brightness-valu.patch
ApplyOptionalPatch 0794-keep-bootloader-logo-on-and-release-backlight-first.patch
ApplyOptionalPatch 0795-display-trun-off-lcd-power-domain-after-the-probe-fu.patch
ApplyOptionalPatch 0796-ccu-fix-rpwm-clk-sel.patch
ApplyOptionalPatch 0797-crypto-reset-and-clock-is-shared-between-crypto-engi.patch
ApplyOptionalPatch 0798-efuse-add-spacemit-efuse-driver.patch
ApplyOptionalPatch 0799-socinfo-add-spacemit-soc-information-driver.patch
ApplyOptionalPatch 0800-dts-support-efuse-and-cpuinfo-module.patch
ApplyOptionalPatch 0801-defconfig-enable-efuse-and-socinfo-module.patch
ApplyOptionalPatch 0802-k1x-adjust-ddr-master-devices-dram_range.patch
ApplyOptionalPatch 0803-dts-modify-pcie-bar-area-layout.patch
ApplyOptionalPatch 0804-ccu-add-pll3-clk-frequency.patch
ApplyOptionalPatch 0805-scripts-package-mkdebian.patch
ApplyOptionalPatch 0806-efuse-add-nvmem-cells-according-to-the-dts.patch
ApplyOptionalPatch 0807-dts-fix-the-error-of-cache-sets-number.patch
ApplyOptionalPatch 0808-gpu-fix-workqueue-warning.patch
ApplyOptionalPatch 0809-k1-support-mult-frequency-table-and-using-one-policy.patch
ApplyOptionalPatch 0810-hdmiaudio-fix-no-sound-issue-on-some-hdmi-display-du.patch
ApplyOptionalPatch 0811-pinctrl-fix-compile-warning.patch
ApplyOptionalPatch 0812-mipi-fix-compile-warninng.patch
ApplyOptionalPatch 0813-i2c-fix-warn_on-when-system-power-off.patch
ApplyOptionalPatch 0814-aud-fix-can-not-play-record-issue-after-suspend-resu.patch
ApplyOptionalPatch 0815-display-release-reserved-memory-for-bootlogo.patch
ApplyOptionalPatch 0816-fs-enable-ubifs-jffs2-and-squashfs.patch
ApplyOptionalPatch 0817-k1-thermal-separate-the-thermal-configuration-and-re.patch
ApplyOptionalPatch 0818-k1x-add-MUSE-Card-dts-support.patch
ApplyOptionalPatch 0819-k1x-add-MUSE-Paper-dts-support.patch
ApplyOptionalPatch 0820-usb-dwc3-support-remote-wakeup.patch
ApplyOptionalPatch 0821-usb-ehci-support-remote-wakeup.patch
ApplyOptionalPatch 0822-usb-dwc3-enable-irqwake-in-dwc3_suspend-instead-of-s.patch
ApplyOptionalPatch 0823-usb-dwc3-enable-linestate1-wakeup-mask.patch
ApplyOptionalPatch 0824-usb-disable-remote-wakeup-default.patch
ApplyOptionalPatch 0825-phy-k1x-ci-otg-adjust-Makefile-order.patch
ApplyOptionalPatch 0826-bluetooth-use-kernel-btrtl-for-8852bu-instead-of-rtk.patch
ApplyOptionalPatch 0827-phy-spacemit-k1x-combphy-add-suspend-term-quirk.patch
ApplyOptionalPatch 0828-k1x-adjust-crypto-alloc-buffer-and-set-mask-turns.patch
ApplyOptionalPatch 0829-riscv-dts-spacemit-fix-PCIe-lane-number-for-deb1.patch
ApplyOptionalPatch 0830-pinctrl-modify-some-pins-pull-configurations.patch
ApplyOptionalPatch 0831-spacemit-rf-modify-default-value-of-poweron-delay.patch
ApplyOptionalPatch 0832-k1-MUSE-Pi-update-sdio-tx-delaycode.patch
ApplyOptionalPatch 0833-mmc-sdhci-of-k1x-fix-cpufreq-while-execute-sw-tuning.patch
ApplyOptionalPatch 0834-m1-milkv-jupiter-specify-cpufreq-during-sdio-rx-tuni.patch
ApplyOptionalPatch 0835-camera-move-spacemit-bifmode-enable-from-dtsi-to-dts.patch
ApplyOptionalPatch 0836-MUSE-Paper-remove-hdmiaudio-support.patch
ApplyOptionalPatch 0837-k1-MUSE-Pi-update-sdio-tx-delaycode-to-0x30.patch
ApplyOptionalPatch 0838-uart0-dts-add-uart-controller-configuration-for-open.patch
ApplyOptionalPatch 0839-k1-cpufreq-using-the-default-vf-table-of-we-did-not-.patch
ApplyOptionalPatch 0840-k1x-adjust-buck4-ldo1-7-suspend-voltage-to-0V.patch
ApplyOptionalPatch 0841-k1x-MINIPC-adjust-ldo1-to-always-on-for-secjtag-TRST.patch
ApplyOptionalPatch 0842-uart-clean-debug-info.patch
ApplyOptionalPatch 0843-jpu-clean-debug-info.patch
ApplyOptionalPatch 0844-pcie-clean-debug-info.patch
ApplyOptionalPatch 0845-sound-clean-debug-info.patch
ApplyOptionalPatch 0846-k1x-fix-dldo1-always-on-to-aldo1-always-on.patch
ApplyOptionalPatch 0847-change-error-to-warning-when-frequency-table-is-full.patch
ApplyOptionalPatch 0848-Add-support-for-ICM42607-sensor.patch
ApplyOptionalPatch 0849-camera-sync-code-from-linux-6.1.patch
ApplyOptionalPatch 0850-k1-pm-domain-disable-wakeup5-by-default.patch
ApplyOptionalPatch 0851-k1-pm-close-some-dcdc-ldo-to-optimize-sleep-power-co.patch
ApplyOptionalPatch 0852-Linux-Open-jffs2-and-squash-support.patch
ApplyOptionalPatch 0853-Linux-For-the-Power-button-shutdown-add-support-for-.patch
ApplyOptionalPatch 0854-To-ensure-a-better-user-experience-set-the-battery-l.patch
ApplyOptionalPatch 0855-To-add-hall-sensor-support-for-Muse-Paper-report-SW_.patch
ApplyOptionalPatch 0856-k1-hotplug-close-the-SCMI-configuration.patch
ApplyOptionalPatch 0857-pcie-supporting-PCIe-interface-power-management.patch
ApplyOptionalPatch 0858-clock-add-rcpu-i2c-clock.patch
ApplyOptionalPatch 0859-reset-add-rcpu-i2c-reset.patch
ApplyOptionalPatch 0860-gmac-supporting-ptp-with-hardware-timestamp.patch
ApplyOptionalPatch 0861-display-modify-panel-backlight-level.patch
ApplyOptionalPatch 0862-display-add-panel-notifier-event-for-spacemit.patch
ApplyOptionalPatch 0863-display-add-mipi-lcd-icnl9951r.patch
ApplyOptionalPatch 0864-display-support-mipi-lcd-avee-and-avdd.patch
ApplyOptionalPatch 0865-display-add-resume-and-suspend-for-lt9711-driver.patch
ApplyOptionalPatch 0866-k1-cpufreq-Support-dynamic-switching-of-1.6G-and-1.8.patch
ApplyOptionalPatch 0867-k1-pm-domain-improve-the-detach-operation-of-the-pow.patch
ApplyOptionalPatch 0868-gmac-fixed-the-bug-that-Ethernet-phy-cannot-enter-lo.patch
ApplyOptionalPatch 0869-k1x-add-MUSE-Paper-mini-4g-dts-support.patch
ApplyOptionalPatch 0870-clock-fix-can-not-get-correct-rate-issue.patch
ApplyOptionalPatch 0871-pcie-modify-the-phy-initialization-for-pcie-controll.patch
ApplyOptionalPatch 0872-k1-x_MUSE-Book-not-reset-usb-during-suspend.patch
ApplyOptionalPatch 0873-k1-MUSE-Paper-update-dts-enable-usb-and-wifi.patch
ApplyOptionalPatch 0874-k1-MUSE-Paper-enable-uart2-for-bluetooth.patch
ApplyOptionalPatch 0875-k1-MUSE-Paper-update-card-detection-logic.patch
ApplyOptionalPatch 0876-ehci-k1x-ci-fix-multiple-instance-debugfs-conflict.patch
ApplyOptionalPatch 0877-mingo-change-u3-role-switch-default-mode-to-host.patch
ApplyOptionalPatch 0878-spi-nor-supporting-FM25Q64AI3-spi-nor-flash.patch
ApplyOptionalPatch 0879-k1x-i2c1-i2c6-apply-for-the-same-pin-delete-i2c1.patch
ApplyOptionalPatch 0880-k1x-fix-crypto-buffer-data-copy-method.patch
ApplyOptionalPatch 0881-dts-adding-the-power-switch-of-wifi-and-bt-on-kx312.patch
ApplyOptionalPatch 0882-dts-adding-the-power-switch-of-wifi-and-bt-on-MUSE-B.patch
ApplyOptionalPatch 0883-this-is-not-pcie-patch-Revert-pcie-clean-debug-info.patch
ApplyOptionalPatch 0884-pcie-clean-debug-info.patch
ApplyOptionalPatch 0885-pcie-fix-the-bug-that-Samsung-nvme-ssd-link-establis.patch
ApplyOptionalPatch 0886-k1x-disable-watchdog.patch
ApplyOptionalPatch 0887-arch-riscv-boot-dts-Enable-MUSE-Book-eeprom-by-defau.patch
ApplyOptionalPatch 0888-k1-x_lpi3a.dts-change-usb2.0otg-port-to-device-mode.patch
ApplyOptionalPatch 0889-k1-x_lpi3a.dts-fix-no-interrupt-of-ctp.patch
ApplyOptionalPatch 0890-k1_deconfig-add-i2c-gpio-expander-PCA953X-driver.patch
ApplyOptionalPatch 0891-codec-add-es7210-driver.patch
ApplyOptionalPatch 0892-codec-add-es8156-driver.patch
ApplyOptionalPatch 0893-dts-fix-JD9365DA-10.1-inch-lcd-cann-t-display-for-lp.patch
ApplyOptionalPatch 0894-as1911-change-file-mode-to-0644.patch
ApplyOptionalPatch 0895-k1-pm-rproc-put-the-de-assert-of-rproc-s-clock-into-.patch
ApplyOptionalPatch 0896-dtsi-k1-add-otg1-support-add-wakeup_reg-reg.patch
ApplyOptionalPatch 0897-k1x_udc_core-fix-global-variable-and-extcon.patch
ApplyOptionalPatch 0898-phy-k1x-ci-otg-refactor-otg-logic-to-support-more-us.patch
ApplyOptionalPatch 0899-ehci-k1x-ci-fix-otg-suspend-resume-and-pm_runtime.patch
ApplyOptionalPatch 0900-k1_defconfig-enable-otg-support.patch
ApplyOptionalPatch 0901-k1-milkv-jupiter-update-sdio-tx-delaycode-to-0x30.patch
ApplyOptionalPatch 0902-Linux-Add-a-virtual-charger-driver.This-resolves-the.patch
ApplyOptionalPatch 0903-display-fix-the-issue-of-bootlogo-flashing-screen.patch
ApplyOptionalPatch 0904-gmac-set-mac_managed_pm-to-true-to-fix-mdio-resume-w.patch
ApplyOptionalPatch 0905-MUSE-N1-u3-set-the-default-mode-to-host-1.so-2.5G-et.patch
ApplyOptionalPatch 0906-adma-fix-compile-warning.patch
ApplyOptionalPatch 0907-k1x-flexcan-do-ram-init-by-iowrite32-instead-of-mems.patch
ApplyOptionalPatch 0908-thermal-add-hwmon-sysfs-node-for-some-debug-tools.patch
ApplyOptionalPatch 0909-thermal-fix-compile-error-because-of-sysfs-register-.patch
ApplyOptionalPatch 0910-k1x-support-cw2015-driver.patch
ApplyOptionalPatch 0911-defconfig-update-kernel-default-configuration.patch
ApplyOptionalPatch 0912-clock-add-rcpu-ir-uart0-uart1-ssp-clocks.patch
ApplyOptionalPatch 0913-reset-add-rcpu-ir-uart0-uart1-ssp-resets.patch
ApplyOptionalPatch 0914-display-fix-compile-warning.patch
ApplyOptionalPatch 0915-camera-fix-compile-warning.patch
ApplyOptionalPatch 0916-crypto-fix-compile-warning.patch
ApplyOptionalPatch 0917-vpu-fix-compile-warning.patch
ApplyOptionalPatch 0918-reset-fix-compile-warning.patch
ApplyOptionalPatch 0919-cpufreq-fix-compile-warning.patch
ApplyOptionalPatch 0920-spi-fix-compile-warning.patch
ApplyOptionalPatch 0921-usb-fix-compiler-warning.patch
ApplyOptionalPatch 0922-clock-fix-compile-warning.patch
ApplyOptionalPatch 0923-gmac-fix-compiler-warning.patch
ApplyOptionalPatch 0924-codec-fix-compile-warning.patch
ApplyOptionalPatch 0925-k1-muse_book-support-hall-to-wakeup-system.patch
ApplyOptionalPatch 0926-usb-typec-husb239-support-hynetek-husb239.patch
ApplyOptionalPatch 0927-k1-defconfig-support-husb239-typec-controller.patch
ApplyOptionalPatch 0928-k1x-x60-can-and-rcpu-can-separate.patch
ApplyOptionalPatch 0929-k1-MUSE-Paper-support-husb239-typec-controller.patch
ApplyOptionalPatch 0930-ai-fix-error-in-bind-ai-task-to-ai-core.patch
ApplyOptionalPatch 0931-phy-k1x-ci-usb2-add-set_suspend-op.patch
ApplyOptionalPatch 0932-phy-k1x-ci-otg-set-role-to-default-role-in-probe.patch
ApplyOptionalPatch 0933-k1-x_MUSE-Pi-enable-otg1-and-set-dwc3-to-drd-mode.patch
ApplyOptionalPatch 0934-k1-x_MUSE-Book-enable-otg-for-usb0.patch
ApplyOptionalPatch 0935-k1x-support-rcpu-uart1-function-through-x60.patch
ApplyOptionalPatch 0936-k1-i2c-support-i2c-driver-of-rcpu-domain.patch
ApplyOptionalPatch 0937-spacemit_onboard_hub-add-pm-domain-support.patch
ApplyOptionalPatch 0938-dwc3-spacemit-add-pm-domain-support.patch
ApplyOptionalPatch 0939-dtsi-k1-update-usb-power-domain-settings.patch
ApplyOptionalPatch 0940-display-fix-the-issue-while-the-i2c-communication-is.patch
ApplyOptionalPatch 0941-insmod-simplify-section-header-process-for-optimize-.patch
ApplyOptionalPatch 0942-k1-pinctrl-we-d-better-clean-the-edge-detect-pending.patch
ApplyOptionalPatch 0943-k1x-i2c-add-one-callback-of-power-off.patch
ApplyOptionalPatch 0944-k1-x_MUSE-Paper-mini-4g-camera-verify-ok.patch
ApplyOptionalPatch 0945-display-add-mipi-lcd-jd9365dah3.patch
ApplyOptionalPatch 0946-display-add-hdmi-notifier-event-for-spacemit.patch
ApplyOptionalPatch 0947-k1-power-key-don-t-report-the-event-of-power-key-whe.patch
ApplyOptionalPatch 0948-k1-MUSE-Paper-mini-4g-update-dts-enable-typec-and-wi.patch
ApplyOptionalPatch 0949-usb-typec-husb239-fix-possible-NULL-pointer-derefere.patch
ApplyOptionalPatch 0950-k1-serial-register-freeze-restore-callback-for-hiber.patch
ApplyOptionalPatch 0951-MUSE-Paper-mini-4g-enable-codec-snd-card-support.patch
ApplyOptionalPatch 0952-clear-some-boot-error-without-including-these-dtsi.patch
ApplyOptionalPatch 0953-pcie-Add-request-operation-before-gpio-operation.patch
ApplyOptionalPatch 0954-k1x-flexcan-fix-clock-frequency-config-and-clk-set.patch
ApplyOptionalPatch 0955-arch-riscv-configs-Update-k1_defconfig.patch
ApplyOptionalPatch 0956-k1x-support-rcpu-ir.patch
ApplyOptionalPatch 0957-asix_usb-fix-netdev-dev_addr_shadow-not-set.patch
ApplyOptionalPatch 0958-k1-MUSE-Paper-mini-4g-update-modules_usrload.patch
ApplyOptionalPatch 0959-mmc-sdhci-of-k1x-use-remove_new-instead-of-remove.patch
ApplyOptionalPatch 0960-phy-k1x-ci-otg-fix-shared-reset-assert-warning.patch
ApplyOptionalPatch 0961-spacemit-rf-introduce-spacemit-rfkill-driver.patch
ApplyOptionalPatch 0962-k1-x_MUSE-Paper-mini-4g-add-4g-module-support.patch
ApplyOptionalPatch 0963-pcie-Set-the-vendor-id-and-device-id-of-k1x-pcie-rc.patch
ApplyOptionalPatch 0964-qmi_wwan_f-add-fibocom-qmi-modem-driver.patch
ApplyOptionalPatch 0965-k1_defconfig-enable-qmi_wwan_f-as-module.patch
ApplyOptionalPatch 0966-defconfig-enable-CONFIG_MTD_CMDLINE_PARTS.patch
ApplyOptionalPatch 0967-k1x-turn-on-ir-spacemit-defconfig.patch
ApplyOptionalPatch 0968-sbs-charger-change-file-mode-0755-0644.patch
ApplyOptionalPatch 0969-k1-cpufreq-using-on-v-f-table-to-support-k1-m1-chip.patch
ApplyOptionalPatch 0970-k1-cpufreq-delete-the-boost-related-node-for-k1.patch
ApplyOptionalPatch 0971-k1-thermal-using-one-thermal-table-for-both-m1-k1.patch
ApplyOptionalPatch 0972-k1_defconfig-add-USB-Audio-UAC-devices-support.patch
ApplyOptionalPatch 0973-k1-alsa-alsa-driver-adds-audio-data-dump.patch
ApplyOptionalPatch 0974-spacemit_onboard_hub-fix-Kconfig-dependancy.patch
ApplyOptionalPatch 0975-gpu-Fix-building-error-with-FORTIFY_SOURCE-enabled.patch
ApplyOptionalPatch 0976-k1-thermal-fix-the-issue-where-the-frequency-cannot-.patch
ApplyOptionalPatch 0977-pcie-print-MSIX_AFIFO_FULL-information-once.patch
ApplyOptionalPatch 0978-deconfig-enable-spinlock_debug.patch
ApplyOptionalPatch 0979-MUSE-Paper-mini-support-battery-profile.patch
ApplyOptionalPatch 0980-MUSE-Paper-mini-support-some-sensor.patch
ApplyOptionalPatch 0981-k1x_udc_core-fix-missing-STATUS-IN-in-control-out-tr.patch
ApplyOptionalPatch 0982-k1x_udc_core-fix-enable-after-disable-may-fail.patch
ApplyOptionalPatch 0983-k1x_udc_core-fix-high-bandwidth-isoc-endpoint-transf.patch
ApplyOptionalPatch 0984-k1x_udc_core-cleanup-info-print.patch
ApplyOptionalPatch 0985-usb-typec-husb239-support-mic-switch.patch
ApplyOptionalPatch 0986-usb-typec-husb239-update-pd-contract.patch
ApplyOptionalPatch 0987-display-reduce-panel-lt8911exb-resume-time.patch
ApplyOptionalPatch 0988-lpi3a-add-aic8800-wifi-support.patch
ApplyOptionalPatch 0989-camera-fix-unknown-type-compile-error-and-comment-sl.patch
ApplyOptionalPatch 0990-spacemit-rf-use-gpiod_set_value_cansleep-instead-of-.patch
ApplyOptionalPatch 0991-display-fix-the-issue-of-bootlogo-flashing-screen.patch
ApplyOptionalPatch 0992-k1-pm_domain-lcd-don-t-open-the-power-switch-again-i.patch
ApplyOptionalPatch 0993-camera-perfect-open-close-node-in-pinmulti-mode.patch
ApplyOptionalPatch 0994-k1-update-sd-sdio-tx-delaycode.patch
ApplyOptionalPatch 0995-usb-f_uvc-use-GFP_DMA32-for-vb2_queue-at-spacemit-k1.patch
ApplyOptionalPatch 0996-k1x-adc-p1-supprt-adc-driver-for-k1x.patch
ApplyOptionalPatch 0997-display-add-plane-cursor-type-and-support-crop.patch
ApplyOptionalPatch 0998-add-baton-camera-solution.patch
ApplyOptionalPatch 0999-dts-add-k1-x_FusionOne-for-eli-NAS.patch
ApplyOptionalPatch 1000-k1-suspend-skip-system-sync-in-kernel.patch
ApplyOptionalPatch 1001-k1x-support-touchscreen-chipone-tddi.patch
ApplyOptionalPatch 1002-k1x-support-sgm41515-charger-driver.patch
ApplyOptionalPatch 1003-k1-reboot-add-a-flag-indicating-whether-to-shutdown-.patch
ApplyOptionalPatch 1004-MUSE-Paper-support-volume-up-dowm-key-event.patch
ApplyOptionalPatch 1005-hung-task-set-hung-timeout-120s.patch
ApplyOptionalPatch 1006-add-new-pinctrl-node-for-FusionOne-to-support-wifi-s.patch
ApplyOptionalPatch 1007-soc-support-notifier-among-modules.patch
ApplyOptionalPatch 1008-usb-typec-husb239-add-notifier-event-for-typec-heads.patch
ApplyOptionalPatch 1009-cpuidle-delete-the-dts-node-for-cpuidle.patch
ApplyOptionalPatch 1010-clock-add-dpll-and-ddr-clocks.patch
ApplyOptionalPatch 1011-usb-typec-husb239-add-vdd-supply-and-usb2-switch.patch
ApplyOptionalPatch 1012-mmc-sdhci-of-k1x-avoid-recovery-sdr104-while-dts-dis.patch
ApplyOptionalPatch 1013-enable-typec-for-FusionOne.patch
ApplyOptionalPatch 1014-muse-paper-sync-camera-draw-dts-configuration.patch
ApplyOptionalPatch 1015-k1-dts-add-all-disabled-usb-nodes.patch
ApplyOptionalPatch 1016-blk-add-request-completion-flags-for-debug.patch
ApplyOptionalPatch 1017-deconfig-enable-CONFIG_LOCKDEP-for-debug.patch
ApplyOptionalPatch 1018-display-fix-the-issue-of-trace-during-system-sleep-a.patch
ApplyOptionalPatch 1019-sound-support-build-module.patch
ApplyOptionalPatch 1020-defconfig-add-audio-config.patch
ApplyOptionalPatch 1021-Bluetooth-btrtl-fix-oops-in-btrtl_vendor_read_reg16.patch
ApplyOptionalPatch 1022-k1-pm_domain-fix-bug-when-device-detach-from-pm-doma.patch
ApplyOptionalPatch 1023-serial-fix-lockdep_assert-warning.patch
ApplyOptionalPatch 1024-nvme-expose-allocation-or-mapping-failure-reports.patch
ApplyOptionalPatch 1025-Fix-dma_buf-warning-with-enabled-lockdep.patch
ApplyOptionalPatch 1026-camera-Fix-dma_buf-warning-with-enabled-lockdep.patch
ApplyOptionalPatch 1027-vpu-Fix-dma_buf-warning-with-enabled-lockdep.patch
ApplyOptionalPatch 1028-jpu-Fix-dma_buf-warning-with-enabled-lockdep.patch
ApplyOptionalPatch 1029-v2d-fix-dmabuf-warning-with-enabled-lockdep.patch
ApplyOptionalPatch 1030-display-modify-the-initcall-sequence-of-the-hdmi-dri.patch
ApplyOptionalPatch 1031-dts-modify-hdmiaudio-config.patch
ApplyOptionalPatch 1032-sound-change-from-late_initcall_sync-to-late_initcal.patch
ApplyOptionalPatch 1033-hdmiaudio-support-hot-plug.patch
ApplyOptionalPatch 1034-display-adjust-resolution-to-60Hz.patch
ApplyOptionalPatch 1035-ir-fix-global-out-of-bounds-when-KASAN-enable.patch
ApplyOptionalPatch 1036-k1x-chipone-tddi-reduce-init-log-level.patch
ApplyOptionalPatch 1037-disable-the-function-that-auto-switch-usb-mode-at-Fu.patch
ApplyOptionalPatch 1038-dts-add-orangepi-rv2-solution.patch
ApplyOptionalPatch 1039-orangepi-rv2-add-usb-ctl-adaptation.patch
ApplyOptionalPatch 1040-k1-hall-support-separating-wake-up-interrupts-from-n.patch
ApplyOptionalPatch 1041-k1-pwr-key-support-wakeup-count.patch
ApplyOptionalPatch 1042-k1x-fix-xts-aes-key2-error.patch
ApplyOptionalPatch 1043-mmc-sdhci-of-k1x-support-MMC1-debug-as-uart0.patch
ApplyOptionalPatch 1044-k1-MUSE-Paper-add-SD-debug-pinctrl.patch
ApplyOptionalPatch 1045-stacktrace-delect-KASAN-warning.patch
ApplyOptionalPatch 1046-gpu-fix-slab-use-after-free-err.patch
ApplyOptionalPatch 1047-k1x-support-ddr-bandwidth-tool-driver.patch
ApplyOptionalPatch 1048-dts-MUSE-Pi-remove-cd-inverted-of-sdhci0.patch
ApplyOptionalPatch 1049-k1x-clean-uart-useless-info.patch
ApplyOptionalPatch 1050-add-ili9881c-mipi-to-orangepi-rv2.patch
ApplyOptionalPatch 1051-camera-verify-camera-success.patch
ApplyOptionalPatch 1052-orangepi-rv2-add-es8323-config-and-modify-sound-code.patch
ApplyOptionalPatch 1053-defconfig-support-codec-es8323.patch
ApplyOptionalPatch 1054-usb-typec-husb239-enable-Try.SNK-mechanism.patch
ApplyOptionalPatch 1055-display-fix-mmu-configuration-error-while-tbu-id-is-.patch
ApplyOptionalPatch 1056-k1x-stop-watchdog-before-the-system-suspend-and-reco.patch
ApplyOptionalPatch 1057-k1x-remove-cw2015-useless-info.patch
ApplyOptionalPatch 1058-k1-MUSE-Paper-fix-the-mistake-about-sd-sdio-tx-delay.patch
ApplyOptionalPatch 1059-camera-sync-V5.7-code-and-verify-single_online_test.patch
ApplyOptionalPatch 1060-k1x-update-MUSE-Paper-cw2015-profile.patch
ApplyOptionalPatch 1061-k1x-add-ZT001H-dts-support.patch
ApplyOptionalPatch 1062-vpu-Fix-circular-lock-warning-with-enabled-lockdep.patch
ApplyOptionalPatch 1063-vpu-Fix-amvx-build-error-when-building-amvx-as-modul.patch
ApplyOptionalPatch 1064-k1-add-fanghang-k1-x_uav-dts.patch
ApplyOptionalPatch 1065-riscv-Flush-the-icache-of-all-cores-related-to-the-c.patch
ApplyOptionalPatch 1066-clock-reset-add-rcpu-pwm-clocks-and-resets.patch
ApplyOptionalPatch 1067-k1x-1.fix-gpio74-function2-pwm9-rpwm9-2.add-rpwm0-9-.patch
ApplyOptionalPatch 1068-dts-modify-the-address-space-allocation-of-pcie2_rc.patch
ApplyOptionalPatch 1069-PCI-Add-arch_can_pci_mmap_wc-macro-on-spacemit-k1-so.patch
ApplyOptionalPatch 1070-k1x-support-chsc5xxx-touchpad-driver.patch
ApplyOptionalPatch 1071-k1x-MUSE-Paper-mini-4g-support-charger.patch
ApplyOptionalPatch 1072-k1-x_uav-camera-verify-imx415-okay.patch
ApplyOptionalPatch 1073-defconfig-add-real-time-linux-defconfig.patch
ApplyOptionalPatch 1074-k1_uav-enable-uart-ports.patch
ApplyOptionalPatch 1075-drm-radeon-mask-MSI-on-K1x.patch
ApplyOptionalPatch 1076-radeon-amdgpu-force-32-bit-dma.patch
ApplyOptionalPatch 1077-Radeon-modify-cached-mapping-to-writecombine.patch
ApplyOptionalPatch 1078-k1-add-radeon-module-in-k1_defconfig.patch
ApplyOptionalPatch 1079-camera-Fix-isp-and-cpp-build-error-when-building-the.patch
ApplyOptionalPatch 1080-defconfig-disable-LOCKDEP-config.patch
ApplyOptionalPatch 1081-rt-defconfig-config-CONFIG_PREEMPT_RT.patch
ApplyOptionalPatch 1082-mmc-sdhci-of-k1x-fix-bug-about-get-invalid-cpufreq_p.patch
ApplyOptionalPatch 1083-dts-update-k1-x_uav-disabled-some-no-used-moduels-fi.patch
ApplyOptionalPatch 1084-k1-support-decompression-of-zstd-format-file.patch
ApplyOptionalPatch 1085-1.add-clk-reset-to-i2c3-2.enable-rpwm9.patch
ApplyOptionalPatch 1086-cpuinfo-add-uarch-information.patch
ApplyOptionalPatch 1087-k1x-clear-charger-useless-info.patch
ApplyOptionalPatch 1088-es8326-support-headphone-notifier-call-chain.patch
ApplyOptionalPatch 1089-es8326-fix-es8326-no-sound-due-to-data-length-settin.patch
ApplyOptionalPatch 1090-es8326-fix-no-sound-issue-after-suspend-resume.patch
ApplyOptionalPatch 1091-es8326-cleanup-unused-code.patch
ApplyOptionalPatch 1092-es8326-reset-jack-status-when-suspend.patch
ApplyOptionalPatch 1093-riscv-rwonce-add-__READ_ONCE-implementation-for-risc.patch
ApplyOptionalPatch 1094-riscv-spackemit-add-of-node-get-for-process-cpuinfo-.patch
ApplyOptionalPatch 1095-sound-adapt-linux-kernel-new-vision.patch
ApplyOptionalPatch 1096-usb-phy-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1097-usb-dwc3-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1098-usb-udc-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1099-usb-host-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1100-usb-misc-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1101-spi-spacemit-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1102-qspi-spacemit-modify-prototype-of-device-remove-func.patch
ApplyOptionalPatch 1103-crypto-spacemit-replace-strlcpy-with-strscpy.patch
ApplyOptionalPatch 1104-dma-spacemit-adma-modify-prototype-of-device-remove-.patch
ApplyOptionalPatch 1105-dma-spacemit-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1106-spacemit-v2d-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1107-soc-spacemit-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1108-soc-spacemit-pm-fix-error-when-save-context-for-lowp.patch
ApplyOptionalPatch 1109-spacemit-jpu-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1110-spacemit-ddrbw-clear-compile-warnings.patch
ApplyOptionalPatch 1111-remoteproc-spacemit-modify-prototype-of-device-remov.patch
ApplyOptionalPatch 1112-i2c-k1x-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1113-plic-fix-error-on-some-offset-macro-definition.patch
ApplyOptionalPatch 1114-mailbox-spacemit-modify-prototype-of-device-remove-f.patch
ApplyOptionalPatch 1115-extcon-k1x-modify-prototype-of-device-remove-functio.patch
ApplyOptionalPatch 1116-camera-spacemit-modify-prototype-of-device-remove-fu.patch
ApplyOptionalPatch 1117-vpu-spacemit-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1118-ir-spacemit-modify-prototype-of-device-remove-functi.patch
ApplyOptionalPatch 1119-wdt-k1x-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1120-thermal-k1x-modify-prototype-of-device-remove-functi.patch
ApplyOptionalPatch 1121-phy-combphy-clean-compile-warning-because-of-prototy.patch
ApplyOptionalPatch 1122-pxa-k1x-adapt-to-linux-kernel-new-version.patch
ApplyOptionalPatch 1123-power-supply-sbs-modify-prototype-of-device-remove-f.patch
ApplyOptionalPatch 1124-pcie-k1x-porting-to-linux-6.12.patch
ApplyOptionalPatch 1125-nvme-remove-segment-buffer-size-limit.patch
ApplyOptionalPatch 1126-tcm-spacemit-modify-prototype-of-device-remove-funct.patch
ApplyOptionalPatch 1127-flexcan-fix-error-in-flexcan-core-probe-function.patch
ApplyOptionalPatch 1128-emac-k1x-fix-compile-warning-on-function-prototype.patch
ApplyOptionalPatch 1129-stmmac-modify-prototype-of-device-remove-function.patch
ApplyOptionalPatch 1130-ax88179a-porting-to-linux-6.12.patch
ApplyOptionalPatch 1131-usb-qmi_wwan_f-replace-strlcpy-by-strscpy.patch
ApplyOptionalPatch 1132-spi-nor-porting-fmsh-device-driver-to-linux-6.12.patch
ApplyOptionalPatch 1133-drm-spacemit-porting-drm-driver-to-linux-6.12.patch
ApplyOptionalPatch 1134-gpio-k1x-porting-gpio-driver-to-linux-6.12.patch
ApplyOptionalPatch 1135-build-disable-character-output-display-during-the-ke.patch
ApplyOptionalPatch 1136-riscv-restore-vmlinux-target-building-command.patch
ApplyOptionalPatch 1137-wireless-rtl8852be-porting-to-linux-6.12.patch
ApplyOptionalPatch 1138-wireless-rtl8852bs-porting-to-linux-6.12.patch
ApplyOptionalPatch 1139-defconfig-disable-some-modules-which-not-ready.patch
ApplyOptionalPatch 1140-k1-mainline-update-head-files-for-compile-errors.patch
ApplyOptionalPatch 1141-k1-mainline-defconfig-enable-spacemit-ir-driver.patch
ApplyOptionalPatch 1142-k1-mainline-defconfig-enable-codec-es8326-support.patch
ApplyOptionalPatch 1143-k1-mainline-es8326-fix-es8326-compile-and-work-issue.patch
ApplyOptionalPatch 1144-k1-regulator-enable-the-driver-of-regulator.patch
ApplyOptionalPatch 1145-display-resolve-the-issue-of-no-display-on-HDMI.patch
ApplyOptionalPatch 1146-i2c-spacemit-k1-fix-strcpy-func-in-i2c-driver.patch
ApplyOptionalPatch 1147-riscv-k1-defconfig-support-i2c-driver.patch
ApplyOptionalPatch 1148-plic-spacemit-k1-declare-irqchip-of-plic-riscv0.patch
ApplyOptionalPatch 1149-watchdog-spacemit-k1-fix-suspend-enable-judge.patch
ApplyOptionalPatch 1150-gpu-upgrade-to-24.2.patch
ApplyOptionalPatch 1151-gpu-img-rogue-add-judgment-of-linux-version-and-keep.patch
ApplyOptionalPatch 1152-gpu-make-sure-gpu-probe-before-display.patch
ApplyOptionalPatch 1153-drm-img-rogue-porting-gpu-driver-to-linux-6.12.patch
ApplyOptionalPatch 1154-gpu-img-rogue-update-to-linux-6.12-fix-pvr_drm_fops.patch
ApplyOptionalPatch 1155-soc-spacemit-add-prototype-define-for-multi-modules.patch
ApplyOptionalPatch 1156-clk-spacemit-clean-compile-warnings.patch
ApplyOptionalPatch 1157-pinctrl-spacemit-p1-support-pmic-pins.patch
ApplyOptionalPatch 1158-spi-k1-spi-porting-to-linux-6.12.patch
ApplyOptionalPatch 1159-spi-k1-qspi-porting-to-linux-6.12.patch
ApplyOptionalPatch 1160-dwc3-spacemit-fix-compile-warning.patch
ApplyOptionalPatch 1161-usb-gadget-fix-compile-warning.patch
ApplyOptionalPatch 1162-usb-xhci-hub-fix-compile-warnings.patch
ApplyOptionalPatch 1163-wdt-k1-fix-compile-warning.patch
ApplyOptionalPatch 1164-wireless-rtl8852bs-porting-to-linux-6.12.patch
ApplyOptionalPatch 1165-cpufreq-k1-fix-compile-warning.patch
ApplyOptionalPatch 1166-crypto-k1-fix-compile-warning.patch
ApplyOptionalPatch 1167-usbnet-fix-compile-warning.patch
ApplyOptionalPatch 1168-mmc-k1x-fix-compile-warning.patch
ApplyOptionalPatch 1169-v2d-spacemit-fix-compile-warning.patch
ApplyOptionalPatch 1170-power-sgm4154x-reshape-file-style.patch
ApplyOptionalPatch 1171-media-k1x-vpu-porting-to-linux-6.12.patch
ApplyOptionalPatch 1172-media-k1x-camera-porting-to-linux-6.12.patch
ApplyOptionalPatch 1173-drm-k1x-fix-compile-warning.patch
ApplyOptionalPatch 1174-drm-k1x-gpu-fix-compile-warning.patch
ApplyOptionalPatch 1175-riscv-k1-kconfig-update-kernel-configuration.patch
ApplyOptionalPatch 1176-media-k1-vpu-fix-error-on-MODULE_IMPORT_NS-using.patch
ApplyOptionalPatch 1177-mmc-k1-fix-error-of-driver.remove.patch
ApplyOptionalPatch 1178-soc-spacemit-v2d-fix-error-on-MODULE_IMPORT_NS-using.patch
ApplyOptionalPatch 1179-usb-spacemit-k1-fix-compile-error.patch
ApplyOptionalPatch 1180-sound-k1-fix-compile-error.patch
ApplyOptionalPatch 1181-opp-k1-fix-compile-error.patch
ApplyOptionalPatch 1182-can-k1-flexcan-fix-error-on-driver.remove.patch
ApplyOptionalPatch 1183-wireless-rtl8852bs-porting-to-linux-6.13.patch
ApplyOptionalPatch 1184-drm-img-rogue-fix-error-on-MODULE_IMPORT_NS-using.patch
ApplyOptionalPatch 1185-drm-spacemit-porting-to-linux-6.13.patch
ApplyOptionalPatch 1186-camera-fix-compilation-problems-and-run-imx415-in-de.patch
ApplyOptionalPatch 1187-wdt-k1x-fix-MODULE_LICENSE-announce-error.patch
ApplyOptionalPatch 1188-soc-k1-jpu-fix-MODULE_LICENSE-announce-error.patch
ApplyOptionalPatch 1189-thermal-k1-Correct-a-typo-in-the-code.patch
ApplyOptionalPatch 1190-dma-dw-axi-dmac-Correct-a-typo-in-the-code.patch
ApplyOptionalPatch 1191-media-k1-camera-fix-some-compile-warnings.patch
ApplyOptionalPatch 1192-riscv-k1-dts-remove-some-reserved-memory-region.patch
ApplyOptionalPatch 1193-Revert-riscv-Fix-IPIs-usage-in-kfence_protect_page.patch
ApplyOptionalPatch 1194-k1x_rproc-avoid-creating-busy-looping-mailbox-thread.patch
ApplyOptionalPatch 1195-fix-module-dma_buf-ns.patch
ApplyOptionalPatch 1196-fix-wrong-style-comments.patch
ApplyOptionalPatch 1197-Remove-depends-so-PWM_PXA-can-be-enabled.patch
ApplyOptionalPatch 1198-remove-trace_printk.patch
ApplyOptionalPatch 1199-remove-unused-var.patch
ApplyOptionalPatch 1200-Remove-depends-so-SERIAL_8250_PXA-can-be-enabled.patch
ApplyOptionalPatch 1201-fix-includes-for-timestamp.patch
ApplyOptionalPatch 1202-remove-debug-rdinit-from-m1-bpi.patch
ApplyOptionalPatch 1203-6.14-fixes-to-spacemit_drm-and-pvr_drm.patch
ApplyOptionalPatch 1204-Add-bit-brick-k1-devicetree-from-bianbu.patch
ApplyOptionalPatch 1205-Add-minimal-hacked-up-OrangePI-RV2-devicetree.patch
ApplyOptionalPatch 1206-6.15-fixes.patch
ApplyOptionalPatch 1207-Add-distinct-compatibles-for-boards-currently-used-f.patch
ApplyOptionalPatch 1208-fix-build-issue-k1x_cpp.c-1453-18-error-expected-or-.patch
ApplyOptionalPatch 1209-fix-issue-https-github.com-jmontleon-linux-bianbu-is.patch
ApplyOptionalPatch 1210-RTL8852-6.15-fixes.patch
ApplyOptionalPatch 1211-Add-minimal-hacked-up-OrangePi-R2S-devicetree.patch





%endif

ApplyOptionalPatch linux-kernel-test.patch

%{log_msg "End of patch applications"}
# END OF PATCH APPLICATIONS

# Any further pre-build tree manipulations happen here.
%{log_msg "Pre-build tree manipulations"}
chmod +x scripts/checkpatch.pl
mv COPYING COPYING-%{specrpmversion}-%{release}

# on linux-next prevent scripts/setlocalversion from mucking with our version numbers
rm -f localversion-next localversion-rt

# Mangle /usr/bin/python shebangs to /usr/bin/python3
# Mangle all Python shebangs to be Python 3 explicitly
# -p preserves timestamps
# -n prevents creating ~backup files
# -i specifies the interpreter for the shebang
# This fixes errors such as
# *** ERROR: ambiguous python shebang in /usr/bin/kvm_stat: #!/usr/bin/python. Change it to python3 (or python2) explicitly.
# We patch all sources below for which we got a report/error.
%{log_msg "Fixing Python shebangs..."}
%py3_shebang_fix \
	tools/kvm/kvm_stat/kvm_stat \
	scripts/show_delta \
	scripts/diffconfig \
	scripts/bloat-o-meter \
	scripts/jobserver-exec \
	tools \
	Documentation \
	scripts/clang-tools 2> /dev/null

# only deal with configs if we are going to build for the arch
%ifnarch %nobuildarches

if [ -L configs ]; then
	rm -f configs
fi
mkdir configs
cd configs

%{log_msg "Copy additional source files into buildroot"}
# Drop some necessary files from the source dir into the buildroot
cp $RPM_SOURCE_DIR/%{name}-*.config .
cp %{SOURCE80} .
# merge.py
cp %{SOURCE3000} .
# kernel-local - rename and copy for partial snippet config process
cp %{SOURCE3001} partial-kernel-local-snip.config
cp %{SOURCE3001} partial-kernel-local-debug-snip.config
FLAVOR=%{primary_target} SPECPACKAGE_NAME=%{name} SPECVERSION=%{specversion} SPECRPMVERSION=%{specrpmversion} ./generate_all_configs.sh %{debugbuildsenabled}

# Collect custom defined config options
%{log_msg "Collect custom defined config options"}
PARTIAL_CONFIGS=""
%if %{with_gcov}
PARTIAL_CONFIGS="$PARTIAL_CONFIGS %{SOURCE70} %{SOURCE71}"
%endif
%if %{with toolchain_clang}
PARTIAL_CONFIGS="$PARTIAL_CONFIGS %{SOURCE72} %{SOURCE73}"
%endif
%if %{with clang_lto}
PARTIAL_CONFIGS="$PARTIAL_CONFIGS %{SOURCE74} %{SOURCE75} %{SOURCE76} %{SOURCE77}"
%endif
PARTIAL_CONFIGS="$PARTIAL_CONFIGS partial-kernel-local-snip.config partial-kernel-local-debug-snip.config"

GetArch()
{
  case "$1" in
  *aarch64*) echo "aarch64" ;;
  *ppc64le*) echo "ppc64le" ;;
  *s390x*) echo "s390x" ;;
  *x86_64*) echo "x86_64" ;;
  *riscv64*) echo "riscv64" ;;
  # no arch, apply everywhere
  *) echo "" ;;
  esac
}

# Merge in any user-provided local config option changes
%{log_msg "Merge in any user-provided local config option changes"}
%ifnarch %nobuildarches
for i in %{all_configs}
do
  kern_arch="$(GetArch $i)"
  kern_debug="$(echo $i | grep -q debug && echo "debug" || echo "")"

  for j in $PARTIAL_CONFIGS
  do
    part_arch="$(GetArch $j)"
    part_debug="$(echo $j | grep -q debug && echo "debug" || echo "")"

    # empty arch means apply to all arches
    if [ "$part_arch" == "" -o "$part_arch" == "$kern_arch" ] && [ "$part_debug" == "$kern_debug" ]
    then
      mv $i $i.tmp
      ./merge.py $j $i.tmp > $i
    fi
  done
  rm -f $i.tmp
done
%endif

%if %{signkernel}%{signmodules}

# Add DUP and kpatch certificates to system trusted keys for RHEL
%if 0%{?rhel}
%{log_msg "Add DUP and kpatch certificates to system trusted keys for RHEL"}
openssl x509 -inform der -in %{SOURCE100} -out rheldup3.pem
openssl x509 -inform der -in %{SOURCE101} -out rhelkpatch1.pem
openssl x509 -inform der -in %{SOURCE102} -out nvidiagpuoot001.pem
cat rheldup3.pem rhelkpatch1.pem nvidiagpuoot001.pem > ../certs/rhel.pem
%if %{signkernel}
%ifarch s390x ppc64le
openssl x509 -inform der -in %{secureboot_ca_0} -out secureboot.pem
cat secureboot.pem >> ../certs/rhel.pem
%endif
%endif

# rhel
%endif

openssl x509 -inform der -in %{ima_ca_cert} -out imaca.pem
cat imaca.pem >> ../certs/rhel.pem

for i in *.config; do
  sed -i 's@CONFIG_SYSTEM_TRUSTED_KEYS=""@CONFIG_SYSTEM_TRUSTED_KEYS="certs/rhel.pem"@' $i
done
%endif

%{log_msg "Set process_configs.sh $OPTS"}
cp %{SOURCE81} .
OPTS=""
%if %{with_configchecks}
	OPTS="$OPTS -w -n -c"
%endif
%if %{with clang_lto}
for opt in %{clang_make_opts}; do
  OPTS="$OPTS -m $opt"
done
%endif
%{log_msg "Generate redhat configs"}
RHJOBS=$RPM_BUILD_NCPUS SPECPACKAGE_NAME=%{name} ./process_configs.sh $OPTS %{specrpmversion}

# We may want to override files from the primary target in case of building
# against a flavour of it (eg. centos not rhel), thus override it here if
# necessary
update_scripts() {
	TARGET="$1"

	for i in "$RPM_SOURCE_DIR"/*."$TARGET"; do
		NEW=${i%."$TARGET"}
		cp "$i" "$(basename "$NEW")"
	done
}

%{log_msg "Set scripts/SOURCES targets"}
update_target=%{primary_target}
if [ "%{primary_target}" == "rhel" ]; then
: # no-op to avoid empty if-fi error
%if 0%{?centos}
  update_scripts $update_target
  %{log_msg "Updating scripts/sources to centos version"}
  update_target=centos
%endif
fi
update_scripts $update_target

%endif

%{log_msg "End of kernel config"}
cd ..
# # End of Configs stuff

# get rid of unwanted files resulting from patch fuzz
find . \( -name "*.orig" -o -name "*~" \) -delete >/dev/null

# remove unnecessary SCM files
find . -name .gitignore -delete >/dev/null

cd ..

###
### build
###
%build
%{log_msg "Start of build stage"}

%{log_msg "General arch build configuration"}
rm -rf %{buildroot_unstripped} || true
mkdir -p %{buildroot_unstripped}

%if %{with_sparse}
%define sparse_mflags	C=1
%endif

cp_vmlinux()
{
  eu-strip --remove-comment -o "$2" "$1"
}

# Note we need to disable these flags for cross builds because the flags
# from redhat-rpm-config assume that host == target so target arch
# flags cause issues with the host compiler.
%if !%{with_cross}
%define build_hostcflags  %{?build_cflags}
%define build_hostldflags %{?build_ldflags}
%endif

%define make %{__make} %{?cross_opts} %{?make_opts} HOSTCFLAGS="%{?build_hostcflags}" HOSTLDFLAGS="%{?build_hostldflags}"

InitBuildVars() {
    %{log_msg "InitBuildVars for $1"}

    %{log_msg "InitBuildVars: Initialize build variables"}
    # Initialize the kernel .config file and create some variables that are
    # needed for the actual build process.

    Variant=$1

    # Pick the right kernel config file
    Config=%{name}-%{specrpmversion}-%{_target_cpu}${Variant:+-${Variant}}.config
    DevelDir=/usr/src/kernels/%{KVERREL}${Variant:++${Variant}}

    KernelVer=%{specversion}-%{release}.%{_target_cpu}${Variant:++${Variant}}

    %{log_msg "InitBuildVars: Update Makefile"}
    # make sure EXTRAVERSION says what we want it to say
    # Trim the release if this is a CI build, since KERNELVERSION is limited to 64 characters
    ShortRel=$(perl -e "print \"%{release}\" =~ s/\.pr\.[0-9A-Fa-f]{32}//r")
    perl -p -i -e "s/^EXTRAVERSION.*/EXTRAVERSION = -${ShortRel}.%{_target_cpu}${Variant:++${Variant}}/" Makefile

    # if pre-rc1 devel kernel, must fix up PATCHLEVEL for our versioning scheme
    # if we are post rc1 this should match anyway so this won't matter
    perl -p -i -e 's/^PATCHLEVEL.*/PATCHLEVEL = %{patchlevel}/' Makefile

    %{log_msg "InitBuildVars: Copy files"}
    %{make} %{?_smp_mflags} mrproper
    cp configs/$Config .config

    %if %{signkernel}%{signmodules}
    cp configs/x509.genkey certs/.
    %endif

%if %{with_debuginfo} == 0
    sed -i 's/^\(CONFIG_DEBUG_INFO.*\)=y/# \1 is not set/' .config
%endif

    Arch=`head -1 .config | cut -b 3-`
    %{log_msg "InitBuildVars: USING ARCH=$Arch"}

    KCFLAGS="%{?kcflags}"
}

#Build bootstrap bpftool
BuildBpftool(){
    export BPFBOOTSTRAP_CFLAGS=$(echo "%{__global_compiler_flags}" | sed -r "s/\-specs=[^\ ]+\/redhat-annobin-cc1//")
    export BPFBOOTSTRAP_LDFLAGS=$(echo "%{__global_ldflags}" | sed -r "s/\-specs=[^\ ]+\/redhat-annobin-cc1//")
    CFLAGS="" LDFLAGS="" make EXTRA_CFLAGS="${BPFBOOTSTRAP_CFLAGS}" EXTRA_CXXFLAGS="${BPFBOOTSTRAP_CFLAGS}" EXTRA_LDFLAGS="${BPFBOOTSTRAP_LDFLAGS}" %{?make_opts} %{?clang_make_opts} V=1 -C tools/bpf/bpftool bootstrap
}

BuildKernel() {
    %{log_msg "BuildKernel for $4"}
    MakeTarget=$1
    KernelImage=$2
    DoVDSO=$3
    Variant=$4
    InstallName=${5:-vmlinuz}

    %{log_msg "Setup variables"}
    DoModules=1
    if [ "$Variant" = "zfcpdump" ]; then
	    DoModules=0
    fi

    # When the bootable image is just the ELF kernel, strip it.
    # We already copy the unstripped file into the debuginfo package.
    if [ "$KernelImage" = vmlinux ]; then
      CopyKernel=cp_vmlinux
    else
      CopyKernel=cp
    fi

%if %{with_gcov}
    %{log_msg "Setup build directories"}
    # Make build directory unique for each variant, so that gcno symlinks
    # are also unique for each variant.
    if [ -n "$Variant" ]; then
        ln -s $(pwd) ../linux-%{KVERREL}-${Variant}
    fi
    %{log_msg "GCOV - continuing build in: $(pwd)"}
    pushd ../linux-%{KVERREL}${Variant:+-${Variant}}
    pwd > ../kernel${Variant:+-${Variant}}-gcov.list
%endif

    %{log_msg "Calling InitBuildVars for $Variant"}
    InitBuildVars $Variant

    %{log_msg "BUILDING A KERNEL FOR ${Variant} %{_target_cpu}..."}

    %{make} ARCH=$Arch olddefconfig >/dev/null

    %{log_msg "Setup build-ids"}
    # This ensures build-ids are unique to allow parallel debuginfo
    perl -p -i -e "s/^CONFIG_BUILD_SALT.*/CONFIG_BUILD_SALT=\"%{KVERREL}\"/" .config
    %{make} ARCH=$Arch KCFLAGS="$KCFLAGS" WITH_GCOV="%{?with_gcov}" %{?_smp_mflags} $MakeTarget %{?sparse_mflags} %{?kernel_mflags}
    if [ $DoModules -eq 1 ]; then
	%{make} ARCH=$Arch KCFLAGS="$KCFLAGS" WITH_GCOV="%{?with_gcov}" %{?_smp_mflags} modules %{?sparse_mflags} || exit 1
    fi

    %{log_msg "Setup RPM_BUILD_ROOT directories"}
    mkdir -p $RPM_BUILD_ROOT/%{image_install_path}
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/systemtap
%if %{with_debuginfo}
    mkdir -p $RPM_BUILD_ROOT%{debuginfodir}/%{image_install_path}
%endif

%ifarch aarch64 riscv64
    %{log_msg "Build dtb kernel"}
    %{make} ARCH=$Arch dtbs INSTALL_DTBS_PATH=$RPM_BUILD_ROOT/%{image_install_path}/dtb-$KernelVer
    %{make} ARCH=$Arch dtbs_install INSTALL_DTBS_PATH=$RPM_BUILD_ROOT/%{image_install_path}/dtb-$KernelVer
    cp -r $RPM_BUILD_ROOT/%{image_install_path}/dtb-$KernelVer $RPM_BUILD_ROOT/lib/modules/$KernelVer/dtb
    find arch/$Arch/boot/dts -name '*.dtb' -type f -delete
%endif

    %{log_msg "Cleanup temp btf files"}
    # Remove large intermediate files we no longer need to save space
    # (-f required for zfcpdump builds that do not enable BTF)
    rm -f vmlinux.o .tmp_vmlinux.btf

    %{log_msg "Install files to RPM_BUILD_ROOT"}

    # Comment out specific config settings that may use resources not available
    # to the end user so that the packaged config file can be easily reused with
    # upstream make targets
    %if %{signkernel}%{signmodules}
      sed -i -e '/^CONFIG_SYSTEM_TRUSTED_KEYS/{
        i\# The kernel was built with
        s/^/# /
        a\# We are resetting this value to facilitate local builds
        a\CONFIG_SYSTEM_TRUSTED_KEYS=""
        }' .config
    %endif

    # Start installing the results
    install -m 644 .config $RPM_BUILD_ROOT/boot/config-$KernelVer
    install -m 644 .config $RPM_BUILD_ROOT/lib/modules/$KernelVer/config
    install -m 644 System.map $RPM_BUILD_ROOT/boot/System.map-$KernelVer
    install -m 644 System.map $RPM_BUILD_ROOT/lib/modules/$KernelVer/System.map

    %{log_msg "Reserving 40MB in boot for initramfs"}
    # We estimate the size of the initramfs because rpm needs to take this size
    # into consideration when performing disk space calculations. (See bz #530778)
    dd if=/dev/zero of=$RPM_BUILD_ROOT/boot/initramfs-$KernelVer.img bs=1M count=40

    if [ -f arch/$Arch/boot/zImage.stub ]; then
      %{log_msg "Copy zImage.stub to RPM_BUILD_ROOT"}
      cp arch/$Arch/boot/zImage.stub $RPM_BUILD_ROOT/%{image_install_path}/zImage.stub-$KernelVer || :
      cp arch/$Arch/boot/zImage.stub $RPM_BUILD_ROOT/lib/modules/$KernelVer/zImage.stub-$KernelVer || :
    fi

    %if %{signkernel}
    %{log_msg "Copy kernel for signing"}
    if [ "$KernelImage" = vmlinux ]; then
        # We can't strip and sign $KernelImage in place, because
        # we need to preserve original vmlinux for debuginfo.
        # Use a copy for signing.
        $CopyKernel $KernelImage $KernelImage.tosign
        KernelImage=$KernelImage.tosign
        CopyKernel=cp
    fi

    SignImage=$KernelImage

    %ifarch x86_64 aarch64
    %{log_msg "Sign kernel image"}
    %pesign -s -i $SignImage -o vmlinuz.signed -a %{secureboot_ca_0} -c %{secureboot_key_0} -n %{pesign_name_0}
    %endif
    %ifarch s390x ppc64le
    if [ -x /usr/bin/rpm-sign ]; then
	rpm-sign --key "%{pesign_name_0}" --lkmsign $SignImage --output vmlinuz.signed
    elif [ "$DoModules" == "1" -a "%{signmodules}" == "1" ]; then
	chmod +x scripts/sign-file
	./scripts/sign-file -p sha256 certs/signing_key.pem certs/signing_key.x509 $SignImage vmlinuz.signed
    else
	mv $SignImage vmlinuz.signed
    fi
    %endif

    if [ ! -s vmlinuz.signed ]; then
	%{log_msg "pesigning failed"}
        exit 1
    fi
    mv vmlinuz.signed $SignImage
    # signkernel
    %endif

    %{log_msg "copy signed kernel"}
    $CopyKernel $KernelImage \
                $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer
    chmod 755 $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer
    cp $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer $RPM_BUILD_ROOT/lib/modules/$KernelVer/$InstallName

    # hmac sign the kernel for FIPS
    %{log_msg "hmac sign the kernel for FIPS"}
    %{log_msg "Creating hmac file: $RPM_BUILD_ROOT/%{image_install_path}/.vmlinuz-$KernelVer.hmac"}
    ls -l $RPM_BUILD_ROOT/%{image_install_path}/$InstallName-$KernelVer
    (cd $RPM_BUILD_ROOT/%{image_install_path} && sha512hmac $InstallName-$KernelVer) > $RPM_BUILD_ROOT/%{image_install_path}/.vmlinuz-$KernelVer.hmac;
    cp $RPM_BUILD_ROOT/%{image_install_path}/.vmlinuz-$KernelVer.hmac $RPM_BUILD_ROOT/lib/modules/$KernelVer/.vmlinuz.hmac

    if [ $DoModules -eq 1 ]; then
	%{log_msg "Install modules in RPM_BUILD_ROOT"}
	# Override $(mod-fw) because we don't want it to install any firmware
	# we'll get it from the linux-firmware package and we don't want conflicts
	%{make} %{?_smp_mflags} ARCH=$Arch INSTALL_MOD_PATH=$RPM_BUILD_ROOT %{?_smp_mflags} modules_install KERNELRELEASE=$KernelVer mod-fw=
    fi

%if %{with_gcov}
    %{log_msg "install gcov-needed files to $BUILDROOT/$BUILD/"}
    # install gcov-needed files to $BUILDROOT/$BUILD/...:
    #   gcov_info->filename is absolute path
    #   gcno references to sources can use absolute paths (e.g. in out-of-tree builds)
    #   sysfs symlink targets (set up at compile time) use absolute paths to BUILD dir
    find . \( -name '*.gcno' -o -name '*.[chS]' \) -exec install -D '{}' "$RPM_BUILD_ROOT/$(pwd)/{}" \;
%endif

    %{log_msg "Add VDSO files"}
    # add an a noop %%defattr statement 'cause rpm doesn't like empty file list files
    echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-ldsoconf.list
    if [ $DoVDSO -ne 0 ]; then
        %{make} ARCH=$Arch INSTALL_MOD_PATH=$RPM_BUILD_ROOT vdso_install KERNELRELEASE=$KernelVer
        if [ -s ldconfig-kernel.conf ]; then
             install -D -m 444 ldconfig-kernel.conf \
                $RPM_BUILD_ROOT/etc/ld.so.conf.d/kernel-$KernelVer.conf
	     echo /etc/ld.so.conf.d/kernel-$KernelVer.conf >> ../kernel${Variant:+-${Variant}}-ldsoconf.list
        fi

        rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/vdso/.build-id
    fi

    %{log_msg "Save headers/makefiles, etc. for kernel-headers"}
    # And save the headers/makefiles etc for building modules against
    #
    # This all looks scary, but the end result is supposed to be:
    # * all arch relevant include/ files
    # * all Makefile/Kconfig files
    # * all script/ files

    rm -f $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    rm -f $RPM_BUILD_ROOT/lib/modules/$KernelVer/source
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    (cd $RPM_BUILD_ROOT/lib/modules/$KernelVer ; ln -s build source)
    # dirs for additional modules per module-init-tools, kbuild/modules.txt
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/updates
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/weak-updates
    # CONFIG_KERNEL_HEADER_TEST generates some extra files in the process of
    # testing so just delete
    find . -name *.h.s -delete
    # first copy everything
    cp --parents `find  -type f -name "Makefile*" -o -name "Kconfig*"` $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    if [ ! -e Module.symvers ]; then
        touch Module.symvers
    fi
    cp Module.symvers $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp System.map $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    if [ -s Module.markers ]; then
      cp Module.markers $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    fi

    # create the kABI metadata for use in packaging
    # NOTENOTE: the name symvers is used by the rpm backend
    # NOTENOTE: to discover and run the /usr/lib/rpm/fileattrs/kabi.attr
    # NOTENOTE: script which dynamically adds exported kernel symbol
    # NOTENOTE: checksums to the rpm metadata provides list.
    # NOTENOTE: if you change the symvers name, update the backend too
    %{log_msg "GENERATING kernel ABI metadata"}
    %compression --stdout %compression_flags < Module.symvers > $RPM_BUILD_ROOT/boot/symvers-$KernelVer.%compext
    cp $RPM_BUILD_ROOT/boot/symvers-$KernelVer.%compext $RPM_BUILD_ROOT/lib/modules/$KernelVer/symvers.%compext

%if %{with_kabichk}
    %{log_msg "kABI checking is enabled in kernel SPEC file."}
    chmod 0755 $RPM_SOURCE_DIR/check-kabi
    if [ -e $RPM_SOURCE_DIR/Module.kabi_%{_target_cpu}$Variant ]; then
        cp $RPM_SOURCE_DIR/Module.kabi_%{_target_cpu}$Variant $RPM_BUILD_ROOT/Module.kabi
        $RPM_SOURCE_DIR/check-kabi -k $RPM_BUILD_ROOT/Module.kabi -s Module.symvers || exit 1
        # for now, don't keep it around.
        rm $RPM_BUILD_ROOT/Module.kabi
    else
	%{log_msg "NOTE: Cannot find reference Module.kabi file."}
    fi
%endif

%if %{with_kabidupchk}
    %{log_msg "kABI DUP checking is enabled in kernel SPEC file."}
    if [ -e $RPM_SOURCE_DIR/Module.kabi_dup_%{_target_cpu}$Variant ]; then
        cp $RPM_SOURCE_DIR/Module.kabi_dup_%{_target_cpu}$Variant $RPM_BUILD_ROOT/Module.kabi
        $RPM_SOURCE_DIR/check-kabi -k $RPM_BUILD_ROOT/Module.kabi -s Module.symvers || exit 1
        # for now, don't keep it around.
        rm $RPM_BUILD_ROOT/Module.kabi
    else
	%{log_msg "NOTE: Cannot find DUP reference Module.kabi file."}
    fi
%endif

%if %{with_kabidw_base}
    # Don't build kabi base for debug kernels
    if [ "$Variant" != "zfcpdump" -a "$Variant" != "debug" ]; then
        mkdir -p $RPM_BUILD_ROOT/kabi-dwarf
        tar -xvf %{SOURCE301} -C $RPM_BUILD_ROOT/kabi-dwarf

        mkdir -p $RPM_BUILD_ROOT/kabi-dwarf/stablelists
        tar -xvf %{SOURCE300} -C $RPM_BUILD_ROOT/kabi-dwarf/stablelists

	%{log_msg "GENERATING DWARF-based kABI baseline dataset"}
        chmod 0755 $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh
        $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh generate \
            "$RPM_BUILD_ROOT/kabi-dwarf/stablelists/kabi-current/kabi_stablelist_%{_target_cpu}" \
            "$(pwd)" \
            "$RPM_BUILD_ROOT/kabidw-base/%{_target_cpu}${Variant:+.${Variant}}" || :

        rm -rf $RPM_BUILD_ROOT/kabi-dwarf
    fi
%endif

%if %{with_kabidwchk}
    if [ "$Variant" != "zfcpdump" ]; then
        mkdir -p $RPM_BUILD_ROOT/kabi-dwarf
        tar -xvf %{SOURCE301} -C $RPM_BUILD_ROOT/kabi-dwarf
        if [ -d "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}" ]; then
            mkdir -p $RPM_BUILD_ROOT/kabi-dwarf/stablelists
            tar -xvf %{SOURCE300} -C $RPM_BUILD_ROOT/kabi-dwarf/stablelists

	    %{log_msg "GENERATING DWARF-based kABI dataset"}
            chmod 0755 $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh
            $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh generate \
                "$RPM_BUILD_ROOT/kabi-dwarf/stablelists/kabi-current/kabi_stablelist_%{_target_cpu}" \
                "$(pwd)" \
                "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}.tmp" || :

	    %{log_msg "kABI DWARF-based comparison report"}
            $RPM_BUILD_ROOT/kabi-dwarf/run_kabi-dw.sh compare \
                "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}" \
                "$RPM_BUILD_ROOT/kabi-dwarf/base/%{_target_cpu}${Variant:+.${Variant}}.tmp" || :
	    %{log_msg "End of kABI DWARF-based comparison report"}
        else
	    %{log_msg "Baseline dataset for kABI DWARF-BASED comparison report not found"}
        fi

        rm -rf $RPM_BUILD_ROOT/kabi-dwarf
    fi
%endif

   %{log_msg "Cleanup Makefiles/Kconfig files"}
    # then drop all but the needed Makefiles/Kconfig files
    rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts
    rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include
    cp .config $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a scripts $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    rm -rf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts/tracing
    rm -f $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts/spdxcheck.py

%ifarch s390x
    # CONFIG_EXPOLINE_EXTERN=y produces arch/s390/lib/expoline/expoline.o
    # which is needed during external module build.
    %{log_msg "Copy expoline.o"}
    if [ -f arch/s390/lib/expoline/expoline.o ]; then
      cp -a --parents arch/s390/lib/expoline/expoline.o $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    fi
%endif

    %{log_msg "Copy additional files for make targets"}
    # Files for 'make scripts' to succeed with kernel-devel.
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/security/selinux/include
    cp -a --parents security/selinux/include/classmap.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents security/selinux/include/initial_sid_to_string.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/include/tools
    cp -a --parents tools/include/tools/be_byteshift.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/tools/le_byteshift.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    # Files for 'make prepare' to succeed with kernel-devel.
    cp -a --parents tools/include/linux/compiler* $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/linux/types.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/build/Build.include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/build/fixdep.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/sync-check.sh $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/bpf/resolve_btfids $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    cp --parents security/selinux/include/policycap_names.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents security/selinux/include/policycap.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    cp -a --parents tools/include/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/asm-generic $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/linux $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/uapi/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/uapi/asm-generic $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/uapi/linux $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/include/vdso $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/scripts/utilities.mak $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/lib/subcmd $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/lib/*.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/*.[ch] $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/Build $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/objtool/include/objtool/*.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/lib/bpf $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp --parents tools/lib/bpf/Build $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

    if [ -f tools/objtool/objtool ]; then
      cp -a tools/objtool/objtool $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/objtool/ || :
    fi
    if [ -f tools/objtool/fixdep ]; then
      cp -a tools/objtool/fixdep $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/objtool/ || :
    fi
    if [ -d arch/$Arch/scripts ]; then
      cp -a arch/$Arch/scripts $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/arch/%{_arch} || :
    fi
    if [ -f arch/$Arch/*lds ]; then
      cp -a arch/$Arch/*lds $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/arch/%{_arch}/ || :
    fi
    if [ -f arch/%{asmarch}/kernel/module.lds ]; then
      cp -a --parents arch/%{asmarch}/kernel/module.lds $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    fi
    find $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/scripts \( -iname "*.o" -o -iname "*.cmd" \) -exec rm -f {} +
%ifarch ppc64le
    cp -a --parents arch/powerpc/lib/crtsavres.[So] $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
%endif
    if [ -d arch/%{asmarch}/include ]; then
      cp -a --parents arch/%{asmarch}/include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    fi
    if [ -d tools/arch/%{asmarch}/include ]; then
      cp -a --parents tools/arch/%{asmarch}/include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    fi
%ifarch aarch64
    # arch/arm64/include/asm/xen references arch/arm
    cp -a --parents arch/arm/include/asm/xen $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    # arch/arm64/include/asm/opcodes.h references arch/arm
    cp -a --parents arch/arm/include/asm/opcodes.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
%endif
    cp -a include $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include
    # Cross-reference from include/perf/events/sof.h
    cp -a sound/soc/sof/sof-audio.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/sound/soc/sof
%ifarch i686 x86_64
    # files for 'make prepare' to succeed with kernel-devel
    cp -a --parents arch/x86/entry/syscalls/syscall_32.tbl $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/entry/syscalls/syscall_64.tbl $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs_32.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs_64.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs_common.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/tools/relocs.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/purgatory.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/stack.S $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/setup-x86_64.S $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/purgatory/entry64.S $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/boot/string.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/boot/string.c $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents arch/x86/boot/ctype.h $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/

    cp -a --parents scripts/syscalltbl.sh $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/
    cp -a --parents scripts/syscallhdr.sh $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/

    cp -a --parents tools/arch/x86/include/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/arch/x86/include/uapi/asm $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/objtool/arch/x86/lib $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/arch/x86/lib/ $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/arch/x86/tools/gen-insn-attr-x86.awk $RPM_BUILD_ROOT/lib/modules/$KernelVer/build
    cp -a --parents tools/objtool/arch/x86/ $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

%endif
    %{log_msg "Clean up intermediate tools files"}
    # Clean up intermediate tools files
    find $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools \( -iname "*.o" -o -iname "*.cmd" \) -exec rm -f {} +

    # Make sure the Makefile, version.h, and auto.conf have a matching
    # timestamp so that external modules can be built
    touch -r $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/Makefile \
        $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include/generated/uapi/linux/version.h \
        $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/include/config/auto.conf

%if %{with_debuginfo}
    eu-readelf -n vmlinux | grep "Build ID" | awk '{print $NF}' > vmlinux.id
    cp vmlinux.id $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/vmlinux.id

    %{log_msg "Copy additional files for kernel-debuginfo rpm"}
    #
    # save the vmlinux file for kernel debugging into the kernel-debuginfo rpm
    # (use mv + symlink instead of cp to reduce disk space requirements)
    #
    mkdir -p $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer
    mv vmlinux $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer
    ln -s $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer/vmlinux vmlinux
    if [ -n "%{?vmlinux_decompressor}" ]; then
	    eu-readelf -n  %{vmlinux_decompressor} | grep "Build ID" | awk '{print $NF}' > vmlinux.decompressor.id
	    # Without build-id the build will fail. But for s390 the build-id
	    # wasn't added before 5.11. In case it is missing prefer not
	    # packaging the debuginfo over a build failure.
	    if [ -s vmlinux.decompressor.id ]; then
		    cp vmlinux.decompressor.id $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/vmlinux.decompressor.id
		    cp %{vmlinux_decompressor} $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer/vmlinux.decompressor
	    fi
    fi

    # build and copy the vmlinux-gdb plugin files into kernel-debuginfo
    %{make} ARCH=$Arch %{?_smp_mflags} scripts_gdb
    cp -a --parents scripts/gdb/{,linux/}*.py $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer
    # this should be a relative symlink (Kbuild creates an absolute one)
    ln -s scripts/gdb/vmlinux-gdb.py $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer/vmlinux-gdb.py
    %py_byte_compile %{python3} $RPM_BUILD_ROOT%{debuginfodir}/lib/modules/$KernelVer/scripts/gdb
%endif

    %{log_msg "Create modnames"}
    find $RPM_BUILD_ROOT/lib/modules/$KernelVer -name "*.ko" -type f >modnames

    # mark modules executable so that strip-to-file can strip them
    xargs --no-run-if-empty chmod u+x < modnames

    # Generate a list of modules for block and networking.
    %{log_msg "Generate a list of modules for block and networking"}
    grep -F /drivers/ modnames | xargs --no-run-if-empty nm -upA |
    sed -n 's,^.*/\([^/]*\.ko\):  *U \(.*\)$,\1 \2,p' > drivers.undef

    collect_modules_list()
    {
      sed -r -n -e "s/^([^ ]+) \\.?($2)\$/\\1/p" drivers.undef |
        LC_ALL=C sort -u > $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.$1
      if [ ! -z "$3" ]; then
        sed -r -e "/^($3)\$/d" -i $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.$1
      fi
    }

    collect_modules_list networking \
      'register_netdev|ieee80211_register_hw|usbnet_probe|phy_driver_register|rt(l_|2x00)(pci|usb)_probe|register_netdevice'
    collect_modules_list block \
      'ata_scsi_ioctl|scsi_add_host|scsi_add_host_with_dma|blk_alloc_queue|blk_init_queue|register_mtd_blktrans|scsi_esp_register|scsi_register_device_handler|blk_queue_physical_block_size' 'pktcdvd.ko|dm-mod.ko'
    collect_modules_list drm \
      'drm_open|drm_init'
    collect_modules_list modesetting \
      'drm_crtc_init'

    %{log_msg "detect missing or incorrect license tags"}
    # detect missing or incorrect license tags
    ( find $RPM_BUILD_ROOT/lib/modules/$KernelVer -name '*.ko' | xargs /sbin/modinfo -l | \
        grep -E -v 'GPL( v2)?$|Dual BSD/GPL$|Dual MPL/GPL$|GPL and additional rights$' ) && exit 1


    if [ $DoModules -eq 0 ]; then
        %{log_msg "Create empty files for RPM packaging"}
        # Ensure important files/directories exist to let the packaging succeed
        echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-modules-core.list
        echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-modules.list
        echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-modules-extra.list
        echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-modules-internal.list
        echo '%%defattr(-,-,-)' > ../kernel${Variant:+-${Variant}}-modules-partner.list
        mkdir -p $RPM_BUILD_ROOT/lib/modules/$KernelVer/kernel
        # Add files usually created by make modules, needed to prevent errors
        # thrown by depmod during package installation
        touch $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.order
        touch $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.builtin
    fi

    # Copy the System.map file for depmod to use
    cp System.map $RPM_BUILD_ROOT/.

    if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" || "$Variant" == "rt-64k" || "$Variant" == "rt-64k-debug" || "$Variant" == "automotive" || "$Variant" == "automotive-debug" ]]; then
	%{log_msg "Skipping efiuki build"}
    else
%if %{with_efiuki}
        %{log_msg "Setup the EFI UKI kernel"}

        # RHEL/CentOS specific .SBAT entries
%if 0%{?centos}
        SBATsuffix="centos"
%else
%if 0%{?fedora}
        SBATsuffix="fedora"
%else
        SBATsuffix="rhel"
%endif
%endif
        SBAT=$(cat <<- EOF
	linux,1,Red Hat,linux,$KernelVer,mailto:secalert@redhat.com
	linux.$SBATsuffix,1,Red Hat,linux,$KernelVer,mailto:secalert@redhat.com
	kernel-uki-virt.$SBATsuffix,1,Red Hat,kernel-uki-virt,$KernelVer,mailto:secalert@redhat.com
	EOF
	)

        ADDONS_SBAT=$(cat <<- EOF
	sbat,1,SBAT Version,sbat,1,https://github.com/rhboot/shim/blob/main/SBAT.md
	kernel-uki-virt-addons.$SBATsuffix,1,Red Hat,kernel-uki-virt-addons,$KernelVer,mailto:secalert@redhat.com
	EOF
	)

	KernelUnifiedImageDir="$RPM_BUILD_ROOT/lib/modules/$KernelVer"
    	KernelUnifiedImage="$KernelUnifiedImageDir/$InstallName-virt.efi"

    	mkdir -p $KernelUnifiedImageDir

    	dracut --conf=%{SOURCE86} \
           --confdir=$(mktemp -d) \
           --verbose \
           --kver "$KernelVer" \
           --kmoddir "$RPM_BUILD_ROOT/lib/modules/$KernelVer/" \
           --logfile=$(mktemp) \
           --uefi \
%if 0%{?rhel} && !0%{?eln}
           --sbat "$SBAT" \
%endif
           --kernel-image $(realpath $KernelImage) \
           --kernel-cmdline 'console=tty0 console=ttyS0' \
	   $KernelUnifiedImage

  KernelAddonsDirOut="$KernelUnifiedImage.extra.d"
  mkdir -p $KernelAddonsDirOut
  python3 %{SOURCE151} %{SOURCE152} $KernelAddonsDirOut virt %{primary_target} %{_target_cpu} "$ADDONS_SBAT"

%if %{signkernel}
	%{log_msg "Sign the EFI UKI kernel"}
%if 0%{?fedora}%{?eln}
        %pesign -s -i $KernelUnifiedImage -o $KernelUnifiedImage.signed -a %{secureboot_ca_0} -c %{secureboot_key_0} -n %{pesign_name_0}
%else
%if 0%{?centos}
        UKI_secureboot_name=centossecureboot204
%else
        UKI_secureboot_name=redhatsecureboot504
%endif
        UKI_secureboot_cert=%{_datadir}/pki/sb-certs/secureboot-uki-virt-%{_arch}.cer

        %pesign -s -i $KernelUnifiedImage -o $KernelUnifiedImage.signed -a %{secureboot_ca_0} -c $UKI_secureboot_cert -n $UKI_secureboot_name
# 0%{?fedora}%{?eln}
%endif
        if [ ! -s $KernelUnifiedImage.signed ]; then
            echo "pesigning failed"
            exit 1
        fi
        mv $KernelUnifiedImage.signed $KernelUnifiedImage

      for addon in "$KernelAddonsDirOut"/*; do
        %pesign -s -i $addon -o $addon.signed -a %{secureboot_ca_0} -c %{secureboot_key_0} -n %{pesign_name_0}
        rm -f $addon
        mv $addon.signed $addon
      done

# signkernel
%endif

    # hmac sign the UKI for FIPS
    KernelUnifiedImageHMAC="$KernelUnifiedImageDir/.$InstallName-virt.efi.hmac"
    %{log_msg "hmac sign the UKI for FIPS"}
    %{log_msg "Creating hmac file: $KernelUnifiedImageHMAC"}
    (cd $KernelUnifiedImageDir && sha512hmac $InstallName-virt.efi) > $KernelUnifiedImageHMAC;

# with_efiuki
%endif
	:  # in case of empty block
    fi # "$Variant" == "rt" || "$Variant" == "rt-debug" || "$Variant" == "automotive" || "$Variant" == "automotive-debug"


    #
    # Generate the modules files lists
    #
    move_kmod_list()
    {
        local module_list="$1"
        local subdir_name="$2"

        mkdir -p "$RPM_BUILD_ROOT/lib/modules/$KernelVer/$subdir_name"

        set +x
        while read -r kmod; do
            local target_file="$RPM_BUILD_ROOT/lib/modules/$KernelVer/$subdir_name/$kmod"
            local target_dir="${target_file%/*}"
            mkdir -p "$target_dir"
            mv "$RPM_BUILD_ROOT/lib/modules/$KernelVer/kernel/$kmod" "$target_dir"
        done < <(sed -e 's|^kernel/||' "$module_list")
        set -x
    }

    create_module_file_list()
    {
        # subdirectory within /lib/modules/$KernelVer where kmods should go
        local module_subdir="$1"
        # kmod list with relative paths produced by filtermods.py
        local relative_kmod_list="$2"
        # list with absolute paths to kmods and other files to be included
        local absolute_file_list="$3"
        # if 1, this adds also all kmod directories to absolute_file_list
        local add_all_dirs="$4"
        local run_mod_deny="$5"

        if [ "$module_subdir" != "kernel" ]; then
            # move kmods into subdirs if needed (internal, partner, extra,..)
            move_kmod_list $relative_kmod_list $module_subdir
        fi

        # make kmod paths absolute
        sed -e 's|^kernel/|/lib/modules/'$KernelVer'/'$module_subdir'/|' $relative_kmod_list > $absolute_file_list

	if [ "$run_mod_deny" -eq 1 ]; then
            # run deny-mod script, this adds blacklist-* files to absolute_file_list
            %{SOURCE20} "$RPM_BUILD_ROOT" lib/modules/$KernelVer $absolute_file_list
	fi

%if %{zipmodules}
        # deny-mod script works with kmods as they are now (not compressed),
        # but if they will be we need to add compext to all
        sed -i %{?zipsed} $absolute_file_list
%endif
        # add also dir for the case when there are no kmods
        # "kernel" subdir is covered in %files section, skip it here
        if [ "$module_subdir" != "kernel" ]; then
                echo "%dir /lib/modules/$KernelVer/$module_subdir" >> $absolute_file_list
        fi

        if [ "$add_all_dirs" -eq 1 ]; then
            (cd $RPM_BUILD_ROOT; find lib/modules/$KernelVer/kernel -mindepth 1 -type d | sort -n) > ../module-dirs.list
            sed -e 's|^lib|%dir /lib|' ../module-dirs.list >> $absolute_file_list
        fi
    }

    if [ $DoModules -eq 1 ]; then
        # save modules.dep for debugging
        cp $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.dep ../

        %{log_msg "Create module list files for all kernel variants"}
        variants_param=""
        if [[ "$Variant" == "rt" || "$Variant" == "rt-debug" ]]; then
            variants_param="-r rt"
        fi
        if [[ "$Variant" == "rt-64k" || "$Variant" == "rt-64k-debug" ]]; then
            variants_param="-r rt-64k"
        fi
        if [[ "$Variant" == "automotive" || "$Variant" == "automotive-debug" ]]; then
            variants_param="-r automotive"
        fi
        # this creates ../modules-*.list output, where each kmod path is as it
        # appears in modules.dep (relative to lib/modules/$KernelVer)
        ret=0
        %{SOURCE22} -l "../filtermods-$KernelVer.log" sort -d $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.dep -c configs/def_variants.yaml $variants_param -o .. || ret=$?
        if [ $ret -ne 0 ]; then
            echo "8< --- filtermods-$KernelVer.log ---"
            cat "../filtermods-$KernelVer.log"
            echo "--- filtermods-$KernelVer.log --- >8"

            echo "8< --- modules.dep ---"
            cat $RPM_BUILD_ROOT/lib/modules/$KernelVer/modules.dep
            echo "--- modules.dep --- >8"
            exit 1
        fi

        create_module_file_list "kernel" ../modules-core.list ../kernel${Variant:+-${Variant}}-modules-core.list 1 0
        create_module_file_list "kernel" ../modules.list ../kernel${Variant:+-${Variant}}-modules.list 0 0
        create_module_file_list "internal" ../modules-internal.list ../kernel${Variant:+-${Variant}}-modules-internal.list 0 1
        create_module_file_list "kernel" ../modules-extra.list ../kernel${Variant:+-${Variant}}-modules-extra.list 0 1
%if 0%{!?fedora:1}
        create_module_file_list "partner" ../modules-partner.list ../kernel${Variant:+-${Variant}}-modules-partner.list 1 1
%endif
    fi # $DoModules -eq 1

    remove_depmod_files()
    {
        # remove files that will be auto generated by depmod at rpm -i time
        pushd $RPM_BUILD_ROOT/lib/modules/$KernelVer/
            # in case below list needs to be extended, remember to add a
            # matching ghost entry in the files section as well
            rm -f modules.{alias,alias.bin,builtin.alias.bin,builtin.bin} \
                  modules.{dep,dep.bin,devname,softdep,symbols,symbols.bin,weakdep}
        popd
    }

    # Cleanup
    %{log_msg "Cleanup build files"}
    rm -f $RPM_BUILD_ROOT/System.map
    %{log_msg "Remove depmod files"}
    remove_depmod_files

%if %{with_cross}
    make -C $RPM_BUILD_ROOT/lib/modules/$KernelVer/build M=scripts clean
    make -C $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/tools/bpf/resolve_btfids clean
    sed -i 's/REBUILD_SCRIPTS_FOR_CROSS:=0/REBUILD_SCRIPTS_FOR_CROSS:=1/' $RPM_BUILD_ROOT/lib/modules/$KernelVer/build/Makefile
%endif

    # Move the devel headers out of the root file system
    %{log_msg "Move the devel headers to RPM_BUILD_ROOT"}
    mkdir -p $RPM_BUILD_ROOT/usr/src/kernels
    mv $RPM_BUILD_ROOT/lib/modules/$KernelVer/build $RPM_BUILD_ROOT/$DevelDir

    # This is going to create a broken link during the build, but we don't use
    # it after this point.  We need the link to actually point to something
    # when kernel-devel is installed, and a relative link doesn't work across
    # the F17 UsrMove feature.
    ln -sf $DevelDir $RPM_BUILD_ROOT/lib/modules/$KernelVer/build

%if %{with_debuginfo}
    # Generate vmlinux.h and put it to kernel-devel path
    # zfcpdump build does not have btf anymore
    if [ "$Variant" != "zfcpdump" ]; then
	%{log_msg "Build the bootstrap bpftool to generate vmlinux.h"}
        # Build the bootstrap bpftool to generate vmlinux.h
        BuildBpftool
        tools/bpf/bpftool/bootstrap/bpftool btf dump file vmlinux format c > $RPM_BUILD_ROOT/$DevelDir/vmlinux.h
    fi
%endif

    %{log_msg "Cleanup kernel-devel and kernel-debuginfo files"}
    # prune junk from kernel-devel
    find $RPM_BUILD_ROOT/usr/src/kernels -name ".*.cmd" -delete
    # prune junk from kernel-debuginfo
    find $RPM_BUILD_ROOT/usr/src/kernels -name "*.mod.c" -delete

    # Red Hat UEFI Secure Boot CA cert, which can be used to authenticate the kernel
    %{log_msg "Install certs"}
    mkdir -p $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer
%if %{signkernel}
    install -m 0644 %{secureboot_ca_0} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca.cer
    %ifarch s390x ppc64le
    if [ -x /usr/bin/rpm-sign ]; then
        install -m 0644 %{secureboot_key_0} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{signing_key_filename}
    fi
    %endif
%endif

%if 0%{?rhel}
    # Red Hat IMA code-signing cert, which is used to authenticate package files
    install -m 0644 %{ima_signing_cert} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{ima_cert_name}
%endif

%if %{signmodules}
    if [ $DoModules -eq 1 ]; then
        # Save the signing keys so we can sign the modules in __modsign_install_post
        cp certs/signing_key.pem certs/signing_key.pem.sign${Variant:++${Variant}}
        cp certs/signing_key.x509 certs/signing_key.x509.sign${Variant:++${Variant}}
        %ifarch s390x ppc64le
        if [ ! -x /usr/bin/rpm-sign ]; then
            install -m 0644 certs/signing_key.x509.sign${Variant:++${Variant}} $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/kernel-signing-ca.cer
            openssl x509 -in certs/signing_key.pem.sign${Variant:++${Variant}} -outform der -out $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{signing_key_filename}
            chmod 0644 $RPM_BUILD_ROOT%{_datadir}/doc/kernel-keys/$KernelVer/%{signing_key_filename}
        fi
        %endif
    fi
%endif

%if %{with_gcov}
    popd
%endif
}

###
# DO it...
###

# prepare directories
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/boot
mkdir -p $RPM_BUILD_ROOT%{_libexecdir}

cd linux-%{KVERREL}

%if %{with_debug}
%if %{with_realtime}
BuildKernel %make_target %kernel_image %{_use_vdso} rt-debug
%endif

%if %{with_realtime_arm64_64k}
BuildKernel %make_target %kernel_image %{_use_vdso} rt-64k-debug
%endif

%if %{with_automotive}
BuildKernel %make_target %kernel_image %{_use_vdso} automotive-debug
%endif

%if %{with_arm64_16k}
BuildKernel %make_target %kernel_image %{_use_vdso} 16k-debug
%endif

%if %{with_arm64_64k}
BuildKernel %make_target %kernel_image %{_use_vdso} 64k-debug
%endif

%if %{with_up}
BuildKernel %make_target %kernel_image %{_use_vdso} debug
%endif
%endif

%if %{with_zfcpdump}
BuildKernel %make_target %kernel_image %{_use_vdso} zfcpdump
%endif

%if %{with_arm64_16k_base}
BuildKernel %make_target %kernel_image %{_use_vdso} 16k
%endif

%if %{with_arm64_64k_base}
BuildKernel %make_target %kernel_image %{_use_vdso} 64k
%endif

%if %{with_realtime_base}
BuildKernel %make_target %kernel_image %{_use_vdso} rt
%endif

%if %{with_realtime_arm64_64k_base}
BuildKernel %make_target %kernel_image %{_use_vdso} rt-64k
%endif

%if %{with_automotive_base}
BuildKernel %make_target %kernel_image %{_use_vdso} automotive
%endif

%if %{with_up_base}
BuildKernel %make_target %kernel_image %{_use_vdso}
%endif

%ifnarch noarch i686 %{nobuildarches}
%if !%{with_debug} && !%{with_zfcpdump} && !%{with_up} && !%{with_arm64_16k} && !%{with_arm64_64k} && !%{with_realtime} && !%{with_realtime_arm64_64k} && !%{with_automotive}
# If only building the user space tools, then initialize the build environment
# and some variables so that the various userspace tools can be built.
%{log_msg "Initialize userspace tools build environment"}
InitBuildVars
# Some tests build also modules, and need Module.symvers
if ! [[ -e Module.symvers ]] && [[ -f $DevelDir/Module.symvers ]]; then
    %{log_msg "Found Module.symvers in DevelDir, copying to ."}
    cp "$DevelDir/Module.symvers" .
fi
%endif
%endif

%ifarch aarch64
%global perf_build_extra_opts CORESIGHT=1
%endif
%global perf_make \
  %{__make} %{?make_opts} EXTRA_CFLAGS="${RPM_OPT_FLAGS}" EXTRA_CXXFLAGS="${RPM_OPT_FLAGS}" LDFLAGS="%{__global_ldflags} -Wl,-E" %{?cross_opts} -C tools/perf V=1 NO_PERF_READ_VDSO32=1 NO_PERF_READ_VDSOX32=1 WERROR=0 NO_LIBUNWIND=1 HAVE_CPLUS_DEMANGLE=1 NO_GTK2=1 NO_STRLCPY=1 NO_BIONIC=1 LIBBPF_DYNAMIC=1 LIBTRACEEVENT_DYNAMIC=1 %{?perf_build_extra_opts} prefix=%{_prefix} PYTHON=%{__python3}
%if %{with_perf}
%{log_msg "Build perf"}
# perf
# make sure check-headers.sh is executable
chmod +x tools/perf/check-headers.sh
%{perf_make} DESTDIR=$RPM_BUILD_ROOT all
%endif

%if %{with_libperf}
%global libperf_make \
  %{__make} %{?make_opts} EXTRA_CFLAGS="${RPM_OPT_FLAGS}" LDFLAGS="%{__global_ldflags}" %{?cross_opts} -C tools/lib/perf V=1
  %{log_msg "build libperf"}
%{libperf_make} DESTDIR=$RPM_BUILD_ROOT
%endif

%global tools_make \
  CFLAGS="${RPM_OPT_FLAGS}" LDFLAGS="%{__global_ldflags}" EXTRA_CFLAGS="${RPM_OPT_FLAGS}" %{make} %{?make_opts}

%ifarch %{cpupowerarchs}
    # link against in-tree libcpupower for idle state support
    %global rtla_make %{tools_make} LDFLAGS="%{__global_ldflags} -L../../power/cpupower" INCLUDES="-I../../power/cpupower/lib"
%else
    %global rtla_make %{tools_make}
%endif

%if %{with_tools}

%if %{with_ynl}
pushd tools/net/ynl
export PIP_CONFIG_FILE=/tmp/pip.config
cat <<EOF > $PIP_CONFIG_FILE
[install]
no-index = true
no-build-isolation = false
EOF
%{tools_make} %{?_smp_mflags} DESTDIR=$RPM_BUILD_ROOT install
popd
%endif

%ifarch %{cpupowerarchs}
# cpupower
# make sure version-gen.sh is executable.
chmod +x tools/power/cpupower/utils/version-gen.sh
%{log_msg "build cpupower"}
%{tools_make} %{?_smp_mflags} -C tools/power/cpupower CPUFREQ_BENCH=false DEBUG=false
%ifarch x86_64
    pushd tools/power/cpupower/debug/x86_64
    %{log_msg "build centrino-decode powernow-k8-decode"}
    %{tools_make} %{?_smp_mflags} centrino-decode powernow-k8-decode
    popd
%endif
%ifarch x86_64
   pushd tools/power/x86/x86_energy_perf_policy/
   %{log_msg "build x86_energy_perf_policy"}
   %{tools_make}
   popd
   pushd tools/power/x86/turbostat
   %{log_msg "build turbostat"}
   %{tools_make}
   popd
   pushd tools/power/x86/intel-speed-select
   %{log_msg "build intel-speed-select"}
   %{tools_make}
   popd
   pushd tools/arch/x86/intel_sdsi
   %{log_msg "build intel_sdsi"}
   %{tools_make} CFLAGS="${RPM_OPT_FLAGS}"
   popd
%endif
%endif
pushd tools/thermal/tmon/
%{log_msg "build tmon"}
%{tools_make}
popd
pushd tools/bootconfig/
%{log_msg "build bootconfig"}
%{tools_make}
popd
pushd tools/iio/
%{log_msg "build iio"}
%{tools_make}
popd
pushd tools/gpio/
%{log_msg "build gpio"}
%{tools_make}
popd
# build VM tools
pushd tools/mm/
%{log_msg "build slabinfo page_owner_sort"}
%{tools_make} slabinfo page_owner_sort
popd
pushd tools/verification/rv/
%{log_msg "build rv"}
%{tools_make}
popd
pushd tools/tracing/rtla
%{log_msg "build rtla"}
%{rtla_make}
popd
%endif

#set RPM_VMLINUX_H
if [ -f $RPM_BUILD_ROOT/$DevelDir/vmlinux.h ]; then
  RPM_VMLINUX_H=$RPM_BUILD_ROOT/$DevelDir/vmlinux.h
elif [ -f $DevelDir/vmlinux.h ]; then
  RPM_VMLINUX_H=$DevelDir/vmlinux.h
fi
echo "${RPM_VMLINUX_H}" > ../vmlinux_h_path

%if %{with_selftests}
%{log_msg "start build selftests"}
# Unfortunately, samples/bpf/Makefile expects that the headers are installed
# in the source tree. We installed them previously to $RPM_BUILD_ROOT/usr
# but there's no way to tell the Makefile to take them from there.
%{log_msg "install headers for selftests"}
%{make} %{?_smp_mflags} headers_install

# If we re building only tools without kernel, we need to generate config
# headers and prepare tree for modules building. The modules_prepare target
# will cover both.
if [ ! -f include/generated/autoconf.h ]; then
   %{log_msg "modules_prepare for selftests"}
   %{make} %{?_smp_mflags} modules_prepare
fi

# Build BPFtool for samples/bpf
if [ ! -f tools/bpf/bpftool/bootstrap/bpftool ]; then
  BuildBpftool
fi

%{log_msg "build samples/bpf"}
%{make} %{?_smp_mflags} ARCH=$Arch BPFTOOL=$(pwd)/tools/bpf/bpftool/bootstrap/bpftool V=1 M=samples/bpf/ VMLINUX_H="${RPM_VMLINUX_H}" || true

pushd tools/testing/selftests
# We need to install here because we need to call make with ARCH set which
# doesn't seem possible to do in the install section.
%if %{selftests_must_build}
  force_targets="FORCE_TARGETS=1"
%else
  force_targets=""
%endif

%{log_msg "main selftests compile"}
%{make} %{?_smp_mflags} ARCH=$Arch V=1 TARGETS="bpf cgroup mm net net/forwarding net/mptcp net/netfilter net/packetdrill tc-testing memfd drivers/net/bonding iommu cachestat pid_namespace rlimits" SKIP_TARGETS="" $force_targets INSTALL_PATH=%{buildroot}%{_libexecdir}/kselftests VMLINUX_H="${RPM_VMLINUX_H}" install

%ifarch %{klptestarches}
	# kernel livepatching selftest test_modules will build against
	# /lib/modules/$(shell uname -r)/build tree unless KDIR is set
	export KDIR=$(realpath $(pwd)/../../..)
	%{make} %{?_smp_mflags} ARCH=$Arch V=1 TARGETS="livepatch" SKIP_TARGETS="" $force_targets INSTALL_PATH=%{buildroot}%{_libexecdir}/kselftests VMLINUX_H="${RPM_VMLINUX_H}" install || true
%endif

# 'make install' for bpf is broken and upstream refuses to fix it.
# Install the needed files manually.
%{log_msg "install selftests"}
for dir in bpf bpf/no_alu32 bpf/progs; do
	# In ARK, the rpm build continues even if some of the selftests
	# cannot be built. It's not always possible to build selftests,
	# as upstream sometimes dependens on too new llvm version or has
	# other issues. If something did not get built, just skip it.
	test -d $dir || continue
	mkdir -p %{buildroot}%{_libexecdir}/kselftests/$dir
	find $dir -maxdepth 1 -type f \( -executable -o -name '*.py' -o -name settings -o \
		-name 'btf_dump_test_case_*.c' -o -name '*.ko' -o \
		-name '*.o' -exec sh -c 'readelf -h "{}" | grep -q "^  Machine:.*BPF"' \; \) -print0 | \
	xargs -0 cp -t %{buildroot}%{_libexecdir}/kselftests/$dir || true
done
%buildroot_save_unstripped "usr/libexec/kselftests/bpf/test_progs"
%buildroot_save_unstripped "usr/libexec/kselftests/bpf/test_progs-no_alu32"
popd
%{log_msg "end build selftests"}
%endif

%if %{with_doc}
%{log_msg "start install docs"}
# Make the HTML pages.
%{log_msg "build html docs"}
%{__make} PYTHON=/usr/bin/python3 htmldocs || %{doc_build_fail}

# sometimes non-world-readable files sneak into the kernel source tree
chmod -R a=rX Documentation
find Documentation -type d | xargs chmod u+w
%{log_msg "end install docs"}
%endif

# Module signing (modsign)
#
# This must be run _after_ find-debuginfo.sh runs, otherwise that will strip
# the signature off of the modules.
#
# Don't sign modules for the zfcpdump variant as it is monolithic.

%define __modsign_install_post \
  if [ "%{signmodules}" -eq "1" ]; then \
    %{log_msg "Signing kernel modules ..."} \
    modules_dirs="$(shopt -s nullglob; echo $RPM_BUILD_ROOT/lib/modules/%{KVERREL}*)" \
    for modules_dir in $modules_dirs; do \
        variant_suffix="${modules_dir#$RPM_BUILD_ROOT/lib/modules/%{KVERREL}}" \
        [ "$variant_suffix" == "+zfcpdump" ] && continue \
	%{log_msg "Signing modules for %{KVERREL}${variant_suffix}"} \
        %{modsign_cmd} certs/signing_key.pem.sign${variant_suffix} certs/signing_key.x509.sign${variant_suffix} $modules_dir/ \
    done \
  fi \
  if [ "%{zipmodules}" -eq "1" ]; then \
    %{log_msg "Compressing kernel modules ..."} \
    find $RPM_BUILD_ROOT/lib/modules/ -type f -name '*.ko' | xargs -n 16 -P${RPM_BUILD_NCPUS} -r %compression %compression_flags; \
  fi \
%{nil}

###
### Special hacks for debuginfo subpackages.
###

# This macro is used by %%install, so we must redefine it before that.
%define debug_package %{nil}

%if %{with_debuginfo}

%ifnarch noarch %{nobuildarches}
%global __debug_package 1
%files -f debugfiles.list debuginfo-common-%{_target_cpu}
%endif

%endif

# We don't want to package debuginfo for self-tests and samples but
# we have to delete them to avoid an error messages about unpackaged
# files.
# Delete the debuginfo for kernel-devel files
%define __remove_unwanted_dbginfo_install_post \
  if [ "%{with_selftests}" -ne "0" ]; then \
    rm -rf $RPM_BUILD_ROOT/usr/lib/debug/usr/libexec/ksamples; \
    rm -rf $RPM_BUILD_ROOT/usr/lib/debug/usr/libexec/kselftests; \
  fi \
  rm -rf $RPM_BUILD_ROOT/usr/lib/debug/usr/src; \
%{nil}

# Make debugedit and gdb-add-index use target versions of tools
# when cross-compiling. This is supported since debugedit-5.1-5.fc42
# https://inbox.sourceware.org/debugedit/20250220153858.963312-1-mark@klomp.org/
%if %{with_cross}
%define __override_target_tools_for_debugedit \
	export OBJCOPY=%{_build_arch}-linux-gnu-objcopy \
	export NM=%{_build_arch}-linux-gnu-nm \
	export READELF=%{_build_arch}-linux-gnu-readelf \
%{nil}
%endif

#
# Disgusting hack alert! We need to ensure we sign modules *after* all
# invocations of strip occur, which is in __debug_install_post if
# find-debuginfo.sh runs, and __os_install_post if not.
#
%define __spec_install_post \
  %{?__override_target_tools_for_debugedit:%{__override_target_tools_for_debugedit}}\
  %{?__debug_package:%{__debug_install_post}}\
  %{__arch_install_post}\
  %{__os_install_post}\
  %{__remove_unwanted_dbginfo_install_post}\
  %{__restore_unstripped_root_post}\
  %{__modsign_install_post}

###
### install
###

%install

cd linux-%{KVERREL}

# re-define RPM_VMLINUX_H, because it doesn't carry over from %build
RPM_VMLINUX_H="$(cat ../vmlinux_h_path)"

%if %{with_doc}
docdir=$RPM_BUILD_ROOT%{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}

# copy the source over
mkdir -p $docdir
tar -h -f - --exclude=man --exclude='.*' -c Documentation | tar xf - -C $docdir
cat %{SOURCE2} | xz > $docdir/kernel.changelog.xz
chmod 0644 $docdir/kernel.changelog.xz

# with_doc
%endif

# We have to do the headers install before the tools install because the
# kernel headers_install will remove any header files in /usr/include that
# it doesn't install itself.

%if %{with_headers}
# Install kernel headers
%{__make} ARCH=%{hdrarch} INSTALL_HDR_PATH=$RPM_BUILD_ROOT/usr headers_install

find $RPM_BUILD_ROOT/usr/include \
     \( -name .install -o -name .check -o \
        -name ..install.cmd -o -name ..check.cmd \) -delete

%endif

%if %{with_cross_headers}
HDR_ARCH_LIST='arm64 powerpc s390 x86 riscv'
mkdir -p $RPM_BUILD_ROOT/usr/tmp-headers

for arch in $HDR_ARCH_LIST; do
	mkdir $RPM_BUILD_ROOT/usr/tmp-headers/arch-${arch}
	%{__make} ARCH=${arch} INSTALL_HDR_PATH=$RPM_BUILD_ROOT/usr/tmp-headers/arch-${arch} headers_install
done

find $RPM_BUILD_ROOT/usr/tmp-headers \
     \( -name .install -o -name .check -o \
        -name ..install.cmd -o -name ..check.cmd \) -delete

# Copy all the architectures we care about to their respective asm directories
for arch in $HDR_ARCH_LIST ; do
	mkdir -p $RPM_BUILD_ROOT/usr/${arch}-linux-gnu/include
	mv $RPM_BUILD_ROOT/usr/tmp-headers/arch-${arch}/include/* $RPM_BUILD_ROOT/usr/${arch}-linux-gnu/include/
done

rm -rf $RPM_BUILD_ROOT/usr/tmp-headers
%endif

%if %{with_kernel_abi_stablelists}
# kabi directory
INSTALL_KABI_PATH=$RPM_BUILD_ROOT/lib/modules/
mkdir -p $INSTALL_KABI_PATH

# install kabi releases directories
tar -xvf %{SOURCE300} -C $INSTALL_KABI_PATH
# with_kernel_abi_stablelists
%endif

%if %{with_perf}
# perf tool binary and supporting scripts/binaries
%{perf_make} DESTDIR=$RPM_BUILD_ROOT lib=%{_lib} install-bin
# remove the 'trace' symlink.
rm -f %{buildroot}%{_bindir}/trace

# For both of the below, yes, this should be using a macro but right now
# it's hard coded and we don't actually want it anyway right now.
# Whoever wants examples can fix it up!

# remove examples
rm -rf %{buildroot}/usr/lib/perf/examples
rm -rf %{buildroot}/usr/lib/perf/include

# python-perf extension
%{perf_make} DESTDIR=$RPM_BUILD_ROOT install-python_ext

# perf man pages (note: implicit rpm magic compresses them later)
mkdir -p %{buildroot}/%{_mandir}/man1
%{perf_make} DESTDIR=$RPM_BUILD_ROOT install-man

# remove any tracevent files, eg. its plugins still gets built and installed,
# even if we build against system's libtracevent during perf build (by setting
# LIBTRACEEVENT_DYNAMIC=1 above in perf_make macro). Those files should already
# ship with libtraceevent package.
rm -rf %{buildroot}%{_libdir}/traceevent
%endif

%if %{with_libperf}
%{libperf_make} DESTDIR=%{buildroot} prefix=%{_prefix} libdir=%{_libdir} install install_headers
# This is installed on some arches and we don't want to ship it
rm -rf %{buildroot}%{_libdir}/libperf.a
%endif

%if %{with_tools}
%ifarch %{cpupowerarchs}
%{make} -C tools/power/cpupower DESTDIR=$RPM_BUILD_ROOT libdir=%{_libdir} mandir=%{_mandir} CPUFREQ_BENCH=false install
%find_lang cpupower
mv cpupower.lang ../
%ifarch x86_64
    pushd tools/power/cpupower/debug/x86_64
    install -m755 centrino-decode %{buildroot}%{_bindir}/centrino-decode
    install -m755 powernow-k8-decode %{buildroot}%{_bindir}/powernow-k8-decode
    popd
%endif
chmod 0755 %{buildroot}%{_libdir}/libcpupower.so*
%endif
%ifarch x86_64
   mkdir -p %{buildroot}%{_mandir}/man8
   pushd tools/power/x86/x86_energy_perf_policy
   %{tools_make} DESTDIR=%{buildroot} install
   popd
   pushd tools/power/x86/turbostat
   %{tools_make} DESTDIR=%{buildroot} install
   popd
   pushd tools/power/x86/intel-speed-select
   %{tools_make} DESTDIR=%{buildroot} install
   popd
   pushd tools/arch/x86/intel_sdsi
   %{tools_make} CFLAGS="${RPM_OPT_FLAGS}" DESTDIR=%{buildroot} BINDIR=%{_sbindir} install
   popd
%endif
pushd tools/thermal/tmon
%{tools_make} INSTALL_ROOT=%{buildroot} install
popd
pushd tools/bootconfig
%{tools_make} DESTDIR=%{buildroot} install
popd
pushd tools/iio
%{tools_make} DESTDIR=%{buildroot} install
popd
pushd tools/gpio
%{tools_make} DESTDIR=%{buildroot} install
popd
install -m644 -D %{SOURCE2002} %{buildroot}%{_sysconfdir}/logrotate.d/kvm_stat
pushd tools/kvm/kvm_stat
%{__make} INSTALL_ROOT=%{buildroot} install-tools
%{__make} INSTALL_ROOT=%{buildroot} install-man
install -m644 -D kvm_stat.service %{buildroot}%{_unitdir}/kvm_stat.service
popd
# install VM tools
pushd tools/mm/
install -m755 slabinfo %{buildroot}%{_bindir}/slabinfo
install -m755 page_owner_sort %{buildroot}%{_bindir}/page_owner_sort
popd
pushd tools/verification/rv/
%{tools_make} DESTDIR=%{buildroot} install
popd
pushd tools/tracing/rtla/
%{tools_make} DESTDIR=%{buildroot} install
rm -f %{buildroot}%{_bindir}/hwnoise
rm -f %{buildroot}%{_bindir}/osnoise
rm -f %{buildroot}%{_bindir}/timerlat
(cd %{buildroot}

        ln -sf rtla ./%{_bindir}/hwnoise
        ln -sf rtla ./%{_bindir}/osnoise
        ln -sf rtla ./%{_bindir}/timerlat
)
popd
%endif

%if %{with_selftests}
pushd samples
install -d %{buildroot}%{_libexecdir}/ksamples
# install bpf samples
pushd bpf
install -d %{buildroot}%{_libexecdir}/ksamples/bpf
find -type f -executable -exec install -m755 {} %{buildroot}%{_libexecdir}/ksamples/bpf \;
install -m755 *.sh %{buildroot}%{_libexecdir}/ksamples/bpf
# test_lwt_bpf.sh compiles test_lwt_bpf.c when run; this works only from the
# kernel tree. Just remove it.
rm %{buildroot}%{_libexecdir}/ksamples/bpf/test_lwt_bpf.sh
install -m644 *_kern.o %{buildroot}%{_libexecdir}/ksamples/bpf || true
install -m644 tcp_bpf.readme %{buildroot}%{_libexecdir}/ksamples/bpf
popd
# install pktgen samples
pushd pktgen
install -d %{buildroot}%{_libexecdir}/ksamples/pktgen
find . -type f -executable -exec install -m755 {} %{buildroot}%{_libexecdir}/ksamples/pktgen/{} \;
find . -type f ! -executable -exec install -m644 {} %{buildroot}%{_libexecdir}/ksamples/pktgen/{} \;
popd
popd
# install mm selftests
pushd tools/testing/selftests/mm
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/mm/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/mm/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/mm/{} \;
popd
# install cgroup selftests
pushd tools/testing/selftests/cgroup
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/cgroup/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/cgroup/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/cgroup/{} \;
popd
# install drivers/net/mlxsw selftests
pushd tools/testing/selftests/drivers/net/mlxsw
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/drivers/net/mlxsw/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/mlxsw/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/mlxsw/{} \;
popd
# install drivers/net/netdevsim selftests
pushd tools/testing/selftests/drivers/net/netdevsim
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/drivers/net/netdevsim/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/netdevsim/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/netdevsim/{} \;
popd
# install drivers/net/bonding selftests
pushd tools/testing/selftests/drivers/net/bonding
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/drivers/net/bonding/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/bonding/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/drivers/net/bonding/{} \;
popd
# install net/forwarding selftests
pushd tools/testing/selftests/net/forwarding
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/net/forwarding/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/net/forwarding/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/net/forwarding/{} \;
popd
# install net/mptcp selftests
pushd tools/testing/selftests/net/mptcp
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/net/mptcp/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/net/mptcp/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/net/mptcp/{} \;
popd
# install tc-testing selftests
pushd tools/testing/selftests/tc-testing
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/tc-testing/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/tc-testing/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/tc-testing/{} \;
popd
# install livepatch selftests
pushd tools/testing/selftests/livepatch
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/livepatch/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/livepatch/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/livepatch/{} \;
popd
# install net/netfilter selftests
pushd tools/testing/selftests/net/netfilter
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/net/netfilter/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/net/netfilter/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/net/netfilter/{} \;
popd
# install net/packetdrill selftests
pushd tools/testing/selftests/net/packetdrill
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/net/packetdrill/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/net/packetdrill/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/net/packetdrill/{} \;
popd

# install memfd selftests
pushd tools/testing/selftests/memfd
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/memfd/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/memfd/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/memfd/{} \;
popd
# install iommu selftests
pushd tools/testing/selftests/iommu
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/iommu/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/iommu/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/iommu/{} \;
popd
# install rlimits selftests
pushd tools/testing/selftests/rlimits
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/rlimits/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/rlimits/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/rlimits/{} \;
popd
# install pid_namespace selftests
pushd tools/testing/selftests/pid_namespace
find -type d -exec install -d %{buildroot}%{_libexecdir}/kselftests/pid_namespace/{} \;
find -type f -executable -exec install -D -m755 {} %{buildroot}%{_libexecdir}/kselftests/pid_namespace/{} \;
find -type f ! -executable -exec install -D -m644 {} %{buildroot}%{_libexecdir}/kselftests/pid_namespace/{} \;
popd
%endif

###
### clean
###

###
### scripts
###

%if %{with_tools}
%post -n %{package_name}-tools-libs
/sbin/ldconfig

%postun -n %{package_name}-tools-libs
/sbin/ldconfig
%endif

#
# This macro defines a %%post script for a kernel*-devel package.
#	%%kernel_devel_post [<subpackage>]
# Note we don't run hardlink if ostree is in use, as ostree is
# a far more sophisticated hardlink implementation.
# https://github.com/projectatomic/rpm-ostree/commit/58a79056a889be8814aa51f507b2c7a4dccee526
#
# The deletion of *.hardlink-temporary files is a temporary workaround
# for this bug in the hardlink binary (fixed in util-linux 2.38):
# https://github.com/util-linux/util-linux/issues/1602
#
%define kernel_devel_post() \
%{expand:%%post %{?1:%{1}-}devel}\
if [ -f /etc/sysconfig/kernel ]\
then\
    . /etc/sysconfig/kernel || exit $?\
fi\
if [ "$HARDLINK" != "no" -a -x /usr/bin/hardlink -a ! -e /run/ostree-booted ] \
then\
    (cd /usr/src/kernels/%{KVERREL}%{?1:+%{1}} &&\
     /usr/bin/find . -type f | while read f; do\
       hardlink -c /usr/src/kernels/*%{?dist}.*/$f $f > /dev/null\
     done;\
     /usr/bin/find /usr/src/kernels -type f -name '*.hardlink-temporary' -delete\
    )\
fi\
%if %{with_cross}\
    echo "Building scripts and resolve_btfids"\
    env --unset=ARCH make -C /usr/src/kernels/%{KVERREL}%{?1:+%{1}} prepare_after_cross\
%endif\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-extra package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_extra_post [<subpackage>]
#
%define kernel_modules_extra_post() \
%{expand:%%post %{?1:%{1}-}modules-extra}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules-extra}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-internal package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_internal_post [<subpackage>]
#
%define kernel_modules_internal_post() \
%{expand:%%post %{?1:%{1}-}modules-internal}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules-internal}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-partner package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_partner_post [<subpackage>]
#
%define kernel_modules_partner_post() \
%{expand:%%post %{?1:%{1}-}modules-partner}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules-partner}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules package.
# It also defines a %%postun script that does the same thing.
#	%%kernel_modules_post [<subpackage>]
#
%define kernel_modules_post() \
%{expand:%%post %{?1:%{1}-}modules}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
if [ ! -f %{_localstatedir}/lib/rpm-state/%{name}/installing_core_%{KVERREL}%{?1:+%{1}} ]; then\
	mkdir -p %{_localstatedir}/lib/rpm-state/%{name}\
	touch %{_localstatedir}/lib/rpm-state/%{name}/need_to_run_dracut_%{KVERREL}%{?1:+%{1}}\
fi\
%{nil}\
%{expand:%%postun %{?1:%{1}-}modules}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}\
%{expand:%%posttrans %{?1:%{1}-}modules}\
if [ -f %{_localstatedir}/lib/rpm-state/%{name}/need_to_run_dracut_%{KVERREL}%{?1:+%{1}} ]; then\
	rm -f %{_localstatedir}/lib/rpm-state/%{name}/need_to_run_dracut_%{KVERREL}%{?1:+%{1}}\
	echo "Running: dracut -f --kver %{KVERREL}%{?1:+%{1}}"\
	dracut -f --kver "%{KVERREL}%{?1:+%{1}}" || exit $?\
fi\
%{nil}

#
# This macro defines a %%post script for a kernel*-modules-core package.
#	%%kernel_modules_core_post [<subpackage>]
#
%define kernel_modules_core_post() \
%{expand:%%posttrans %{?1:%{1}-}modules-core}\
/sbin/depmod -a %{KVERREL}%{?1:+%{1}}\
%{nil}

# This macro defines a %%posttrans script for a kernel package.
#	%%kernel_variant_posttrans [-v <subpackage>] [-u uki-suffix]
# More text can follow to go at the end of this variant's %%post.
#
%define kernel_variant_posttrans(v:u:) \
%{expand:%%posttrans %{?-v:%{-v*}-}%{!?-u*:core}%{?-u*:uki-%{-u*}}}\
%if 0%{!?fedora:1}\
%if !%{with_automotive}\
if [ -x %{_sbindir}/weak-modules ]\
then\
    %{_sbindir}/weak-modules --add-kernel %{KVERREL}%{?-v:+%{-v*}} || exit $?\
fi\
%endif\
%endif\
rm -f %{_localstatedir}/lib/rpm-state/%{name}/installing_core_%{KVERREL}%{?-v:+%{-v*}}\
/bin/kernel-install add %{KVERREL}%{?-v:+%{-v*}} /lib/modules/%{KVERREL}%{?-v:+%{-v*}}/vmlinuz%{?-u:-%{-u*}.efi} || exit $?\
if [[ ! -e "/boot/symvers-%{KVERREL}%{?-v:+%{-v*}}.%compext" ]]; then\
    cp "/lib/modules/%{KVERREL}%{?-v:+%{-v*}}/symvers.%compext" "/boot/symvers-%{KVERREL}%{?-v:+%{-v*}}.%compext"\
    if command -v restorecon &>/dev/null; then\
        restorecon "/boot/symvers-%{KVERREL}%{?-v:+%{-v*}}.%compext"\
    fi\
fi\
%{nil}

#
# This macro defines a %%post script for a kernel package and its devel package.
#	%%kernel_variant_post [-v <subpackage>] [-r <replace>]
# More text can follow to go at the end of this variant's %%post.
#
%define kernel_variant_post(v:r:) \
%{expand:%%kernel_devel_post %{?-v*}}\
%{expand:%%kernel_modules_post %{?-v*}}\
%{expand:%%kernel_modules_core_post %{?-v*}}\
%{expand:%%kernel_modules_extra_post %{?-v*}}\
%{expand:%%kernel_modules_internal_post %{?-v*}}\
%if 0%{!?fedora:1}\
%{expand:%%kernel_modules_partner_post %{?-v*}}\
%endif\
%{expand:%%kernel_variant_posttrans %{?-v*:-v %{-v*}}}\
%{expand:%%post %{?-v*:%{-v*}-}core}\
%{-r:\
if [ `uname -i` == "x86_64" -o `uname -i` == "i386" ] &&\
   [ -f /etc/sysconfig/kernel ]; then\
  /bin/sed -r -i -e 's/^DEFAULTKERNEL=%{-r*}$/DEFAULTKERNEL=kernel%{?-v:-%{-v*}}/' /etc/sysconfig/kernel || exit $?\
fi}\
mkdir -p %{_localstatedir}/lib/rpm-state/%{name}\
touch %{_localstatedir}/lib/rpm-state/%{name}/installing_core_%{KVERREL}%{?-v:+%{-v*}}\
%{nil}

#
# This macro defines a %%preun script for a kernel package.
#	%%kernel_variant_preun [-v <subpackage>] -u [uki-suffix]
#
%define kernel_variant_preun(v:u:) \
%{expand:%%preun %{?-v:%{-v*}-}%{!?-u*:core}%{?-u*:uki-%{-u*}}}\
/bin/kernel-install remove %{KVERREL}%{?-v:+%{-v*}} || exit $?\
%if !%{with_automotive}\
if [ -x %{_sbindir}/weak-modules ]\
then\
    %{_sbindir}/weak-modules --remove-kernel %{KVERREL}%{?-v:+%{-v*}} || exit $?\
fi\
%endif\
%{nil}

%if %{with_up_base} && %{with_efiuki}
%kernel_variant_posttrans -u virt
%kernel_variant_preun -u virt
%endif

%if %{with_up_base}
%kernel_variant_preun
%kernel_variant_post
%endif

%if %{with_zfcpdump}
%kernel_variant_preun -v zfcpdump
%kernel_variant_post -v zfcpdump
%endif

%if %{with_up} && %{with_debug} && %{with_efiuki}
%kernel_variant_posttrans -v debug -u virt
%kernel_variant_preun -v debug -u virt
%endif

%if %{with_up} && %{with_debug}
%kernel_variant_preun -v debug
%kernel_variant_post -v debug
%endif

%if %{with_arm64_16k_base}
%kernel_variant_preun -v 16k
%kernel_variant_post -v 16k
%endif

%if %{with_debug} && %{with_arm64_16k}
%kernel_variant_preun -v 16k-debug
%kernel_variant_post -v 16k-debug
%endif

%if %{with_arm64_16k} && %{with_debug} && %{with_efiuki}
%kernel_variant_posttrans -v 16k-debug -u virt
%kernel_variant_preun -v 16k-debug -u virt
%endif

%if %{with_arm64_16k_base} && %{with_efiuki}
%kernel_variant_posttrans -v 16k -u virt
%kernel_variant_preun -v 16k -u virt
%endif

%if %{with_arm64_64k_base}
%kernel_variant_preun -v 64k
%kernel_variant_post -v 64k
%endif

%if %{with_debug} && %{with_arm64_64k}
%kernel_variant_preun -v 64k-debug
%kernel_variant_post -v 64k-debug
%endif

%if %{with_arm64_64k} && %{with_debug} && %{with_efiuki}
%kernel_variant_posttrans -v 64k-debug -u virt
%kernel_variant_preun -v 64k-debug -u virt
%endif

%if %{with_arm64_64k_base} && %{with_efiuki}
%kernel_variant_posttrans -v 64k -u virt
%kernel_variant_preun -v 64k -u virt
%endif

%if %{with_realtime_base}
%kernel_variant_preun -v rt
%kernel_variant_post -v rt -r kernel
%endif

%if %{with_automotive_base}
%kernel_variant_preun -v automotive
%kernel_variant_post -v automotive -r kernel
%endif

%if %{with_realtime} && %{with_debug}
%kernel_variant_preun -v rt-debug
%kernel_variant_post -v rt-debug
%endif

%if %{with_realtime_arm64_64k_base}
%kernel_variant_preun -v rt-64k
%kernel_variant_post -v rt-64k
%kernel_kvm_post rt-64k
%endif

%if %{with_debug} && %{with_realtime_arm64_64k}
%kernel_variant_preun -v rt-64k-debug
%kernel_variant_post -v rt-64k-debug
%kernel_kvm_post rt-64k-debug
%endif

%if %{with_automotive} && %{with_debug}
%kernel_variant_preun -v automotive-debug
%kernel_variant_post -v automotive-debug
%endif

###
### file lists
###

%if %{with_headers}
%files headers
/usr/include/*
%exclude %{_includedir}/cpufreq.h
%exclude %{_includedir}/ynl
%endif

%if %{with_cross_headers}
%files cross-headers
/usr/*-linux-gnu/include/*
%endif

%if %{with_kernel_abi_stablelists}
%files -n %{package_name}-abi-stablelists
/lib/modules/kabi-*
%endif

%if %{with_kabidw_base}
%ifarch x86_64 s390x ppc64 ppc64le aarch64 riscv64
%files kernel-kabidw-base-internal
%defattr(-,root,root)
/kabidw-base/%{_target_cpu}/*
%endif
%endif

# only some architecture builds need kernel-doc
%if %{with_doc}
%files doc
%defattr(-,root,root)
%{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}/Documentation/*
%dir %{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}/Documentation
%dir %{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}
%{_datadir}/doc/kernel-doc-%{specversion}-%{pkgrelease}/kernel.changelog.xz
%endif

%if %{with_perf}
%files -n perf
%{_bindir}/perf
%{_libdir}/libperf-jvmti.so
%dir %{_libexecdir}/perf-core
%{_libexecdir}/perf-core/*
%{_mandir}/man[1-8]/perf*
%{_sysconfdir}/bash_completion.d/perf
%doc linux-%{KVERREL}/tools/perf/Documentation/examples.txt
%{_docdir}/perf-tip/tips.txt
%{_includedir}/perf/perf_dlfilter.h

%files -n python3-perf
%{python3_sitearch}/*

%if %{with_debuginfo}
%files -f perf-debuginfo.list -n perf-debuginfo

%files -f python3-perf-debuginfo.list -n python3-perf-debuginfo
%endif
# with_perf
%endif

%if %{with_libperf}
%files -n libperf
%{_libdir}/libperf.so.0
%{_libdir}/libperf.so.0.0.1

%files -n libperf-devel
%{_libdir}/libperf.so
%{_libdir}/pkgconfig/libperf.pc
%{_includedir}/internal/*.h
%{_includedir}/perf/bpf_perf.h
%{_includedir}/perf/core.h
%{_includedir}/perf/cpumap.h
%{_includedir}/perf/event.h
%{_includedir}/perf/evlist.h
%{_includedir}/perf/evsel.h
%{_includedir}/perf/mmap.h
%{_includedir}/perf/threadmap.h
%{_mandir}/man3/libperf.3.gz
%{_mandir}/man7/libperf-counting.7.gz
%{_mandir}/man7/libperf-sampling.7.gz
%{_docdir}/libperf/examples/sampling.c
%{_docdir}/libperf/examples/counting.c
%{_docdir}/libperf/html/libperf.html
%{_docdir}/libperf/html/libperf-counting.html
%{_docdir}/libperf/html/libperf-sampling.html

%if %{with_debuginfo}
%files -f libperf-debuginfo.list -n libperf-debuginfo
%endif

# with_libperf
%endif


%if %{with_tools}
%ifnarch %{cpupowerarchs}
%files -n %{package_name}-tools
%else
%files -n %{package_name}-tools -f cpupower.lang
%{_bindir}/cpupower
%{_datadir}/bash-completion/completions/cpupower
%ifarch x86_64
%{_bindir}/centrino-decode
%{_bindir}/powernow-k8-decode
%endif
%{_mandir}/man[1-8]/cpupower*
%ifarch x86_64
%{_bindir}/x86_energy_perf_policy
%{_mandir}/man8/x86_energy_perf_policy*
%{_bindir}/turbostat
%{_mandir}/man8/turbostat*
%{_bindir}/intel-speed-select
%{_sbindir}/intel_sdsi
%endif
# cpupowerarchs
%endif
%{_bindir}/tmon
%{_bindir}/bootconfig
%{_bindir}/iio_event_monitor
%{_bindir}/iio_generic_buffer
%{_bindir}/lsiio
%{_bindir}/lsgpio
%{_bindir}/gpio-hammer
%{_bindir}/gpio-event-mon
%{_bindir}/gpio-watch
%{_mandir}/man1/kvm_stat*
%{_bindir}/kvm_stat
%{_unitdir}/kvm_stat.service
%config(noreplace) %{_sysconfdir}/logrotate.d/kvm_stat
%{_bindir}/page_owner_sort
%{_bindir}/slabinfo
%if %{with_ynl}
%{_bindir}/ynl*
%{_docdir}/ynl
%{_datadir}/ynl
%{python3_sitelib}/pyynl*
%endif

%if %{with_debuginfo}
%files -f %{package_name}-tools-debuginfo.list -n %{package_name}-tools-debuginfo
%endif

%files -n %{package_name}-tools-libs
%ifarch %{cpupowerarchs}
%{_libdir}/libcpupower.so.1
%{_libdir}/libcpupower.so.1.0.1
%endif

%files -n %{package_name}-tools-libs-devel
%ifarch %{cpupowerarchs}
%{_libdir}/libcpupower.so
%{_includedir}/cpufreq.h
%{_includedir}/cpuidle.h
%{_includedir}/powercap.h
%endif
%if %{with_ynl}
%{_libdir}/libynl*
%{_includedir}/ynl
%endif

%files -n rtla
%{_bindir}/rtla
%{_bindir}/hwnoise
%{_bindir}/osnoise
%{_bindir}/timerlat
%{_mandir}/man1/rtla-hwnoise.1.gz
%{_mandir}/man1/rtla-osnoise-hist.1.gz
%{_mandir}/man1/rtla-osnoise-top.1.gz
%{_mandir}/man1/rtla-osnoise.1.gz
%{_mandir}/man1/rtla-timerlat-hist.1.gz
%{_mandir}/man1/rtla-timerlat-top.1.gz
%{_mandir}/man1/rtla-timerlat.1.gz
%{_mandir}/man1/rtla.1.gz

%files -n rv
%{_bindir}/rv
%{_mandir}/man1/rv-list.1.gz
%{_mandir}/man1/rv-mon-wip.1.gz
%{_mandir}/man1/rv-mon-wwnr.1.gz
%{_mandir}/man1/rv-mon.1.gz
%{_mandir}/man1/rv-mon-sched.1.gz
%{_mandir}/man1/rv.1.gz

# with_tools
%endif

%if %{with_selftests}
%files selftests-internal
%{_libexecdir}/ksamples
%{_libexecdir}/kselftests
%endif

# empty meta-package
%if %{with_up_base}
%ifnarch %nobuildarches noarch
%files
%endif
%endif

# This is %%{image_install_path} on an arch where that includes ELF files,
# or empty otherwise.
%define elf_image_install_path %{?kernel_image_elf:%{image_install_path}}

#
# This macro defines the %%files sections for a kernel package
# and its devel and debuginfo packages.
#	%%kernel_variant_files [-k vmlinux] <use_vdso> <condition> <subpackage>
#
%define kernel_variant_files(k:) \
%if %{2}\
%{expand:%%files %{?1:-f kernel-%{?3:%{3}-}ldsoconf.list} %{?3:%{3}-}core}\
%{!?_licensedir:%global license %%doc}\
%%license linux-%{KVERREL}/COPYING-%{version}-%{release}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/%{?-k:%{-k*}}%{!?-k:vmlinuz}\
%ghost /%{image_install_path}/%{?-k:%{-k*}}%{!?-k:vmlinuz}-%{KVERREL}%{?3:+%{3}}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/.vmlinuz.hmac \
%ghost /%{image_install_path}/.vmlinuz-%{KVERREL}%{?3:+%{3}}.hmac \
%ifarch aarch64 riscv64\
/lib/modules/%{KVERREL}%{?3:+%{3}}/dtb \
%ghost /%{image_install_path}/dtb-%{KVERREL}%{?3:+%{3}} \
%endif\
/lib/modules/%{KVERREL}%{?3:+%{3}}/System.map\
%ghost /boot/System.map-%{KVERREL}%{?3:+%{3}}\
%dir /lib/modules\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/symvers.%compext\
/lib/modules/%{KVERREL}%{?3:+%{3}}/config\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin*\
%ghost %attr(0644, root, root) /boot/symvers-%{KVERREL}%{?3:+%{3}}.%compext\
%ghost %attr(0600, root, root) /boot/initramfs-%{KVERREL}%{?3:+%{3}}.img\
%ghost %attr(0644, root, root) /boot/config-%{KVERREL}%{?3:+%{3}}\
%{expand:%%files -f kernel-%{?3:%{3}-}modules-core.list %{?3:%{3}-}modules-core}\
%dir /lib/modules\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}/kernel\
/lib/modules/%{KVERREL}%{?3:+%{3}}/build\
/lib/modules/%{KVERREL}%{?3:+%{3}}/source\
/lib/modules/%{KVERREL}%{?3:+%{3}}/updates\
/lib/modules/%{KVERREL}%{?3:+%{3}}/weak-updates\
/lib/modules/%{KVERREL}%{?3:+%{3}}/systemtap\
%{_datadir}/doc/kernel-keys/%{KVERREL}%{?3:+%{3}}\
%if %{1}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/vdso\
%endif\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.block\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.drm\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.modesetting\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.networking\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.order\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.alias\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.alias.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin.alias.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.dep\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.dep.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.devname\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.softdep\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.symbols\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.symbols.bin\
%ghost %attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/modules.weakdep\
%{expand:%%files -f kernel-%{?3:%{3}-}modules.list %{?3:%{3}-}modules}\
%{expand:%%files %{?3:%{3}-}devel}\
%defverify(not mtime)\
/usr/src/kernels/%{KVERREL}%{?3:+%{3}}\
%{expand:%%files %{?3:%{3}-}devel-matched}\
%{expand:%%files -f kernel-%{?3:%{3}-}modules-extra.list %{?3:%{3}-}modules-extra}\
%{expand:%%files -f kernel-%{?3:%{3}-}modules-internal.list %{?3:%{3}-}modules-internal}\
%if 0%{!?fedora:1}\
%{expand:%%files -f kernel-%{?3:%{3}-}modules-partner.list %{?3:%{3}-}modules-partner}\
%endif\
%if %{with_debuginfo}\
%ifnarch noarch\
%{expand:%%files -f debuginfo%{?3}.list %{?3:%{3}-}debuginfo}\
%endif\
%endif\
%if %{with_efiuki} && "%{3}" != "rt" && "%{3}" != "rt-debug" && "%{3}" != "rt-64k" && "%{3}" != "rt-64k-debug"\
%{expand:%%files %{?3:%{3}-}uki-virt}\
%dir /lib/modules\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}\
/lib/modules/%{KVERREL}%{?3:+%{3}}/System.map\
/lib/modules/%{KVERREL}%{?3:+%{3}}/symvers.%compext\
/lib/modules/%{KVERREL}%{?3:+%{3}}/config\
/lib/modules/%{KVERREL}%{?3:+%{3}}/modules.builtin*\
%attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/%{?-k:%{-k*}}%{!?-k:vmlinuz}-virt.efi\
%attr(0644, root, root) /lib/modules/%{KVERREL}%{?3:+%{3}}/.%{?-k:%{-k*}}%{!?-k:vmlinuz}-virt.efi.hmac\
%ghost /%{image_install_path}/efi/EFI/Linux/%{?-k:%{-k*}}%{!?-k:*}-%{KVERREL}%{?3:+%{3}}.efi\
%{expand:%%files %{?3:%{3}-}uki-virt-addons}\
%dir /lib/modules/%{KVERREL}%{?3:+%{3}}/%{?-k:%{-k*}}%{!?-k:vmlinuz}-virt.efi.extra.d/ \
/lib/modules/%{KVERREL}%{?3:+%{3}}/%{?-k:%{-k*}}%{!?-k:vmlinuz}-virt.efi.extra.d/*.addon.efi\
%endif\
%if %{?3:1} %{!?3:0}\
%{expand:%%files %{3}}\
%endif\
%if %{with_gcov}\
%ifnarch %nobuildarches noarch\
%{expand:%%files -f kernel-%{?3:%{3}-}gcov.list %{?3:%{3}-}gcov}\
%endif\
%endif\
%endif\
%{nil}

%kernel_variant_files %{_use_vdso} %{with_up_base}
%if %{with_up}
%kernel_variant_files %{_use_vdso} %{with_debug} debug
%endif
%if %{with_arm64_16k}
%kernel_variant_files %{_use_vdso} %{with_debug} 16k-debug
%endif
%if %{with_arm64_64k}
%kernel_variant_files %{_use_vdso} %{with_debug} 64k-debug
%endif
%kernel_variant_files %{_use_vdso} %{with_realtime_base} rt
%if %{with_realtime}
%kernel_variant_files %{_use_vdso} %{with_debug} rt-debug
%endif
%kernel_variant_files %{_use_vdso} %{with_automotive_base} automotive
%if %{with_automotive}
%kernel_variant_files %{_use_vdso} %{with_debug} automotive-debug
%endif
%if %{with_debug_meta}
%files debug
%files debug-core
%files debug-devel
%files debug-devel-matched
%files debug-modules
%files debug-modules-core
%files debug-modules-extra
%if %{with_arm64_16k}
%files 16k-debug
%files 16k-debug-core
%files 16k-debug-devel
%files 16k-debug-devel-matched
%files 16k-debug-modules
%files 16k-debug-modules-extra
%endif
%if %{with_arm64_64k}
%files 64k-debug
%files 64k-debug-core
%files 64k-debug-devel
%files 64k-debug-devel-matched
%files 64k-debug-modules
%files 64k-debug-modules-extra
%endif
%endif
%kernel_variant_files %{_use_vdso} %{with_zfcpdump} zfcpdump
%kernel_variant_files %{_use_vdso} %{with_arm64_16k_base} 16k
%kernel_variant_files %{_use_vdso} %{with_arm64_64k_base} 64k
%kernel_variant_files %{_use_vdso} %{with_realtime_arm64_64k_base} rt-64k
%if %{with_realtime_arm64_64k}
%kernel_variant_files %{_use_vdso} %{with_debug} rt-64k-debug
%endif

%files modules-extra-matched

# plz don't put in a version string unless you're going to tag
# and build.
#
#
%changelog
* Thu Jul 17 2025 Augusto Caringi <acaringi@redhat.com> [6.15.7-0]
- Linux v6.15.7

* Thu Jul 10 2025 Augusto Caringi <acaringi@redhat.com> [6.15.6-0]
- Turn on MITIGATION_TSA for RHEL configs (Augusto Caringi)
- Turn on TSA Mitigation for Fedora (Justin M. Forbes)
- Linux v6.15.6

* Sun Jul 06 2025 Justin M. Forbes <jforbes@fedoraproject.org> [6.15.5-0]
- io_uring: gate REQ_F_ISREG on !S_ANON_INODE as well (Jens Axboe)
- Linux v6.15.5

* Fri Jun 27 2025 Justin M. Forbes <jforbes@fedoraproject.org> [6.15.4-0]
- redhat: Restore the status quo wrt memory onlining (Vitaly Kuznetsov) [2375049]
- Linux v6.15.4

* Thu Jun 19 2025 Justin M. Forbes <jforbes@fedoraproject.org> [6.15.3-0]
- ACPICA: Refuse to evaluate a method if arguments are missing (Rafael J. Wysocki)
- Linux v6.15.3

* Fri Jun 13 2025 Justin M. Forbes <jforbes@fedoraproject.org> [6.15.2-0]
- wifi: ath12k: support MLO as well if single_chip_mlo_support flag is set (Baochen Qiang)
- wifi: ath12k: use fw_features only when it is valid (Baochen Qiang)
- wifi: ath12k: introduce ath12k_fw_feature_supported() (Baochen Qiang)
- aarch64: Switch TI_SCI_CLK and TI_SCI_PM_DOMAINS symbols to built-in (Peter Robinson)
- redhat/configs: fedora: set some qcom clk, icc, and pinctrl drivers to built in (Brian Masney)

* Tue Jun 10 2025 Justin M. Forbes <jforbes@fedoraproject.org> [6.15.2-0]
- Revert "drm/amd/display: more liberal vmin/vmax update for freesync" (Justin M. Forbes)
- Linux v6.15.2

* Wed Jun 04 2025 Justin M. Forbes <jforbes@fedoraproject.org> [6.15.1-0]
- arm64: dts: rockchip: Drop assigned-clock* from cpu nodes on rk3588 (Diederik de Haas)
- arm64: dts: rockchip: Improve LED config for NanoPi R5S (Diederik de Haas)
- arm64: dts: rockchip: Move rk3568 PCIe3 MSI to use GIC ITS (Chukun Pan)
- arm64: dts: rockchip: Update eMMC for NanoPi R5 series (Peter Robinson)
- arm64: dts: rockchip: Add vcc-supply to SPI flash on rk3566-rock3c (Peter Robinson)
- arm64: dts: rockchip: Add vcc-supply to SPI flash on rk3566-quartz64-b (Diederik de Haas)
- arm64: dts: rockchip: Add phy-supply to gmac0 on NanoPi R5S (Diederik de Haas)
- arm64: dts: rockchip: Add vcc-supply to SPI flash on rk3588-rock-5b (Diederik de Haas)
- arm64: dts: rockchip: Add vcc-supply to SPI flash on rk3399-rockpro64 (Diederik de Haas)
- arm64: dts: rockchip: Add vcc-supply to SPI flash on rk3328-rock64 (Diederik de Haas)
- arm64: dts: rockchip: Move SHMEM memory to reserved memory on rk3588 (Chukun Pan)
- arm64: dts: rockchip: Add gmac phy reset GPIO to QNAP TS433 (Uwe Kleine-König)
- arm64: dts: rockchip: Correct gmac phy address on QNAP TS433 (Uwe Kleine-König)
- Reset build id for fedora-srpm script (Justin M. Forbes)
- redhat/configs: Add configs for new ov02c10 and ov02e10 drivers (Hans de Goede)
- media: i2c: Add Omnivision OV02C10 sensor driver (Heimir Thor Sverrisson)
- media: i2c: ov02e10: add OV02E10 image sensor driver (Jingjing Xiong)
- platform/x86: int3472: Debug log when remapping pins (Hans de Goede)
- platform/x86: int3472: Add handshake pin support (Hans de Goede)
- platform/x86: int3472: Prepare for registering more than 1 GPIO regulator (Hans de Goede)
- platform/x86: int3472: Avoid GPIO regulator spikes (Hans de Goede)
- platform/x86: int3472: Make regulator supply name configurable (Hans de Goede)
- platform/x86: int3472: Rework AVDD second sensor quirk handling (Hans de Goede)
- platform/x86: int3472: Drop unused gpio field from struct int3472_gpio_regulator (Hans de Goede)
- platform/x86: int3472: Stop setting a supply-name for GPIO regulators (Hans de Goede)
- platform/x86: int3472: Add skl_int3472_register_clock() helper (Hans de Goede)
- powerpc: Fix struct termio related ioctl macros (Madhavan Srinivasan)
- Initial setup for stable Fedora releases (Justin M. Forbes)
- Reset RHEL_RELEASE for the 6.16 cycle (Justin M. Forbes)
- fedora: add 'fedora' SBAT suffix for UKI addons (Li Tian)
- redhat: add downstream SBAT for UKI addons (Emanuele Giuseppe Esposito)
- uki_addons: provide custom SBAT as input parameter (Emanuele Giuseppe Esposito)
- uki_addons: remove completely sbat/sbat.conf (Emanuele Giuseppe Esposito)
- Linux v6.15.1

* Mon May 26 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-60]
- Consolidate configs to common for 6.15 (Justin M. Forbes)
- Linux v6.15.0

* Thu May 22 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc7.d608703fcdd9.59]
- Linux v6.15.0-0.rc7.d608703fcdd9

* Wed May 21 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc7.4a95bc121ccd.58]
- redhat/configs: automotive: enable MHI_BUS_EP (Eric Chanudet)
- Fix PHYSICAL_ALIGN for x86 Fedora (Justin M. Forbes)
- Switch ZSWAP_ZPOOL_DEFAULT to ZSMALLOC as ZBUD has been removed (Justin M. Forbes)
- redhat: configs: rhel: Enable CX231XX drivers (Kate Hsuan)
- configs: add redhat/configs/common/generic/CONFIG_OBJTOOL_WERROR (Ryan Sullivan) [RHEL-85301]
- redhat: make ENABLE_WERROR also enable OBJTOOL_WERROR (Ryan Sullivan) [RHEL-85301]
- redhat/configs: Enable CONFIG_X86_POSTED_MSI (Jerry Snitselaar)
- Linux v6.15.0-0.rc7.4a95bc121ccd

* Mon May 19 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc7.57]
- redhat/configs: remove CRC16 config files (Scott Weaver)
- Linux v6.15.0-0.rc7

* Sun May 18 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.5723cc3450bc.56]
- Revert CONFIG_GENKSYMS in pending for x86 (Justin M. Forbes)
- Linux v6.15.0-0.rc6.5723cc3450bc

* Sat May 17 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.172a9d94339c.55]
- Linux v6.15.0-0.rc6.172a9d94339c

* Fri May 16 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.fee3e843b309.54]
- Linux v6.15.0-0.rc6.fee3e843b309

* Thu May 15 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.088d13246a46.53]
- Flip GENKSYMS for RHEL (Justin M. Forbes)
- Linux v6.15.0-0.rc6.088d13246a46

* Thu May 15 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.9f35e33144ae.52]
- Move MITIGATION_ITS to the x86 directory (Justin M. Forbes)
- Set MITIGATION_ITS for Fedora (Justin M. Forbes)
- Fedora: arm: Updates for QCom devices (Souradeep Chowdhury)

* Wed May 14 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.9f35e33144ae.51]
- redhat/configs: Explicitly disable CONFIG_VIRTIO_MEM on powerpc in RHEL (Thomas Huth)
- redhat/configs: Consolidate the CONFIG_AP_DEBUG config switch (Thomas Huth)
- Linux v6.15.0-0.rc6.9f35e33144ae

* Tue May 13 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.e9565e23cd89.50]
- Set Fedora configs for 6.15 (Justin M. Forbes)
- Linux v6.15.0-0.rc6.e9565e23cd89

* Mon May 12 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc6.49]
- Shorten the uname for git snapshots (Justin M. Forbes)
- Linux v6.15.0-0.rc6

* Sun May 11 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.3ce9925823c7.48]
- Linux v6.15.0-0.rc5.3ce9925823c7

* Sat May 10 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.1a33418a69cc.47]
- nvme: explicitly enable the nvme keyring (Maurizio Lombardi)
- Linux v6.15.0-0.rc5.1a33418a69cc

* Fri May 09 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.9c69f8884904.46]
- Enable the gs_usb CAN bus driver in RHEL (Radu Rendec)
- Stop disabling some modules needed to run on Azure (Pierre-Yves Chibon)
- redhat/configs: enable ACPI_DEBUG on non-debug kernels (Mark Langsdorf)
- specfile:  add with_toolsonly variable to build only tools packages (Clark Williams)
- redhat/configs: Enable CONFIG_TYPEC_TBT_ALTMODE in RHEL (Desnes Nunes) [RHEL-78931]
- Linux v6.15.0-0.rc5.9c69f8884904

* Thu May 08 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.d76bb1ebb558.45]
- Linux v6.15.0-0.rc5.d76bb1ebb558

* Wed May 07 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.0d8d44db295c.44]
- Linux v6.15.0-0.rc5.0d8d44db295c

* Tue May 06 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.01f95500a162.43]
- Linux v6.15.0-0.rc5.01f95500a162

* Mon May 05 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc5.42]
- Linux v6.15.0-0.rc5

* Sun May 04 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.e8ab83e34bdc.41]
- Linux v6.15.0-0.rc4.e8ab83e34bdc

* Sat May 03 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.95d3481af6dc.40]
- Turn on ACPI_DEBUG for Fedora (Justin M. Forbes)
- redhat: fix kernel-rt-kvm package removal for Fedora (Thorsten Leemhuis)
- Linux v6.15.0-0.rc4.95d3481af6dc

* Fri May 02 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.ebd297a2affa.39]
- redhat/configs: aarch64: Enable Apple touchbar display driver for Fedora (Neal Gompa)
- Linux v6.15.0-0.rc4.ebd297a2affa

* Thu May 01 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.4f79eaa2ceac.38]
- redhat: remove kernel-rt-kvm package (Clark Williams)
- redhat: introduce modules-extra-matched meta package (Jan Stancek)
- Fix up some Netfilter configs for Fedora (Justin M. Forbes)
- Turn NF_CT_NETLINK_TIMEOUT for Fedora (Justin M. Forbes)
- Turn on NF_CONNTRACK_TIMEOUT for Fedora (Justin M. Forbes)
- Linux v6.15.0-0.rc4.4f79eaa2ceac

* Wed Apr 30 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.b6ea1680d0ac.37]
- redhat/configs: Adjust CONFIG_TUNE for s390x (Mete Durlu)
- Linux v6.15.0-0.rc4.b6ea1680d0ac

* Tue Apr 29 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.ca91b9500108.36]
- redhat/spec: fix selftests dependencies (Gregory Bell) [RHEL-88228]
- redhat: add namespace selftests to kernel-modules-internal package (Joel Savitz) [RHEL-88635]
- Turn off CONFIG_PCI_REALLOC_ENABLE_AUTO for Fedora (Justin M. Forbes)
- Linux v6.15.0-0.rc4.ca91b9500108

* Mon Apr 28 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc4.35]
- Linux v6.15.0-0.rc4

* Sun Apr 27 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.5bc1018675ec.34]
- Linux v6.15.0-0.rc3.5bc1018675ec

* Sat Apr 26 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.f1a3944c860b.33]
- Linux v6.15.0-0.rc3.f1a3944c860b

* Fri Apr 25 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.02ddfb981de8.32]
- gitlab-ci: enable pipelines for rt-64k (Clark Williams)
- rt-64k:  Enable building 64k page-size RT kernel (Clark Williams)
- Linux v6.15.0-0.rc3.02ddfb981de8

* Thu Apr 24 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.a79be02bba5c.31]
- redhat: drop Y issues from changelog (Jan Stancek)
- redhat/configs: Update the CONFIG_KERNEL_IMAGE_BASE kernel config option (Thomas Huth)
- redhat/configs: Remove the obsolete CONFIG_ZCRYPT_DEBUG switches (Thomas Huth)
- redhat/configs: Consolidate the CONFIG_AP switch (Thomas Huth)
- Linux v6.15.0-0.rc3.a79be02bba5c

* Wed Apr 23 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.bc3372351d0c.30]
- Linux v6.15.0-0.rc3.bc3372351d0c

* Tue Apr 22 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.a33b5a08cbbd.29]
- fedora: updates for 6.15 (Peter Robinson)
- redhat/configs: Disable CONFIG_COMPAT option on s390 (Mete Durlu) [RHEL-24047]
- Linux v6.15.0-0.rc3.a33b5a08cbbd

* Mon Apr 21 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc3.9d7a0577c9db.28]
- Linux v6.15.0-0.rc3.9d7a0577c9db

* Sun Apr 20 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.6fea5fabd332.27]
- Linux v6.15.0-0.rc2.6fea5fabd332

* Sat Apr 19 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.8560697b23dc.26]
- uki: Add weak dependency on 'uki-direct' (Vitaly Kuznetsov)
- redhat/kernel.spec: fix duplicate packaging of ynl headers (Jan Stancek)
- Enable FunctionFS on aarch64 + x86 (Sam Day)
- Linux v6.15.0-0.rc2.8560697b23dc

* Fri Apr 18 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.fc96b232f8e7.25]
- Turn on USB Gadget for Fedora x86 (Justin M. Forbes)
- Linux v6.15.0-0.rc2.fc96b232f8e7

* Thu Apr 17 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.cfb2e2c57aef.24]
- redhat: enable drm panic screen with a QR code (Scott Weaver)
- redhat: enable Rust code in ELN (Scott Weaver)
- redhat: strip leading '(' in dist-get-buildreqs (Jan Stancek)
- Linux v6.15.0-0.rc2.cfb2e2c57aef

* Wed Apr 16 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.1a1d569a75f3.23]
- Linux v6.15.0-0.rc2.1a1d569a75f3

* Tue Apr 15 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.834a4a689699.22]
- Linux v6.15.0-0.rc2.834a4a689699

* Mon Apr 14 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc2.21]
- Linux v6.15.0-0.rc2

* Sun Apr 13 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.7cdabafc0012.20]
- Linux v6.15.0-0.rc1.7cdabafc0012

* Sat Apr 12 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.3bde70a2c827.19]
- Linux v6.15.0-0.rc1.3bde70a2c827

* Fri Apr 11 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.900241a5cc15.18]
- Linux v6.15.0-0.rc1.900241a5cc15

* Thu Apr 10 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.3b07108ada81.17]
- Linux v6.15.0-0.rc1.3b07108ada81

* Wed Apr 09 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.a24588245776.16]
- Fix up CONFIG_CRC_ITU_T mismatch (Scott Weaver)
- Fix up CONFIG_CRC16 mismatch (Scott Weaver)
- Linux v6.15.0-0.rc1.a24588245776

* Wed Apr 09 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.15]
- redhat: remove kernel-ipaclones-internal package (Joe Lawrence)
- redhat/kernel.spec.template: add net packetdrill selftests (Hangbin Liu)
- redhat/kernel.spec.template: Build rtla with BPF sample collection (Tomas Glozar)

* Tue Apr 08 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.14]
- redhat/configs: automotive: Enable CONFIG_BOOTPARAM_HUNG_TASK_PANIC config (Dorinda Bassey)
- samples/bpf: fix build (Gregory Bell)
- redhat: create 'systemd-volatile-overlay' addon for UKI (Emanuele Giuseppe Esposito)

* Mon Apr 07 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc1.13]
- fedora: arm64: move some TI drivers to modular (Peter Robinson)
- fedora: minor cleanups for 6.14 (Peter Robinson)
- redhat/configs: enable CONFIG_I2C_MUX_PCA954x on x86 (Michal Schmidt)
- Linux v6.15.0-0.rc1

* Sun Apr 06 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc0.f4d2ef48250a.12]
- Linux v6.15.0-0.rc0.f4d2ef48250a

* Sat Apr 05 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc0.a8662bcd2ff1.11]
- Linux v6.15.0-0.rc0.a8662bcd2ff1

* Fri Apr 04 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc0.e48e99b6edf4.10]
- Linux v6.15.0-0.rc0.e48e99b6edf4

* Thu Apr 03 2025 Fedora Kernel Team <kernel-team@fedoraproject.org> [6.15.0-0.rc0.a2cc6ff5ec8f.9]
- redhat: bump RHEL_MAJOR (Jan Stancek)
- redhat/configs: enable CONFIG_AMD_3D_VCACHE for x86 on RHEL (David Arcari)
- Linux v6.15.0-0.rc0.a2cc6ff5ec8f


###
# The following Emacs magic makes C-c C-e use UTC dates.
# Local Variables:
# rpm-change-log-uses-utc: t
# End:
###
