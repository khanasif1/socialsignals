#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-adhoc}"
[[ "$PROFILE" == adhoc || "$PROFILE" == production ]] || { echo "Use adhoc or production (TestFlight)." >&2; exit 1; }
: "${EXPO_PUBLIC_API_URL:?Set your HTTPS backend URL}"
: "${EXPO_PUBLIC_IOS_BUNDLE_ID:?Set your registered Apple bundle identifier}"
: "${EXPO_PUBLIC_EAS_PROJECT_ID:?Run eas init first and set the project UUID}"
[[ "$EXPO_PUBLIC_API_URL" == https://* ]] || { echo "HTTPS API required." >&2; exit 1; }
[[ "$EXPO_PUBLIC_IOS_BUNDLE_ID" != com.yourcompany.signal ]] || { echo "Use your own bundle identifier." >&2; exit 1; }
mkdir -p "$ROOT/output"
cd "$ROOT/frontend"
npm run typecheck
npx expo install --check
# EAS handles Apple credentials interactively on first use; never store them in this repo.
npm exec --yes --package=eas-cli@25.3.0 -- eas build --platform ios --profile "$PROFILE" --wait --json > "$ROOT/output/ios-build.json"
URL="$(python - "$ROOT/output/ios-build.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
build = data[0] if isinstance(data, list) else data
assert build["status"] == "FINISHED", "EAS build did not finish"
url = build["artifacts"]["buildUrl"]
assert url.startswith("https://"), "Invalid artifact URL"
print(url)
PY
)"
curl --fail --location --retry 3 "$URL" --output "$ROOT/output/SIGNAL.ipa"
python - "$ROOT/output/SIGNAL.ipa" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    assert any(p.startswith("Payload/") and p.endswith("/Info.plist") for p in archive.namelist()), "Not an IPA"
PY
echo "IPA saved to output/SIGNAL.ipa"
if [[ -n "${GOOGLE_DRIVE_FOLDER_ID:-}" && -n "${GOOGLE_DRIVE_ACCESS_TOKEN:-}" ]]; then
  bash "$ROOT/scripts/upload-google-drive.sh" "$ROOT/output/SIGNAL.ipa"
else
  echo "Upload output/SIGNAL.ipa manually to your private Google Drive folder."
fi
echo "Ad hoc: only registered devices can install. Use the EAS install link, Apple Configurator, or supported MDM."
echo "Google Drive stores the file; it does not bypass signing or install arbitrary IPAs."
