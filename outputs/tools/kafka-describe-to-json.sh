#!/usr/bin/env bash
# kafka-describe-to-json.sh — convert `kafka-topics --describe` output into
# JSON Lines (one JSON object per partition: topic, partition, leader,
# replicas, isr, observers). This is the input format mrc-expand.sh reads.
#
# No network calls, no jq, no Python, no third-party packages — bash + awk
# only (both part of any base Unix install). Kafka topic names can only
# contain [a-zA-Z0-9._-], so no JSON string escaping is ever needed here.
#
# Usage:
#   kafka-topics --describe --bootstrap-server <BS> --topic <t> > current-state.txt
#   kafka-describe-to-json.sh --describe-file current-state.txt [--out state.jsonl]
#
# Without --out, prints to stdout.

set -eo pipefail

usage() {
  cat <<EOF
Usage: $(basename "$0") --describe-file FILE [--out FILE]

Converts kafka-topics --describe output into JSON Lines (one JSON object
per partition). Prints to stdout by default, or writes to --out FILE.
EOF
}

DESCRIBE_FILE=""
OUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --describe-file) DESCRIBE_FILE="$2"; shift 2 ;;
    --out) OUT_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$DESCRIBE_FILE" ]]; then
  echo "ERROR: --describe-file is required" >&2
  usage
  exit 1
fi

if [[ ! -f "$DESCRIBE_FILE" ]]; then
  echo "ERROR: no such file: $DESCRIBE_FILE" >&2
  exit 1
fi

# Parse `kafka-topics --describe` lines, then hand-build one JSON object per
# partition. csv-to-json-array is just wrapping already-numeric CSV in
# brackets — no escaping needed since replica/isr/observer lists are broker
# IDs (integers).
AWK_PROG='
  /Partition:/ && /Topic:/ {
    topic=""; partition=""; leader=""; replicas=""; isr=""; observers="";
    n = split($0, parts, /[ \t]+/);
    for (i = 1; i <= n; i++) {
      if (parts[i] == "Topic:") topic = parts[i+1];
      else if (parts[i] == "Partition:") partition = parts[i+1];
      else if (parts[i] == "Leader:") leader = parts[i+1];
      else if (parts[i] == "Replicas:") replicas = parts[i+1];
      else if (parts[i] == "Isr:") isr = parts[i+1];
      else if (parts[i] == "Observers:") observers = parts[i+1];
    }
    if (topic != "" && partition != "") {
      if (leader == "") leader = "-1";
      print topic "\t" partition "\t" leader "\t" replicas "\t" isr "\t" observers;
    }
  }
'

csv_to_json_int_array() {
  local csv="$1"
  if [[ -z "$csv" ]]; then
    echo -n "[]"
  else
    echo -n "[${csv}]"
  fi
}

TMP_TSV=$(mktemp)
trap 'rm -f "$TMP_TSV"' EXIT

awk "$AWK_PROG" "$DESCRIBE_FILE" | sort -t $'\t' -k1,1 -k2,2n > "$TMP_TSV"

if [[ ! -s "$TMP_TSV" ]]; then
  echo "ERROR: no partitions parsed from $DESCRIBE_FILE — is this really \`kafka-topics --describe\` output?" >&2
  exit 1
fi

RECORDS=()
while IFS=$'\t' read -r topic partition leader replicas isr observers; do
  [[ -z "$topic" ]] && continue
  replicas_json=$(csv_to_json_int_array "$replicas")
  isr_json=$(csv_to_json_int_array "$isr")
  observers_json=$(csv_to_json_int_array "$observers")
  RECORDS+=("$(printf '{"topic": "%s", "partition": %s, "leader": %s, "replicas": %s, "isr": %s, "observers": %s}' \
    "$topic" "$partition" "$leader" "$replicas_json" "$isr_json" "$observers_json")")
done < "$TMP_TSV"

if [[ -n "$OUT_FILE" ]]; then
  printf '%s\n' "${RECORDS[@]}" > "$OUT_FILE"
  echo "Wrote ${#RECORDS[@]} partition record(s) to $OUT_FILE" >&2
else
  printf '%s\n' "${RECORDS[@]}"
fi
