#!/bin/bash
set -euo pipefail
set -x

check_dependencies() {
    local dependencies=("nuitka3" "patchelf" "fusermount" "shar" "file")
    for cmd in "${dependencies[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "Error: $cmd is not installed. Please install it and try again."
            exit 1
        fi
    done
}

compile_python_script() {
    nuitka3 --standalone --follow-imports "$1" \
            --include-data-file="${LIBFUSE_SO_PATH}=./libfuse.so" \
            --output-dir="$2"
}

copy_libraries() {
    local -r executable="$1"
    local -r dist_dir="$2"
    local lib deps

    copy_deps_recursive() {
        local lib="$1"
        local deps=$(ldd "$lib" | grep '=>' | grep -v 'not found' | awk '{print $3}')
        for dep in $deps; do
            local abs_source=$(readlink -f "$dep")
            local abs_dest=$(readlink -f "$dist_dir/$(basename "$dep")")
            if [[ ! -f "$abs_dest" ]]; then
                cp "$abs_source" "$abs_dest"
                copy_deps_recursive "$abs_source"
            fi
        done
    }

    copy_deps_recursive "$executable"
}

adjust_executable() {
    local loader_path=$(readelf -l "$1" | awk '/program interpreter/ {print $4}' | tr -d ']')
    local loader_name=$(basename "$loader_path")
    patchelf --set-interpreter "./$loader_name" "$1"
    patchelf --set-rpath '$ORIGIN' "$1"
}

create_self_extracting_script() {
    (cd "$1" && shar -x -D * > "../../$2.sh")
    sed "s|exit 0|FUSE_LIBRARY_PATH=/proc/self/cwd/libfuse.so ./$2.bin \"\$@\"|g" -i "$2.sh"
    chmod a+x "$2.sh"
    echo "$2.sh"
}

copy_fusermount() {
    local fusermount_path=$(command -v fusermount)
    [[ -n "$fusermount_path" ]] && cp "$fusermount_path" "$1" || echo "Warning: fusermount binary not found. Skipping copy."
}

cleanup() {
    rm -rf "./build"
}

main() {
    [[ "$#" -ne 1 ]] && echo "Usage: $0 path_to_your_python_script.py" && exit 1
    check_dependencies
    local python_script="$1"
    local executable_name=$(basename "$python_script" .py)
    local build_dir="./build"
    local dist_dir="$build_dir/$executable_name.dist"
    local executable="$dist_dir/$executable_name.bin"
    compile_python_script "$python_script" "$build_dir"

    process_executable() {
        local -r executable="$1"
        local -r dist_dir="$2"
        copy_libraries "$executable" "$dist_dir"
        adjust_executable "$executable"
    }

    process_executable "$executable" "$dist_dir"
    copy_fusermount "$dist_dir"
    local self_extracting_script=$(create_self_extracting_script "$dist_dir" "$executable_name")
    cleanup
    echo "Info: Self-extracting script created: $self_extracting_script"
}

main "$@"

