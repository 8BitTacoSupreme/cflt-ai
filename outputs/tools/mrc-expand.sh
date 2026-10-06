#!/usr/bin/env bash
# mrc-expand.sh — expand topics that are NOT yet stretched across racks into
# a Multi-Region Clusters (MRC) replica layout, using a JSON Lines current-
# state file (produced by kafka-describe-to-json.sh) and a broker-range rack
# config you provide.
#
# Pipeline:
#   kafka-topics --describe --bootstrap-server <BS> --topic <t> > current-state.txt
#   kafka-describe-to-json.sh --describe-file current-state.txt --out state.jsonl
#   mrc-expand.sh --state-file state.jsonl --rack-config racks.conf --out-dir plan/
#
# By default this only computes and writes a plan — no network calls, same
# as reading/writing local files only. Pass --execute N --bootstrap-server
# <BS> to actually apply the plan for up to N topics (kafka-reassign-
# partitions --execute/--verify, then kafka-leader-election --election-type
# preferred) — the rest of the plan is written but left untouched, so you
# control blast radius topic-by-topic across repeated runs.
#
# Dependencies: bash only (3.2+, no associative arrays — runs unmodified on
# macOS's stock /bin/bash). No jq, no Python, no third-party packages. The
# only network calls this script ever makes are the kafka-reassign-
# partitions / kafka-leader-election invocations under --execute, and only
# against the --bootstrap-server you explicitly pass — run --execute only
# from an environment authorized to reach that cluster.

set -eo pipefail
# Deliberately no `-u`: relies on possibly-empty bash arrays throughout,
# which `set -u` treats as unbound on bash <4.4 (macOS ships 3.2).

usage() {
  cat <<EOF
Usage:
  $(basename "$0") --print-example-config
  $(basename "$0") --state-file FILE --rack-config FILE --out-dir DIR [options]

Options:
  --state-file FILE          JSON Lines current-state file (required; see
                              kafka-describe-to-json.sh)
  --rack-config FILE         rack config file, see --print-example-config (required)
  --out-dir DIR              output directory (default: mrc-expand-plan)
  --topics LIST              comma-separated topic allowlist
  --exclude-topics LIST      comma-separated topic denylist
  --prune-excess-replicas    remove replicas in over-provisioned racks (default: leave in place)
  --batch-size N             split the expand-plan into N-partition batches (0 = single file)
  --execute N                actually apply the plan for the first N touched topics
                              (alphabetical order); requires --bootstrap-server.
                              Default 0 = plan only, no network calls.
  --bootstrap-server BS      required with --execute
  --command-config FILE      passed through to kafka-reassign-partitions/kafka-leader-election
  --throttle BYTES           passed through to the expand step's --execute (real data movement)
  --verify-interval-seconds N  poll interval for --verify while executing (default: 5)
  --verify-max-attempts N       give up after this many polls (default: 24, i.e. 2 minutes)
  --print-example-config     print an example --rack-config file and exit
  -h, --help                 show this help
EOF
}

print_example_config() {
  cat <<'CONF'
# Rack config for mrc-expand.sh (and mrc-leader-rebalance.sh) — plain text,
# not JSON, so there's no JSON-parsing dependency on the input side either.
# One directive per line; '#' starts a comment; blank lines are ignored.
#
#   broker <id-or-range> <rack>   — assign broker(s) to a rack. Accepts a
#                                    single id ("3"), a range ("1-2"), or a
#                                    comma list of either ("1-2,5,7-8").
#   target_leader_rack <rack>     — must be one of the racks used below
#   sync <rack> <count>           — desired sync-replica count in this rack
#   observer <rack> <count>       — desired observer-replica count (optional)

broker 1-2 rack-a
broker 3-4 rack-b
broker 5-6 rack-c

target_leader_rack rack-a

sync rack-a 1
sync rack-b 1
sync rack-c 1
CONF
}

# ---------------------------------------------------------------------------
# arg parsing
# ---------------------------------------------------------------------------

STATE_FILE=""
RACK_CONFIG=""
OUT_DIR="mrc-expand-plan"
TOPICS_ALLOW=""
TOPICS_DENY=""
PRUNE_EXCESS=0
BATCH_SIZE=0
EXECUTE_N=0
BOOTSTRAP_SERVER=""
COMMAND_CONFIG=""
THROTTLE=""
VERIFY_INTERVAL=5
VERIFY_MAX_ATTEMPTS=24

