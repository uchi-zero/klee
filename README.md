# SUCOL

requires: LLVM-13, clang-13, lit, gperftools, cmake, sqlite, ninja, z3

```sh
# get the repo
git clone --recursive git@github.com:uchi-zero/klee.git

# build the klee-uclibc
cd 3rd/klee-uclibc
./configure --make-llvm-lib # --with-cc clang-13 --with-llvm-config llvm-config-13
make -j $nproc

# build klee
cmake -B build -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DLLVMCC=$(which clang) -DLLVMCXX=$(which clang++) -DENABLE_SOLVER_Z3=ON -DENABLE_POSIX_RUNTIME=ON -DKLEE_UCLIBC_PATH=$PWD/3rd/klee-uclibc -DENABLE_UNIT_TESTS=OFF

```

## Add new test targets

modify the `justfile` in the `examples/` directory.
