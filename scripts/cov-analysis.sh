#!/usr/bin/env bash

# @option -e --extension=A_data Test case extension
# @option -o --output-dir=cov-reports Directory to write coverage output
# @option -b --binary! Binary to run
# @option -a --args Options to pass to the binary
# @arg input-dir! Directory containing test cases

eval "$(argc --argc-eval "$0" "$@")"

tmpdir=$(mktemp -d)
PROFDATA=fuzz.profdata

if [[ ! -f "$argc_binary" ]]; then
    echo "Binary $argc_binary does not exist"
    exit 1
fi

if [[ ! -d "$argc_input_dir" ]]; then
    echo "Corpus directory $argc_input_dir does not exist"
    exit 1
else
    ./build/bin/ktest-tool --extract "$argc_extension" "$argc_input_dir"/*.ktest
fi

if [[ -d "$argc_output_dir" ]]; then
    echo -e "\033[33mWarning:\033[0m output directory $argc_output_dir already exists, it will be overwritten" >&2
    rm -rf "$argc_output_dir"
fi

i=0
for f in "$argc_input_dir"/*."$argc_extension"; do
    LLVM_PROFILE_FILE="$tmpdir/fuzz-${i}.profraw" $argc_binary "${argc_args[@]}" "$f"
    i=$((i+1))
    echo "Processed $f"
done


llvm-profdata merge -sparse "$tmpdir"/*.profraw -o "$tmpdir/$PROFDATA"

llvm-cov show "$argc_binary" -instr-profile="$tmpdir/$PROFDATA" \
    -format=html -output-dir="$argc_output_dir" \
    -ignore-filename-regex='.*(/usr/include|/toolchain/).*'

llvm-cov report "$argc_binary" -instr-profile="$tmpdir/$PROFDATA"

rm -r "$tmpdir"