while [[ $# -gt 0 ]]; do
  case "$1" in
    --state-file) STATE_FILE="$2"; shift 2 ;;
    --rack-config) RACK_CONFIG="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --topics) TOPICS_ALLOW="$2"; shift 2 ;;
    --exclude-topics) TOPICS_DENY="$2"; shift 2 ;;
    --prune-excess-replicas) PRUNE_EXCESS=1; shift ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    --execute) EXECUTE_N="$2"; shift 2 ;;
    --bootstrap-server) BOOTSTRAP_SERVER="$2"; shift 2 ;;
    --command-config) COMMAND_CONFIG="$2"; shift 2 ;;
    --throttle) THROTTLE="$2"; shift 2 ;;
    --verify-interval-seconds) VERIFY_INTERVAL="$2"; shift 2 ;;
    --verify-max-attempts) VERIFY_MAX_ATTEMPTS="$2"; shift 2 ;;
    --print-example-config) print_example_config; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$STATE_FILE" || -z "$RACK_CONFIG" ]]; then
  echo "ERROR: --state-file and --rack-config are required (or pass --print-example-config)" >&2
  usage
  exit 1
fi

if [[ "$EXECUTE_N" -gt 0 && -z "$BOOTSTRAP_SERVER" ]]; then
  echo "ERROR: --execute requires --bootstrap-server" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# small helpers (no associative arrays — kept 3.2-portable on purpose)
# ---------------------------------------------------------------------------

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

# expand_broker_range "1-2,5,7-8" -> "1 2 5 7 8"
expand_broker_range() {
  local spec="$1"
  local part start end i out=()
  local IFS=','
  local -a parts
  read -ra parts <<< "$spec"
  for part in "${parts[@]}"; do
    if [[ "$part" == *-* ]]; then
      start="${part%-*}"
      end="${part#*-}"
      for ((i = start; i <= end; i++)); do out+=("$i"); done
    else
      out+=("$part")
    fi
  done
  echo "${out[@]}"
}

# ---------------------------------------------------------------------------
# rack config (broker id/range -> rack, target leader rack, sync/observer counts)
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
        local id ids
        ids=$(expand_broker_range "$2")
        for id in $ids; do
          BROKER_IDS+=("$id")
          BROKER_RACKS+=("$3")
        done
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
# parse the JSON Lines state file (kafka-describe-to-json.sh output) — a
# fixed, self-produced format, so a small awk extractor is enough; no JSON
# parsing library needed.
# ---------------------------------------------------------------------------

P_TOPIC=()
P_PART=()
P_LEADER=()
P_REPLICAS=()
P_OBS=()

AWK_JSONL_EXTRACT='
function extract_str(s, key,    idx, rest, endidx) {
  idx = index(s, "\"" key "\": \"");
  if (idx == 0) return "";
  rest = substr(s, idx + length(key) + 5);
  endidx = index(rest, "\"");
  return substr(rest, 1, endidx - 1);
}
function extract_num(s, key,    idx, rest, i, ch, out) {
  idx = index(s, "\"" key "\": ");
  if (idx == 0) return "";
  rest = substr(s, idx + length(key) + 4);
  out = "";
  for (i = 1; i <= length(rest); i++) {
    ch = substr(rest, i, 1);
    if (ch ~ /[0-9-]/) out = out ch; else break;
  }
  return out;
}
function extract_arr(s, key,    idx, rest, endidx) {
  idx = index(s, "\"" key "\": [");
  if (idx == 0) return "";
  rest = substr(s, idx + length(key) + 5);
  endidx = index(rest, "]");
  return substr(rest, 1, endidx - 1);
}
{
  topic = extract_str($0, "topic");
  partition = extract_num($0, "partition");
  leader = extract_num($0, "leader");
  replicas = extract_arr($0, "replicas");
  observers = extract_arr($0, "observers");
  gsub(/ /, "", replicas);
  gsub(/ /, "", observers);
  if (topic != "") print topic "\t" partition "\t" leader "\t" replicas "\t" observers;
}
'

