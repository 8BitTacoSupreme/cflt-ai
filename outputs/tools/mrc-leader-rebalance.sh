#!/usr/bin/env bash
# mrc-leader-rebalance.sh — compute a preferred-leader-rack + replica-expansion
# plan for an existing Kafka cluster converting to (or already on) Multi-Region
# Clusters (MRC), where all partition leaders should land on brokers in one
# specific rack.
#
# Why this exists: neither Self-Balancing Clusters nor the legacy Auto Data
# Balancer optimize for "put every leader in rack X" — that isn't a goal
# either rebalancer knows about, only even load/replica distribution. Pinning
# leaders to a rack is a preferred-replica-ordering problem, solved with
# `kafka-reassign-partitions` (to set replicas[0]) + `kafka-leader-election
# --election-type preferred` (to act on it) — not with either rebalancer.
#
# This script makes NO network calls. It only reads local files and writes
# local files. Two inputs, both gathered by you, from your own environment,
# against whichever cluster you're authorized to reach:
#
#   1. Output of:
#        kafka-topics --describe --bootstrap-server <BS> --exclude-internal-topics \
#          [--command-config <client.properties>] > current-state.txt
#
#   2. A rack config file (see --print-example-config) mapping broker IDs to
#      racks, naming the target leader rack, and the desired sync/observer
#      replica count per rack.
#
# It emits reassignment JSON (kafka-reassign-partitions --execute input),
# a preferred-leader-election JSON (kafka-leader-election input), and a plain
# text plan summary — for YOU to run against the target cluster from an
# environment you've verified is authorized to reach it. Do not point the
# *inputs* to this script at a client's live cluster from an environment/agent
# session that isn't authorized to touch that cluster.
#
# Dependencies: bash only (3.2+ — deliberately avoids associative arrays, so
# it runs unmodified on macOS's stock /bin/bash as well as Linux bash 4/5).
# No jq, no Python, no third-party packages of any kind — the rack config
# uses a small line-oriented format (not JSON) so no JSON parser is needed on
# the input side, and the JSON this script writes (reassignment/election
# files) is simple enough — plain strings and integers, no nesting beyond one
# array — to hand-build with printf, since Kafka topic names can't contain
# characters that would need escaping in JSON.
#
# Usage:
#   mrc-leader-rebalance.sh --print-example-config
#   mrc-leader-rebalance.sh --describe-file current-state.txt \
#       --rack-config racks.conf --out-dir plan/

set -eo pipefail
# Deliberately no `-u`: this script leans on possibly-empty bash arrays
# throughout (e.g. `"${REPLY_ARR[@]}"` when REPLY_ARR=()), which `set -u`
# treats as an unbound-variable error on bash <4.4 (macOS's stock /bin/bash
# is 3.2) even though the array is intentionally, validly empty.

SCRIPT_NAME=$(basename "$0")

usage() {
  sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
  cat <<EOF

Options:
  --describe-file FILE       kafka-topics --describe output (required)
  --rack-config FILE         rack config file, see --print-example-config (required)
  --out-dir DIR              output directory (default: mrc-leader-rebalance-plan)
  --topics LIST              comma-separated topic allowlist
  --exclude-topics LIST      comma-separated topic denylist
  --prune-excess-replicas    remove replicas in over-provisioned racks (default: leave in place)
  --batch-size N             split the expand-plan into N-partition batches (0 = single file)
  --print-example-config     print an example --rack-config file and exit
  -h, --help                 show this help
EOF
}

print_example_config() {
  cat <<'CONF'
# Rack config for mrc-leader-rebalance.sh — plain text, not JSON, so this
# script has zero non-bash dependencies. One directive per line; '#'
# starts a comment; blank lines are ignored.
#
#   broker <broker-id> <rack>       — every broker in the cluster, once each
#   target_leader_rack <rack>       — must be one of the racks used below
#   sync <rack> <count>             — desired sync-replica count in this rack
#   observer <rack> <count>         — desired observer-replica count (optional)

broker 1 rack-a
broker 2 rack-a
broker 3 rack-b
broker 4 rack-b
broker 5 rack-c
broker 6 rack-c

target_leader_rack rack-a

sync rack-a 1
sync rack-b 1
sync rack-c 1
CONF
}

