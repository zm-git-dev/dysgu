from setuptools import setup, find_packages
import setuptools
from setuptools.extension import Extension
from Cython.Build import cythonize
import numpy
from distutils import ccompiler
import os
import pysam
import glob
from sys import argv
import subprocess
import sysconfig


# Note building htslib for OSX version might need to be set: make CXXFLAGS="-mmacosx-version-min=10.09"

# Remove the "-Wstrict-prototypes" compiler option, which isn't valid for C++.
# https://stackoverflow.com/questions/8106258/cc1plus-warning-command-line-option-wstrict-prototypes-is-valid-for-ada-c-o
import distutils.sysconfig
cfg_vars = distutils.sysconfig.get_config_vars()
for key, value in cfg_vars.items():
    if type(value) == str:
        cfg_vars[key] = value.replace("-Wstrict-prototypes", "")


# This was stolen from pybind11
# https://github.com/pybind/python_example/blob/master/setup.py
# As of Python 3.6, CCompiler has a `has_flag` method.
# cf http://bugs.python.org/issue26689
def has_flag(compiler, flagname):
    """Return a boolean indicating whether a flag name is supported on
    the specified compiler.
    """
    import tempfile

    with tempfile.NamedTemporaryFile('w', suffix='.cpp') as f:
        f.write('int main (int argc, char **argv) { return 0; }')
        try:
            compiler.compile([f.name], extra_postargs=[flagname])
        except setuptools.distutils.errors.CompileError:
            return False
    return True


def cpp_flag(compiler, flags):
    """Return the -std=c++[11/14/17,20] compiler flag.
    The newer version is prefered over c++11 (when it is available).
    """
    for flag in flags:
        if has_flag(compiler, flag):
            return flag


def get_extra_args():
    compiler = ccompiler.new_compiler()
    extra_compile_args = []
    flags = ['-std=c++17', '-std=c++14', '-std=c++11']
    f = cpp_flag(compiler, flags)
    if not f:
        return ['-std=c++11']
    extra_compile_args.append(f)
    flags = ['-stdlib=libc++']
    f = cpp_flag(compiler, flags)
    if f:
        extra_compile_args.append(f)

    return extra_compile_args


# clang = False
# icc = False
# try:
#     if os.environ['CC'] == "clang":
#         clang = True
# except KeyError:
#     pass
#
# if not clang:
#     try:
#         if subprocess.check_output(
#                 ["gcc", "--version"],
#                 universal_newlines=True).find("clang") != -1:
#             clang = True
#     except (subprocess.CalledProcessError, FileNotFoundError):
#         pass
#
# try:
#     if os.environ['CC'] == "icc":
#         icc = True
# except KeyError:
#     pass

extras = get_extra_args() + ["-Wno-sign-compare", "-Wno-unused-function",
                             "-Wno-unused-result", '-Wno-ignored-qualifiers',
                             "-Wno-deprecated-declarations", '-Wno-volatile'
                             ]

ext_modules = list()

root = os.path.abspath(os.path.dirname(__file__))
# Try and link dynamically to htslib
htslib = None
if "--htslib" in argv:
    idx = argv.index("--htslib")
    h = argv[idx + 1]
    if h and os.path.exists(h):
        if any("libhts" in i for i in glob.glob(h + "/*")):
            print("Using --htslib at {}".format(h))
            htslib = h
            if htslib[-1] == "/":
                htslib = htslib[:-1]
            argv.remove("--htslib")
            argv.remove(h)
    else:
        raise ValueError("--htslib path does not exists")


if htslib is None:
    print("Using packaged htslib")
    htslib = os.path.join(root, "dysgu/htslib")


libraries = [f"{htslib}/hts"]
library_dirs = [htslib, numpy.get_include(), f"{htslib}/htslib"] + pysam.get_include()
include_dirs = [numpy.get_include(), root,
                f"{htslib}/htslib", f"{htslib}/cram"] + pysam.get_include()
runtime_dirs = [htslib]

# Dysgu
print("Libs", libraries)
print("Library dirs", library_dirs)
print("Include dirs", include_dirs)
print("Runtime dirs", runtime_dirs)
print("Extras compiler args", extras)

# Scikit-bio module
ssw_extra_compile_args = ["-Wno-deprecated-declarations", '-std=c99', '-I.']
# if icc or sysconfig.get_config_vars()['CC'] == 'icc':
#     ssw_extra_compile_args.extend(['-qopenmp-simd', '-DSIMDE_ENABLE_OPENMP'])
# elif not (clang or sysconfig.get_config_vars()['CC'] == 'clang'):
#     ssw_extra_compile_args.extend(['-fopenmp-simd', '-DSIMDE_ENABLE_OPENMP'])

ext_modules.append(Extension(f"dysgu.scikitbio._ssw_wrapper",
                             [f"dysgu/scikitbio/_ssw_wrapper.pyx", f"dysgu/scikitbio/ssw.c"],
                             include_dirs=[f"{root}/dysgu/scikitbio", numpy.get_include()],
                             extra_compile_args=ssw_extra_compile_args,
                             # define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
                             language="c"))


# Dysgu modules
for item in ["sv2bam", "io_funcs", "graph", "coverage", "assembler", "call_component",
             "map_set_utils", "cluster", "post_call_metrics", "sv_category"]:

    ext_modules.append(Extension(f"dysgu.{item}",
                                 [f"dysgu/{item}.pyx"],
                                 libraries=libraries,
                                 library_dirs=library_dirs,
                                 include_dirs=include_dirs,
                                 runtime_library_dirs=runtime_dirs,
                                 extra_compile_args=extras,

                                 define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
                                 language="c++"))


print("Found packages", find_packages(where="."))
setup(
    name="dysgu",
    author="Kez Cleal",
    author_email="clealk@cardiff.ac.uk",
    url="https://github.com/kcleal/dysgu",
    description="Structural variant calling",
    license="MIT",
    version='1.3.13',
    python_requires='>=3.7',
    install_requires=[  # runtime requires
            'cython',
            'click>=8.0',
            'numpy>=1.18',
            'scipy',
            'pandas',
            'pysam',
            'networkx>=2.4',
            'scikit-learn>=0.22',
            'sortedcontainers',
            'lightgbm',
            'edlib',
        ],
    setup_requires=[
            'cython',
            'click>=8.0',
            'numpy>=1.18',
            'scipy',
            'pandas',
            'pysam',
            'networkx>=2.4',
            'scikit-learn>=0.22',
            'sortedcontainers',
            'lightgbm',
            'edlib'
        ],  # setup.py requires at compile time
    packages=["dysgu", "dysgu.tests", "dysgu.scikitbio"],
    ext_modules=cythonize(ext_modules),

    include_package_data=True,
    zip_safe=False,
    entry_points='''
        [console_scripts]
        dysgu=dysgu.main:cli
    ''',
)
