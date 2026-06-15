#!/bin/zsh
set -euo pipefail

install_bundle() {
    local source_app="$1"
    local target_app="$2"
    local backup_app="${target_app}.previous"

    /bin/rm -rf "$backup_app"
    if [[ -e "$target_app" ]]; then
        /bin/mv "$target_app" "$backup_app"
    fi

    if ! /usr/bin/ditto "$source_app" "$target_app"; then
        /bin/rm -rf "$target_app"
        if [[ -e "$backup_app" ]]; then
            /bin/mv "$backup_app" "$target_app"
        fi
        return 1
    fi

    /bin/rm -rf "$backup_app"
}

if [[ "${1:-}" == "--install" ]]; then
    install_bundle "$2" "$3"
    exit 0
fi

if [[ "$#" -ne 4 ]]; then
    exit 64
fi

zip_path="$1"
target_app="$2"
app_pid="$3"
expected_bundle_id="$4"
self_path="${0:A}"
helper_dir="${self_path:h}"
log_file="${TMPDIR:-/tmp}/mvr_psp_update.log"
extract_dir=""

exec >>"$log_file" 2>&1

cleanup() {
    if [[ -n "$extract_dir" ]]; then
        /bin/rm -rf "$extract_dir"
    fi
    /bin/rm -f "$zip_path"
    /bin/rm -rf "$helper_dir"
}
trap cleanup EXIT

for _ in {1..480}; do
    if ! /bin/kill -0 "$app_pid" 2>/dev/null; then
        break
    fi
    /bin/sleep 0.25
done

if /bin/kill -0 "$app_pid" 2>/dev/null; then
    print -u2 "Timed out waiting for the app to close."
    exit 70
fi

extract_dir="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/mvr_psp_extract.XXXXXX")"
/usr/bin/ditto -x -k "$zip_path" "$extract_dir"

source_app=""
if [[ -d "$extract_dir/MVR PSP Check.app" ]]; then
    source_app="$extract_dir/MVR PSP Check.app"
else
    for container_dir in "$extract_dir"/*(/N); do
        if [[ -d "$container_dir/MVR PSP Check.app" ]]; then
            source_app="$container_dir/MVR PSP Check.app"
            break
        fi
    done
fi

if [[ -z "$source_app" ]]; then
    print -u2 "The update archive does not contain MVR PSP Check.app."
    exit 65
fi

bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$source_app/Contents/Info.plist")"
if [[ "$bundle_id" != "$expected_bundle_id" ]]; then
    print -u2 "Unexpected bundle identifier: $bundle_id"
    exit 66
fi

if [[ ! -x "$source_app/Contents/MacOS/MVR_PSP_Check" ]]; then
    print -u2 "The update archive is missing the main executable."
    exit 67
fi

/usr/bin/codesign --verify --deep --strict "$source_app"

target_parent="${target_app:h}"
if [[ -w "$target_parent" ]]; then
    install_bundle "$source_app" "$target_app"
else
    admin_command="/bin/zsh ${(q)self_path} --install ${(q)source_app} ${(q)target_app}"
    /usr/bin/osascript - "$admin_command" <<'APPLESCRIPT'
on run argv
    do shell script (item 1 of argv) with administrator privileges
end run
APPLESCRIPT
fi

/usr/bin/open "$target_app"
