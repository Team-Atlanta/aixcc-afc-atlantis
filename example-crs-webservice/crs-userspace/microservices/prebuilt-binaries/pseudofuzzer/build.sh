#!/bin/bash

set -e

cd `dirname $0`

: "${LIBCXX_PATH:=/usr/lib/libc++.a}"
: "${CARGO_BUILD_FLAGS=}"

if [ "$CARGO_BUILD_FLAGS" == "--release" ]; then
    export LIBFUZZER_PATH=target/release/libfuzzer.a
else 
    export LIBFUZZER_PATH=target/debug/libfuzzer.a
fi

cargo build $CARGO_BUILD_FLAGS

clang -shared -o libfuzzer.so \
-lpthread -lm -lrt -ldl \
-Wl,--whole-archive \
$LIBFUZZER_PATH \
$LIBCXX_PATH \
src/libfuzzer_main.c \
-Wl,--no-whole-archive