# ---------------------------------------------------------------------------
# arg parsing
# ---------------------------------------------------------------------------

DESCRIBE_FILE=""
RACK_CONFIG=""
OUT_DIR="mrc-leader-rebalance-plan"
TOPICS_ALLOW=""
TOPICS_DENY=""
PRUNE_EXCESS=0
BATCH_SIZE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --describe-file) DESCRIBE_FILE="$2"; shift 2 ;;
    --rack-config) RACK_CONFIG="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --topics) TOPICS_ALLOW="$2"; shift 2 ;;
    --exclude-topics) TOPICS_DENY="$2"; shift 2 ;;
    --prune-excess-replicas) PRUNE_EXCESS=1; shift ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    --print-example-config) print_example_config; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$DESCRIBE_FILE" || -z "$RACK_CONFIG" ]]; then
  echo "ERROR: --describe-file and --rack-config are required (or pass --print-example-config)" >&2
  usage
  exit 1
fi

# ---------------------------------------------------------------------------
# small helpers (no associative arrays — kept 3.2-portable on purpose)
# ---------------------------------------------------------------------------

# list_contains "id" "${list[@]}"
list_contains() {
  local needle="$1"; shift
  local x
  for x in "$@"; do
    [[ "$x" == "$needle" ]] && return 0
  done
  return 1
}

csv_to_array() {
  # sets REPLY_ARR
  local csv="$1"
  REPLY_ARR=()
  if [[ -n "$csv" ]]; then
    local IFS=','
    read -ra REPLY_ARR <<< "$csv"
  fi
}

# ---------------------------------------------------------------------------
# rack config
# ---------------------------------------------------------------------------

BROKER_IDS=()
BROKER_RACKS=()
SYNC_RACK_NAMES=()
SYNC_RACK_COUNTS=()
OBS_RACK_NAMES=()
OBS_RACK_COUNTS=()
TARGET_LEADER_RACK=""

