#!/bin/sh
set -eu

REPOSITORY=francescoVaglienti/vibemin
INSTALL_DIR=${VIBEMIN_INSTALL_DIR:-"$HOME/.local/bin"}
VERSION=${VIBEMIN_VERSION:-}

case "$(uname -s)" in
    Darwin) PLATFORM=macos ;;
    Linux) PLATFORM=linux ;;
    *)
        printf '%s\n' 'This installer supports macOS and Linux.' >&2
        printf '%s\n' 'Windows binaries are available from the GitHub Releases page.' >&2
        exit 2
        ;;
esac

case "$(uname -m)" in
    x86_64|amd64) ARCHITECTURE=x86_64 ;;
    arm64|aarch64) ARCHITECTURE=aarch64 ;;
    *)
        printf 'Unsupported architecture: %s\n' "$(uname -m)" >&2
        exit 2
        ;;
esac

ARCHIVE="vibemin-$PLATFORM-$ARCHITECTURE.zip"
if [ -n "$VERSION" ]; then
    case "$VERSION" in v*) TAG=$VERSION ;; *) TAG="v$VERSION" ;; esac
    RELEASE_URL="https://github.com/$REPOSITORY/releases/download/$TAG"
else
    RELEASE_URL="https://github.com/$REPOSITORY/releases/latest/download"
fi

for required_command in curl unzip install; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        printf 'Required command is unavailable: %s\n' "$required_command" >&2
        exit 2
    fi
done

TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/vibemin-install.XXXXXX")
trap 'rm -rf "$TEMP_DIR"' EXIT HUP INT TERM

printf 'Downloading %s...\n' "$ARCHIVE"
curl --fail --location --silent --show-error "$RELEASE_URL/$ARCHIVE" \
    --output "$TEMP_DIR/$ARCHIVE"
curl --fail --location --silent --show-error "$RELEASE_URL/SHA256SUMS" \
    --output "$TEMP_DIR/SHA256SUMS"

EXPECTED=$(awk -v archive="$ARCHIVE" '$2 == archive { print $1 }' "$TEMP_DIR/SHA256SUMS")
if [ -z "$EXPECTED" ]; then
    printf 'No checksum was published for %s.\n' "$ARCHIVE" >&2
    exit 2
fi
if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL=$(sha256sum "$TEMP_DIR/$ARCHIVE" | awk '{ print $1 }')
elif command -v shasum >/dev/null 2>&1; then
    ACTUAL=$(shasum -a 256 "$TEMP_DIR/$ARCHIVE" | awk '{ print $1 }')
else
    printf '%s\n' 'A SHA-256 utility is required to verify the download.' >&2
    exit 2
fi
if [ "$ACTUAL" != "$EXPECTED" ]; then
    printf '%s\n' 'Checksum verification failed; nothing was installed.' >&2
    exit 2
fi

unzip -q "$TEMP_DIR/$ARCHIVE" -d "$TEMP_DIR/unpacked"
mkdir -p "$INSTALL_DIR"
install -m 0755 "$TEMP_DIR/unpacked/vibemin" "$INSTALL_DIR/vibemin"
printf 'Installed %s\n' "$INSTALL_DIR/vibemin"
"$INSTALL_DIR/vibemin" --version
