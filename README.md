# MVR / PSP Check for macOS

This branch contains the native macOS port of MVR / PSP Check. The PDF
parsers and highlight coordinate logic are shared with the Windows version;
the desktop shell, packaging, clipboard integration, and updater are adapted
for macOS.

## Supported systems

- macOS 12 Monterey or newer
- Apple Silicon (`arm64`)
- Intel (`x86_64`)
- Python 3.11 or newer for development

The UI is implemented with pywebview and the Cocoa/WebKit backend. There is
no Tk-based UI dependency.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

The app stores WebView local storage under:

```text
~/Library/Application Support/MVR PSP Check
```

## Build

```bash
python -m pip install -r requirements-build-macos.txt
pyinstaller --noconfirm --clean MVR_PSP_Check.macOS.spec
open "dist/MVR PSP Check.app"
```

The spec creates a Retina-ready `.app` bundle, registers PDF documents, and
includes the macOS update helper.

## Releases and updates

The workflow in `.github/workflows/build-macos.yml` builds separate Apple
Silicon and Intel archives. A normal push to `codex/macos` creates workflow
artifacts. Pushing a tag such as `macos-v1.3.0` also publishes a GitHub
release containing:

```text
MVR_PSP_Check-macOS-arm64.zip
MVR_PSP_Check-macOS-arm64.zip.sha256
MVR_PSP_Check-macOS-x86_64.zip
MVR_PSP_Check-macOS-x86_64.zip.sha256
```

The updater scans repository releases for the newest compatible macOS asset,
selects the current CPU architecture, verifies SHA-256 when supplied, checks
the bundle identifier and code signature, replaces the installed app with a
rollback path, and relaunches it. Updating an app in `/Applications` prompts
for administrator approval when required.

For Developer ID signing and Apple notarization, configure these repository
secrets:

```text
MACOS_CERTIFICATE
MACOS_CERTIFICATE_PASSWORD
KEYCHAIN_PASSWORD
APPLE_ID
APPLE_TEAM_ID
APPLE_APP_PASSWORD
```

`MACOS_CERTIFICATE` must contain the base64-encoded Developer ID Application
`.p12` certificate. Without these secrets, CI still produces ad-hoc signed
test builds, but production releases should be signed and notarized.

## Tests

```bash
python -m unittest discover -s tests -v
```