parse_state_file() {
  local file="$1"
  while IFS=$'\t' read -r topic partition leader replicas observers; do
    [[ -z "$topic" ]] && continue
    P_TOPIC+=("$topic")
    P_PART+=("$partition")
    P_LEADER+=("$leader")
    P_REPLICAS+=("$replicas")
    P_OBS+=("$observers")
  done < <(awk "$AWK_JSONL_EXTRACT" "$file" | sort -t $'\t' -k1,1 -k2,2n)

  if [[ ${#P_TOPIC[@]} -eq 0 ]]; then
    echo "ERROR: no partitions parsed from $file — is this really a kafka-describe-to-json.sh output file?" >&2
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
# planning (same algorithm as mrc-leader-rebalance.sh: preserve correct
# placement, add replicas only in under-provisioned racks, prefer the
# existing leader if it's already in the target rack)
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
# JSON output (hand-built, no jq — topic names can't contain characters that
# need escaping in JSON)
# ---------------------------------------------------------------------------

csv_to_json_int_array() {
  local csv="$1"
  if [[ -z "$csv" ]]; then
    echo -n "[]"
  else
    echo -n "[${csv}]"
  fi
}

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
# execution (only reached if --execute N > 0; the only place this script
# ever makes a network call, and only against --bootstrap-server)
# ---------------------------------------------------------------------------

kafka_reassign_execute() {
  local file="$1" throttle="$2"
  local args=(--bootstrap-server "$BOOTSTRAP_SERVER" --reassignment-json-file "$file" --execute)
  [[ -n "$COMMAND_CONFIG" ]] && args+=(--command-config "$COMMAND_CONFIG")
  [[ -n "$throttle" ]] && args+=(--throttle "$throttle")
  kafka-reassign-partitions "${args[@]}"
}

kafka_reassign_verify_until_done() {
  local file="$1" attempt out
  for ((attempt = 1; attempt <= VERIFY_MAX_ATTEMPTS; attempt++)); do
    local vargs=(--bootstrap-server "$BOOTSTRAP_SERVER" --reassignment-json-file "$file" --verify)
    [[ -n "$COMMAND_CONFIG" ]] && vargs+=(--command-config "$COMMAND_CONFIG")
    out=$(kafka-reassign-partitions "${vargs[@]}" 2>&1)
    echo "$out"
    if ! echo "$out" | grep -qi "in progress"; then
      return 0
    fi
    sleep "$VERIFY_INTERVAL"
  done
  echo "ERROR: reassignment for $file did not complete after $VERIFY_MAX_ATTEMPTS verify attempts" >&2
  return 1
}

kafka_leader_election_run() {
  local file="$1"
  local args=(--bootstrap-server "$BOOTSTRAP_SERVER" --election-type preferred --path-to-json-file "$file")
  [[ -n "$COMMAND_CONFIG" ]] && args+=(--command-config "$COMMAND_CONFIG")
  kafka-leader-election "${args[@]}"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

load_rack_config "$RACK_CONFIG"
parse_state_file "$STATE_FILE"
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
      echo "ERROR: $topic-${P_PART[i]}: broker $b has no rack entry in --rack-config — add it before planning" >&2
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

# distinct touched topics, sorted, for the plan summary and for --execute's
# topic-count throttle
TOUCHED_TOPICS=()
for i in "${TOUCHED_IDX[@]}"; do
  list_contains "${PLAN_TOPIC[i]}" "${TOUCHED_TOPICS[@]}" || TOUCHED_TOPICS+=("${PLAN_TOPIC[i]}")
done
if [[ ${#TOUCHED_TOPICS[@]} -gt 0 ]]; then
  IFS=$'\n' TOUCHED_TOPICS=($(sort <<< "${TOUCHED_TOPICS[*]}")); unset IFS
fi

{
  echo "MRC expansion plan"
  echo "target_leader_rack: $TARGET_LEADER_RACK"
  echo "total partitions considered: ${#PLAN_TOPIC[@]}"
  echo "  already satisfied (no-op):      ${#NONE_IDX[@]}"
  echo "  leader-reorder only (no data movement): ${#LEADER_ONLY_IDX[@]}"
  echo "  replica expansion (data movement):      ${#EXPAND_IDX[@]}"
  echo "  replica pruning (data deletion):        ${#PRUNE_IDX[@]}"
  echo "topics touched: ${#TOUCHED_TOPICS[@]} (${TOUCHED_TOPICS[*]})"
  echo ""
  for i in "${TOUCHED_IDX[@]}"; do
    echo "${PLAN_TOPIC[i]}-${PLAN_PART[i]}: ${PLAN_CHANGE_TYPE[i]} leader ${PLAN_OLD_LEADER[i]}->${PLAN_NEW_LEADER[i]} replicas [${PLAN_OLD_REPLICAS[i]}]->[${PLAN_NEW_REPLICAS[i]}] (+[${PLAN_ADDED[i]}] -[${PLAN_REMOVED[i]}])"
  done
} > "$OUT_DIR/plan-summary.txt"

echo "Wrote plan to $OUT_DIR/ (see plan-summary.txt)"
echo "  no-op: ${#NONE_IDX[@]}  leader-only: ${#LEADER_ONLY_IDX[@]}  expand: ${#EXPAND_IDX[@]}  prune: ${#PRUNE_IDX[@]}  topics touched: ${#TOUCHED_TOPICS[@]}"

if [[ "$EXECUTE_N" -le 0 ]]; then
  echo "Plan only (pass --execute N --bootstrap-server <BS> to apply)."
  exit 0
fi

# ---------------------------------------------------------------------------
# --execute N: apply for the first N touched topics only
# ---------------------------------------------------------------------------

EXEC_TOPICS=("${TOUCHED_TOPICS[@]:0:EXECUTE_N}")
PENDING_TOPICS=("${TOUCHED_TOPICS[@]:EXECUTE_N}")

if [[ ${#EXEC_TOPICS[@]} -eq 0 ]]; then
  echo "Nothing to execute (no touched topics)."
  exit 0
fi

echo ""
echo "Executing against $BOOTSTRAP_SERVER for ${#EXEC_TOPICS[@]} topic(s): ${EXEC_TOPICS[*]}"
if [[ ${#PENDING_TOPICS[@]} -gt 0 ]]; then
  echo "Left pending for a future run: ${PENDING_TOPICS[*]}"
fi

EXEC_LEADER_ONLY_IDX=()
EXEC_EXPAND_IDX=()
EXEC_PRUNE_IDX=()
for i in "${LEADER_ONLY_IDX[@]}"; do list_contains "${PLAN_TOPIC[i]}" "${EXEC_TOPICS[@]}" && EXEC_LEADER_ONLY_IDX+=("$i"); done
for i in "${EXPAND_IDX[@]}"; do list_contains "${PLAN_TOPIC[i]}" "${EXEC_TOPICS[@]}" && EXEC_EXPAND_IDX+=("$i"); done
for i in "${PRUNE_IDX[@]}"; do list_contains "${PLAN_TOPIC[i]}" "${EXEC_TOPICS[@]}" && EXEC_PRUNE_IDX+=("$i"); done
EXEC_TOUCHED_IDX=("${EXEC_LEADER_ONLY_IDX[@]}" "${EXEC_EXPAND_IDX[@]}" "${EXEC_PRUNE_IDX[@]}")

mkdir -p "$OUT_DIR/executed-batch"

if [[ ${#EXEC_LEADER_ONLY_IDX[@]} -gt 0 ]]; then
  write_reassignment_json "$OUT_DIR/executed-batch/reassignment-leader-only.json" "${EXEC_LEADER_ONLY_IDX[@]}"
  echo "-- leader-only reassignment --"
  kafka_reassign_execute "$OUT_DIR/executed-batch/reassignment-leader-only.json" ""
  kafka_reassign_verify_until_done "$OUT_DIR/executed-batch/reassignment-leader-only.json"
fi

if [[ ${#EXEC_EXPAND_IDX[@]} -gt 0 ]]; then
  if [[ "$BATCH_SIZE" -gt 0 ]]; then
    total=${#EXEC_EXPAND_IDX[@]}
    start=0
    batch_num=0
    while (( start < total )); do
      batch_num=$((batch_num + 1))
      batch=("${EXEC_EXPAND_IDX[@]:start:BATCH_SIZE}")
      suffix=$(printf '%02d' "$batch_num")
      f="$OUT_DIR/executed-batch/reassignment-expand-$suffix.json"
      write_reassignment_json "$f" "${batch[@]}"
      echo "-- expand batch $suffix --"
      kafka_reassign_execute "$f" "$THROTTLE"
      kafka_reassign_verify_until_done "$f"
      start=$((start + BATCH_SIZE))
    done
  else
    f="$OUT_DIR/executed-batch/reassignment-expand.json"
    write_reassignment_json "$f" "${EXEC_EXPAND_IDX[@]}"
    echo "-- expand --"
    kafka_reassign_execute "$f" "$THROTTLE"
    kafka_reassign_verify_until_done "$f"
  fi
fi

if [[ ${#EXEC_PRUNE_IDX[@]} -gt 0 ]]; then
  f="$OUT_DIR/executed-batch/reassignment-prune.json"
  write_reassignment_json "$f" "${EXEC_PRUNE_IDX[@]}"
  echo "-- prune --"
  kafka_reassign_execute "$f" "$THROTTLE"
  kafka_reassign_verify_until_done "$f"
fi

if [[ ${#EXEC_TOUCHED_IDX[@]} -gt 0 ]]; then
  f="$OUT_DIR/executed-batch/preferred-election.json"
  write_election_json "$f" "${EXEC_TOUCHED_IDX[@]}"
  echo "-- preferred leader election --"
  kafka_leader_election_run "$f"
fi

echo ""
echo "Done. Executed: ${EXEC_TOPICS[*]}"
if [[ ${#PENDING_TOPICS[@]} -gt 0 ]]; then
  echo "Re-run with a higher --execute N (or re-describe + re-plan) for: ${PENDING_TOPICS[*]}"
fi
