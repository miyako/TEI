#!/bin/bash
set -euo pipefail

image=${1:?Usage: notarize.sh image.dmg}
auth=(--apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password "$NOTARY_PASSWORD")
submit_status=0
xcrun notarytool submit "$image" "${auth[@]}" \
  --wait --timeout 30m --output-format json > notarization.json || submit_status=$?
cat notarization.json
submission_id=$(jq -er '.id | select(type == "string" and length > 0)' notarization.json)
xcrun notarytool log "$submission_id" "${auth[@]}" notarization-log.json
cat notarization-log.json
if [[ "$submit_status" -ne 0 ]]; then
  echo "::error::Notarization submission failed ($submit_status); see notarization-log.json."
  exit "$submit_status"
fi
if [[ "$(jq -r .status notarization.json)" != Accepted ]]; then
  echo "::error::Apple rejected the disk image; see notarization-log.json for exact issues."
  exit 1
fi
xcrun stapler staple "$image"
xcrun stapler validate "$image"