load_rack_config() {
  local file="$1"
  local line stripped directive

  while IFS= read -r line || [[ -n "$line" ]]; do
    stripped="${line%%#*}"
    # trim leading/trailing whitespace without sed/awk
    stripped="${stripped#"${stripped%%[![:space:]]*}"}"
    stripped="${stripped%"${stripped##*[![:space:]]}"}"
    [[ -z "$stripped" ]] && continue

    set -f
    set -- $stripped
    set +f
    directive="$1"
    case "$directive" in
      broker)
        [[ $# -eq 3 ]] || { echo "ERROR: malformed 'broker' line in $file: $line" >&2; exit 1; }
        BROKER_IDS+=("$2")
        BROKER_RACKS+=("$3")
        ;;
      target_leader_rack)
        [[ $# -eq 2 ]] || { echo "ERROR: malformed 'target_leader_rack' line in $file: $line" >&2; exit 1; }
        TARGET_LEADER_RACK="$2"
        ;;
      sync)
        [[ $# -eq 3 ]] || { echo "ERROR: malformed 'sync' line in $file: $line" >&2; exit 1; }
        SYNC_RACK_NAMES+=("$2")
        SYNC_RACK_COUNTS+=("$3")
        ;;
      observer)
        [[ $# -eq 3 ]] || { echo "ERROR: malformed 'observer' line in $file: $line" >&2; exit 1; }
        OBS_RACK_NAMES+=("$2")
        OBS_RACK_COUNTS+=("$3")
        ;;
      *)
        echo "ERROR: unrecognized rack-config directive '$directive' in $file: $line" >&2
        exit 1
        ;;
    esac
  done < "$file"

  if [[ -z "$TARGET_LEADER_RACK" ]]; then
    echo "ERROR: $file has no 'target_leader_rack' directive" >&2
    exit 1
  fi

  local found=0 i
  for ((i = 0; i < ${#SYNC_RACK_NAMES[@]}; i++)); do
    [[ "${SYNC_RACK_NAMES[i]}" == "$TARGET_LEADER_RACK" ]] && found=1
  done
  if [[ "$found" -eq 0 ]]; then
    echo "ERROR: target_leader_rack '$TARGET_LEADER_RACK' is not one of sync_racks" >&2
    exit 1
  fi

  for ((i = 0; i < ${#SYNC_RACK_NAMES[@]}; i++)); do
    local rack="${SYNC_RACK_NAMES[i]}" count="${SYNC_RACK_COUNTS[i]}" pool_size=0 j
    for ((j = 0; j < ${#BROKER_IDS[@]}; j++)); do
      [[ "${BROKER_RACKS[j]}" == "$rack" ]] && pool_size=$((pool_size + 1))
    done
    if (( pool_size < count )); then
      echo "ERROR: sync_racks wants $count replica(s) in rack '$rack' but broker_rack only lists $pool_size broker(s) there" >&2
      exit 1
    fi
  done
}

broker_rack_of() {
  local id="$1" i
  for ((i = 0; i < ${#BROKER_IDS[@]}; i++)); do
    if [[ "${BROKER_IDS[i]}" == "$id" ]]; then
      echo "${BROKER_RACKS[i]}"
      return 0
    fi
  done
  return 1
}

# rack_pool RACK used1 used2 ... -> prints matching broker ids, sorted numerically
rack_pool() {
  local rack="$1"; shift
  local used=("$@")
  local i
  for ((i = 0; i < ${#BROKER_IDS[@]}; i++)); do
    if [[ "${BROKER_RACKS[i]}" == "$rack" ]] && ! list_contains "${BROKER_IDS[i]}" "${used[@]}"; then
      echo "${BROKER_IDS[i]}"
    fi
  done | sort -n
}

# ---------------------------------------------------------------------------
# load tracking (parallel arrays instead of an associative array)
# ---------------------------------------------------------------------------

LOAD_IDS=()
LOAD_COUNTS=()

load_get() {
  local id="$1" i
  for ((i = 0; i < ${#LOAD_IDS[@]}; i++)); do
    if [[ "${LOAD_IDS[i]}" == "$id" ]]; then
      echo "${LOAD_COUNTS[i]}"
      return
    fi
  done
  echo 0
}

load_inc() {
  local id="$1" i
  for ((i = 0; i < ${#LOAD_IDS[@]}; i++)); do
    if [[ "${LOAD_IDS[i]}" == "$id" ]]; then
      LOAD_COUNTS[i]=$((LOAD_COUNTS[i] + 1))
      return
    fi
  done
  LOAD_IDS+=("$id")
  LOAD_COUNTS+=(1)
}

# pick_least_loaded pool_id1 pool_id2 ... -> prints the least-loaded id (ties -> lowest id, pool must be pre-sorted ascending)
pick_least_loaded() {
  local best="" best_load=999999999 id ld
  for id in "$@"; do
    ld=$(load_get "$id")
    if (( ld < best_load )); then
      best_load=$ld
      best=$id
    fi
  done
  echo "$best"
}

# ---------------------------------------------------------------------------
# parse `kafka-topics --describe` output
# ---------------------------------------------------------------------------

P_TOPIC=()
P_PART=()
P_LEADER=()
P_REPLICAS=()
P_ISR=()
P_OBS=()

parse_describe() {
  local file="$1"
  local awk_prog='
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
        print topic "\t" partition "\t" leader "\t" replicas "\t" isr "\t" observers;
      }
    }
  '
  while IFS=$'\t' read -r topic partition leader replicas isr observers; do
    [[ -z "$topic" ]] && continue
    P_TOPIC+=("$topic")
    P_PART+=("$partition")
    P_LEADER+=("$leader")
    P_REPLICAS+=("$replicas")
    P_ISR+=("$isr")
    P_OBS+=("$observers")
  done < <(awk "$awk_prog" "$file" | sort -t $'\t' -k1,1 -k2,2n)

  if [[ ${#P_TOPIC[@]} -eq 0 ]]; then
    echo "ERROR: no partitions parsed from $file — is this really \`kafka-topics --describe\` output?" >&2
    exit 1
  fi
}

seed_load() {
  local i replicas r
  for ((i = 0; i < ${#P_TOPIC[@]}; i++)); do
    csv_to_array "${P_REPLICAS[i]}"
    for r in "${REPLY_ARR[@]}"; do
      load_inc "$r"
    done
  done
}

# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------

PLAN_TOPIC=()
PLAN_PART=()
PLAN_CHANGE_TYPE=()
PLAN_OLD_LEADER=()
PLAN_NEW_LEADER=()
PLAN_OLD_REPLICAS=()
PLAN_NEW_REPLICAS=()
PLAN_ADDED=()
PLAN_REMOVED=()

join_csv() {
  local IFS=','
  echo "$*"
}

# plan_partition i (i indexes P_* arrays); appends to PLAN_* arrays
plan_partition() {
  local idx="$1"
  local topic="${P_TOPIC[idx]}" partition="${P_PART[idx]}" old_leader="${P_LEADER[idx]}"
  csv_to_array "${P_REPLICAS[idx]}"; local old_replicas=("${REPLY_ARR[@]}")
  csv_to_array "${P_OBS[idx]}"; local old_observers=("${REPLY_ARR[@]}")

  local used=()
  local new_sync=()
  local removed=()
  local i b

  for ((i = 0; i < ${#SYNC_RACK_NAMES[@]}; i++)); do
    local rack="${SYNC_RACK_NAMES[i]}" count="${SYNC_RACK_COUNTS[i]}"
    local existing_here=()
    for b in "${old_replicas[@]}"; do
      if [[ "$(broker_rack_of "$b")" == "$rack" ]] && ! list_contains "$b" "${used[@]}"; then
        existing_here+=("$b")
      fi
    done

    local keep=() extra=()
    local j
    for ((j = 0; j < ${#existing_here[@]}; j++)); do
      if (( j < count )); then keep+=("${existing_here[j]}"); else extra+=("${existing_here[j]}"); fi
    done

    for b in "${keep[@]}"; do used+=("$b"); new_sync+=("$b"); done

    if [[ ${#extra[@]} -gt 0 ]]; then
      if [[ "$PRUNE_EXCESS" -eq 1 ]]; then
        for b in "${extra[@]}"; do removed+=("$b"); done
      else
        for b in "${extra[@]}"; do used+=("$b"); new_sync+=("$b"); done
      fi
    fi

    local shortfall=$((count - ${#keep[@]}))
    while (( shortfall > 0 )); do
      local pool
      pool=$(rack_pool "$rack" "${used[@]}")
      local pick=""
      if [[ -n "$pool" ]]; then
        pick=$(pick_least_loaded $pool)
      fi
      if [[ -z "$pick" ]]; then
        echo "ERROR: $topic-$partition: no available broker left in rack '$rack' to satisfy sync_racks count=$count" >&2
        exit 1
      fi
      used+=("$pick")
      new_sync+=("$pick")
      load_inc "$pick"
      shortfall=$((shortfall - 1))
    done
  done

  local new_observers=()
  for ((i = 0; i < ${#OBS_RACK_NAMES[@]}; i++)); do
    local rack="${OBS_RACK_NAMES[i]}" count="${OBS_RACK_COUNTS[i]}"
    local existing_here=()
    for b in "${old_replicas[@]}"; do
      if [[ "$(broker_rack_of "$b")" == "$rack" ]] && ! list_contains "$b" "${used[@]}" && list_contains "$b" "${old_observers[@]}"; then
        existing_here+=("$b")
      fi
    done

    local keep=()
    local j
    for ((j = 0; j < ${#existing_here[@]}; j++)); do
      if (( j < count )); then keep+=("${existing_here[j]}"); fi
    done
    for b in "${keep[@]}"; do used+=("$b"); new_observers+=("$b"); done

    local shortfall=$((count - ${#keep[@]}))
    while (( shortfall > 0 )); do
      local pool
      pool=$(rack_pool "$rack" "${used[@]}")
      local pick=""
      if [[ -n "$pool" ]]; then
        pick=$(pick_least_loaded $pool)
      fi
      if [[ -z "$pick" ]]; then
        echo "ERROR: $topic-$partition: no available broker left in rack '$rack' to satisfy observer_racks count=$count" >&2
        exit 1
      fi
      used+=("$pick")
      new_observers+=("$pick")
      load_inc "$pick"
      shortfall=$((shortfall - 1))
    done
  done

  local new_leader=""
  if list_contains "$old_leader" "${new_sync[@]}" && [[ "$(broker_rack_of "$old_leader")" == "$TARGET_LEADER_RACK" ]]; then
    new_leader="$old_leader"
  else
    local target_members=()
    for b in "${new_sync[@]}"; do
      [[ "$(broker_rack_of "$b")" == "$TARGET_LEADER_RACK" ]] && target_members+=("$b")
    done
    if [[ ${#target_members[@]} -eq 0 ]]; then
      echo "ERROR: $topic-$partition: internal error — no replica landed in target_leader_rack '$TARGET_LEADER_RACK'" >&2
      exit 1
    fi
    new_leader=$(printf '%s\n' "${target_members[@]}" | sort -n | head -1)
  fi

  local ordered_sync=("$new_leader")
  for b in "${new_sync[@]}"; do
    [[ "$b" != "$new_leader" ]] && ordered_sync+=("$b")
  done
  local new_replicas=("${ordered_sync[@]}" "${new_observers[@]}")

  local added=()
  for b in "${new_replicas[@]}"; do
    list_contains "$b" "${old_replicas[@]}" || added+=("$b")
  done

  local old_set_str new_set_str
  old_set_str=$(printf '%s\n' "${old_replicas[@]}" | sort -n | tr '\n' ' ')
  new_set_str=$(printf '%s\n' "${new_replicas[@]}" | sort -n | tr '\n' ' ')
  local membership_changed=1
  [[ "$old_set_str" == "$new_set_str" ]] && membership_changed=0

  local change_type
  if [[ "$membership_changed" -eq 0 ]]; then
    local old_order_str new_order_str
    old_order_str=$(join_csv "${old_replicas[@]}")
    new_order_str=$(join_csv "${new_replicas[@]}")
    if [[ "$old_order_str" == "$new_order_str" ]]; then
      change_type="none"
    else
      change_type="leader-reorder-only"
    fi
  elif [[ ${#removed[@]} -gt 0 && ${#added[@]} -eq 0 ]]; then
    change_type="prune"
  else
    change_type="expand"
  fi

  PLAN_TOPIC+=("$topic")
  PLAN_PART+=("$partition")
  PLAN_CHANGE_TYPE+=("$change_type")
  PLAN_OLD_LEADER+=("$old_leader")
  PLAN_NEW_LEADER+=("$new_leader")
  PLAN_OLD_REPLICAS+=("$(join_csv "${old_replicas[@]}")")
  PLAN_NEW_REPLICAS+=("$(join_csv "${new_replicas[@]}")")
  PLAN_ADDED+=("$(join_csv "${added[@]}")")
  PLAN_REMOVED+=("$(join_csv "${removed[@]}")")
}

# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

# csv_to_json_int_array "1,2,3" -> [1,2,3]  (already-numeric CSV, no escaping needed)
csv_to_json_int_array() {
  local csv="$1"
  if [[ -z "$csv" ]]; then
    echo -n "[]"
  else
    echo -n "[${csv}]"
  fi
}

# csv_to_json_logdirs "1,2,3" -> ["any","any","any"], one "any" per element
csv_to_json_logdirs() {
  local csv="$1"
  if [[ -z "$csv" ]]; then
    echo -n "[]"
    return
  fi
  csv_to_array "$csv"
  local out="[" i
  for ((i = 0; i < ${#REPLY_ARR[@]}; i++)); do
    [[ $i -gt 0 ]] && out+=","
    out+='"any"'
  done
  out+="]"
  echo -n "$out"
}

# write_reassignment_json OUTFILE idx1 idx2 ...
# Hand-built JSON: topic names are validated by Kafka to only contain
# [a-zA-Z0-9._-], so no string escaping is ever needed here.
write_reassignment_json() {
  local outfile="$1"; shift
  local idx first=1 replicas_json log_dirs_json
  {
    echo '{'
    echo '  "version": 1,'
    echo '  "partitions": ['
    for idx in "$@"; do
      [[ "$first" -eq 1 ]] || echo ','
      first=0
      replicas_json=$(csv_to_json_int_array "${PLAN_NEW_REPLICAS[idx]}")
      log_dirs_json=$(csv_to_json_logdirs "${PLAN_NEW_REPLICAS[idx]}")
      printf '    {"topic": "%s", "partition": %s, "replicas": %s, "log_dirs": %s}' \
        "${PLAN_TOPIC[idx]}" "${PLAN_PART[idx]}" "$replicas_json" "$log_dirs_json"
    done
    echo ''
    echo '  ]'
    echo '}'
  } > "$outfile"
}

# write_election_json OUTFILE idx1 idx2 ...
write_election_json() {
  local outfile="$1"; shift
  local idx first=1
  {
    echo '{'
    echo '  "version": 1,'
    echo '  "partitions": ['
    for idx in "$@"; do
      [[ "$first" -eq 1 ]] || echo ','
      first=0
      printf '    {"topic": "%s", "partition": %s}' "${PLAN_TOPIC[idx]}" "${PLAN_PART[idx]}"
    done
    echo ''
    echo '  ]'
    echo '}'
  } > "$outfile"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

load_rack_config "$RACK_CONFIG"
parse_describe "$DESCRIBE_FILE"
seed_load

TOPICS_ALLOW_ARR=()
TOPICS_DENY_ARR=()
[[ -n "$TOPICS_ALLOW" ]] && csv_to_array "$TOPICS_ALLOW" && TOPICS_ALLOW_ARR=("${REPLY_ARR[@]}")
[[ -n "$TOPICS_DENY" ]] && csv_to_array "$TOPICS_DENY" && TOPICS_DENY_ARR=("${REPLY_ARR[@]}")

for ((i = 0; i < ${#P_TOPIC[@]}; i++)); do
  topic="${P_TOPIC[i]}"

  if [[ ${#TOPICS_ALLOW_ARR[@]} -gt 0 ]] && ! list_contains "$topic" "${TOPICS_ALLOW_ARR[@]}"; then
    continue
  fi
  if [[ ${#TOPICS_DENY_ARR[@]} -gt 0 ]] && list_contains "$topic" "${TOPICS_DENY_ARR[@]}"; then
    continue
  fi

  csv_to_array "${P_REPLICAS[i]}"
  for b in "${REPLY_ARR[@]}"; do
    if ! broker_rack_of "$b" >/dev/null; then
      echo "ERROR: $topic-${P_PART[i]}: broker $b has no rack entry in --rack-config broker_rack — add it before planning (a stale/decommissioned broker ID left in a replica set will otherwise silently break the plan)" >&2
      exit 1
    fi
  done

  plan_partition "$i"
done

mkdir -p "$OUT_DIR"

LEADER_ONLY_IDX=()
EXPAND_IDX=()
PRUNE_IDX=()
NONE_IDX=()
for ((i = 0; i < ${#PLAN_TOPIC[@]}; i++)); do
  case "${PLAN_CHANGE_TYPE[i]}" in
    leader-reorder-only) LEADER_ONLY_IDX+=("$i") ;;
    expand) EXPAND_IDX+=("$i") ;;
    prune) PRUNE_IDX+=("$i") ;;
    none) NONE_IDX+=("$i") ;;
  esac
done

if [[ ${#LEADER_ONLY_IDX[@]} -gt 0 ]]; then
  write_reassignment_json "$OUT_DIR/reassignment-leader-only.json" "${LEADER_ONLY_IDX[@]}"
fi

EXPAND_BATCH_COUNT=0
if [[ ${#EXPAND_IDX[@]} -gt 0 ]]; then
  if [[ "$BATCH_SIZE" -gt 0 ]]; then
    total=${#EXPAND_IDX[@]}
    start=0
    batch_num=0
    while (( start < total )); do
      batch_num=$((batch_num + 1))
      batch=("${EXPAND_IDX[@]:start:BATCH_SIZE}")
      suffix=$(printf '%02d' "$batch_num")
      write_reassignment_json "$OUT_DIR/reassignment-expand-$suffix.json" "${batch[@]}"
      start=$((start + BATCH_SIZE))
    done
    EXPAND_BATCH_COUNT=$batch_num
  else
    write_reassignment_json "$OUT_DIR/reassignment-expand.json" "${EXPAND_IDX[@]}"
    EXPAND_BATCH_COUNT=1
  fi
fi

if [[ ${#PRUNE_IDX[@]} -gt 0 ]]; then
  write_reassignment_json "$OUT_DIR/reassignment-prune.json" "${PRUNE_IDX[@]}"
fi

TOUCHED_IDX=("${LEADER_ONLY_IDX[@]}" "${EXPAND_IDX[@]}" "${PRUNE_IDX[@]}")
if [[ ${#TOUCHED_IDX[@]} -gt 0 ]]; then
  write_election_json "$OUT_DIR/preferred-election.json" "${TOUCHED_IDX[@]}"
fi

{
  echo "MRC leader-rack rebalance plan"
  echo "target_leader_rack: $TARGET_LEADER_RACK"
  echo "total partitions considered: ${#PLAN_TOPIC[@]}"
  echo "  already satisfied (no-op):      ${#NONE_IDX[@]}"
  echo "  leader-reorder only (no data movement): ${#LEADER_ONLY_IDX[@]}"
  echo "  replica expansion (data movement):      ${#EXPAND_IDX[@]}"
  echo "  replica pruning (data deletion):        ${#PRUNE_IDX[@]}"
  echo ""
  for i in "${TOUCHED_IDX[@]}"; do
    echo "${PLAN_TOPIC[i]}-${PLAN_PART[i]}: ${PLAN_CHANGE_TYPE[i]} leader ${PLAN_OLD_LEADER[i]}->${PLAN_NEW_LEADER[i]} replicas [${PLAN_OLD_REPLICAS[i]}]->[${PLAN_NEW_REPLICAS[i]}] (+[${PLAN_ADDED[i]}] -[${PLAN_REMOVED[i]}])"
  done
  echo ""
  echo "Run order, from an environment authorized to reach this cluster (never from here):"
  if [[ ${#LEADER_ONLY_IDX[@]} -gt 0 ]]; then
    cat <<EOF
  1. kafka-reassign-partitions --bootstrap-server <BS> --reassignment-json-file reassignment-leader-only.json --execute
     (metadata-only — same broker set, reordered; no data copy, safe to run at full speed)
EOF
  fi
  if [[ ${#EXPAND_IDX[@]} -gt 0 ]]; then
    cat <<EOF
  2. For each of the $EXPAND_BATCH_COUNT reassignment-expand*.json batch(es):
       kafka-reassign-partitions --bootstrap-server <BS> --reassignment-json-file reassignment-expand-NN.json --throttle <bytes/sec> --execute
     Then poll with --verify before moving to the next batch. This moves real data — throttle it.
EOF
  fi
  if [[ ${#PRUNE_IDX[@]} -gt 0 ]]; then
    cat <<EOF
  3. kafka-reassign-partitions --bootstrap-server <BS> --reassignment-json-file reassignment-prune.json --throttle <bytes/sec> --execute
     (deletes replica copies in over-provisioned racks — you passed --prune-excess-replicas, double-check this file before running it)
EOF
  fi
  if [[ ${#TOUCHED_IDX[@]} -gt 0 ]]; then
    cat <<EOF
  4. Once all reassignments above report COMPLETED (--verify), and new replicas have caught up to the ISR:
       kafka-leader-election --bootstrap-server <BS> --election-type preferred --path-to-json-file preferred-election.json
EOF
  fi
} > "$OUT_DIR/plan-summary.txt"

echo "Wrote plan to $OUT_DIR/ (see plan-summary.txt)"
echo "  no-op: ${#NONE_IDX[@]}  leader-only: ${#LEADER_ONLY_IDX[@]}  expand: ${#EXPAND_IDX[@]}  prune: ${#PRUNE_IDX[@]}"
