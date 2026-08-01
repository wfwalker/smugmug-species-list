#!/bin/bash

# Default values
DEFAULT_SOURCE="/Volumes/Batholith/Photos/2024"
DEFAULT_DEST="/Volumes/Photos/2024"
DEFAULT_INTERVAL=10
DEFAULT_METHOD="df" # df is default because it is light on the network mount

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Monitors a running backup (like rsync) and estimates the ETA.

Options:
  -s, --source PATH      Source directory (default: $DEFAULT_SOURCE)
  -d, --dest PATH        Destination directory (default: $DEFAULT_DEST)
  -i, --interval SECS    Refresh interval in seconds (default: $DEFAULT_INTERVAL)
  -m, --method METHOD    Progress tracking method: 'df' or 'du' (default: $DEFAULT_METHOD)
                         'df' measures filesystem-level growth (extremely fast/O(1), ideal for network shares)
                         'du' measures directory-level size (more precise, but slower on slow drives)
  -t, --total SIZE       Override source size calculation (e.g. 2.6T, 2476G, or raw KB)
  -h, --help             Show this help message

EOF
}

# Helper functions
parse_size_to_kb() {
    local val=$1
    val=$(echo "$val" | tr -d ' ')
    if [[ "$val" =~ ^[0-9]+(\.[0-9]+)?[tT]$ ]]; then
        local num
        num=$(echo "$val" | sed -E 's/[tT]//')
        awk -v n="$num" 'BEGIN { printf "%.0f", n * 1024 * 1024 * 1024 }'
    elif [[ "$val" =~ ^[0-9]+(\.[0-9]+)?[gG]$ ]]; then
        local num
        num=$(echo "$val" | sed -E 's/[gG]//')
        awk -v n="$num" 'BEGIN { printf "%.0f", n * 1024 * 1024 }'
    elif [[ "$val" =~ ^[0-9]+(\.[0-9]+)?[mM]$ ]]; then
        local num
        num=$(echo "$val" | sed -E 's/[mM]//')
        awk -v n="$num" 'BEGIN { printf "%.0f", n * 1024 }'
    elif [[ "$val" =~ ^[0-9]+$ ]]; then
        echo "$val"
    else
        echo "0"
    fi
}

format_size() {
    local kb=$1
    awk -v kb="$kb" '
    BEGIN {
        if (kb >= 1073741824) {
            printf "%.2f TB", kb / 1073741824
        } else if (kb >= 1048576) {
            printf "%.2f GB", kb / 1048576
        } else if (kb >= 1024) {
            printf "%.2f MB", kb / 1024
        } else {
            printf "%.2f KB", kb
        }
    }'
}

format_speed() {
    local kbs=$1
    if [[ -z "$kbs" || "$kbs" == "inf" || "$kbs" == "NaN" ]]; then
        echo "Calculating..."
        return
    fi
    awk -v kbs="$kbs" '
    BEGIN {
        if (kbs >= 1048576) {
            printf "%.2f GB/s", kbs / 1048576
        } else if (kbs >= 1024) {
            printf "%.2f MB/s", kbs / 1024
        } else if (kbs > 0) {
            printf "%.2f KB/s", kbs
        } else {
            printf "0.00 KB/s"
        }
    }'
}

format_duration() {
    local seconds=$1
    if [[ -z "$seconds" || "$seconds" == "inf" || "$seconds" == "NaN" || "$seconds" == "Calculating..." ]]; then
        echo "Calculating..."
        return
    fi
    
    # Check if seconds is numeric
    if ! [[ "$seconds" =~ ^[0-9]+$ ]]; then
        echo "Calculating..."
        return
    fi

    local h=$(( seconds / 3600 ))
    local m=$(( (seconds % 3600) / 60 ))
    local s=$(( seconds % 60 ))
    if [ $h -gt 0 ]; then
        printf "%dh %dm %ds" $h $m $s
    elif [ $m -gt 0 ]; then
        printf "%dm %ds" $m $s
    else
        printf "%ds" $s
    fi
}

draw_progress_bar() {
    local pct=$1
    local width=30
    local filled
    filled=$(awk -v pct="$pct" -v w="$width" 'BEGIN { printf "%d", (pct * w) / 100 }')
    # Cap filled
    if [ $filled -gt $width ]; then
        filled=$width
    fi
    local empty=$(( width - filled ))
    
    local bar=""
    for ((i=0; i<filled; i++)); do bar="${bar}█"; done
    for ((i=0; i<empty; i++)); do bar="${bar}░"; done
    
    printf "[%s] %.2f%%" "$bar" "$pct"
}

get_disk_used() {
    local path="$1"
    # Find the nearest existing ancestor path
    while [ ! -d "$path" ] && [ "$path" != "/" ]; do
        path=$(dirname "$path")
    done
    df -k "$path" | tail -n 1 | awk '{print $3}'
}

# Parse command line arguments
SOURCE="$DEFAULT_SOURCE"
DEST="$DEFAULT_DEST"
INTERVAL="$DEFAULT_INTERVAL"
METHOD="$DEFAULT_METHOD"
TOTAL_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--source)
            SOURCE="$2"
            shift 2
            ;;
        -d|--dest)
            DEST="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -m|--method)
            METHOD="$2"
            shift 2
            ;;
        -t|--total)
            TOTAL_OVERRIDE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate method
if [ "$METHOD" != "df" ] && [ "$METHOD" != "du" ]; then
    echo "Error: Method must be 'df' or 'du'."
    exit 1
fi

# Check source exists
if [ ! -d "$SOURCE" ]; then
    echo "Error: Source directory '$SOURCE' does not exist."
    exit 1
fi

# Get source size
if [ -n "$TOTAL_OVERRIDE" ]; then
    SOURCE_SIZE=$(parse_size_to_kb "$TOTAL_OVERRIDE")
    if [ "$SOURCE_SIZE" -eq 0 ]; then
        echo "Error: Invalid total size '$TOTAL_OVERRIDE'."
        exit 1
    fi
    echo "Source size (overridden): $(format_size "$SOURCE_SIZE")"
else
    echo -n "Scanning source folder to get total size... "
    SOURCE_SIZE=$(du -sk "$SOURCE" | cut -f1)
    echo "Done ($(format_size "$SOURCE_SIZE"))"
fi

# Get destination status
echo "Waiting for destination folder to be created by rsync if it doesn't exist..."
# Check if destination parent folder exists
DEST_PARENT=$(dirname "$DEST")
while [ ! -d "$DEST_PARENT" ]; do
    sleep 2
done

# Get initial sizes
INIT_DISK_USED=$(get_disk_used "$DEST")
if [ -d "$DEST" ]; then
    INIT_DIR_SIZE=$(du -sk "$DEST" | cut -f1)
else
    INIT_DIR_SIZE=0
fi

echo "Initial destination size: $(format_size "$INIT_DIR_SIZE")"
echo "Starting ETA calculation loop. Press Ctrl+C to exit."
sleep 1

# Setup trap to restore cursor
trap 'echo -ne "\033[?25h\n"; exit' INT TERM
echo -ne "\033[?25l" # Hide cursor

START_TIME=$(date +%s)
LAST_TIME=$START_TIME
LAST_SIZE=$INIT_DIR_SIZE
EMA_SPEED=0
FIRST_TICK=1
LINES_PRINTED=0

while true; do
    CURR_TIME=$(date +%s)
    ELAPSED=$(( CURR_TIME - START_TIME ))
    TICK_ELAPSED=$(( CURR_TIME - LAST_TIME ))
    
    # Calculate sizes
    if [ "$METHOD" = "df" ]; then
        CURR_DISK_USED=$(get_disk_used "$DEST")
        DISK_DELTA=$(( CURR_DISK_USED - INIT_DISK_USED ))
        CURR_SIZE=$(( INIT_DIR_SIZE + DISK_DELTA ))
        if [ $CURR_SIZE -lt $INIT_DIR_SIZE ]; then
            CURR_SIZE=$INIT_DIR_SIZE
        fi
    else
        if [ -d "$DEST" ]; then
            CURR_SIZE=$(du -sk "$DEST" | cut -f1)
        else
            CURR_SIZE=0
        fi
    fi
    
    TRANSFERRED=$(( CURR_SIZE - INIT_DIR_SIZE ))
    if [ $TRANSFERRED -lt 0 ]; then
        TRANSFERRED=0
    fi
    
    # Remaining size
    REMAINING=$(( SOURCE_SIZE - CURR_SIZE ))
    if [ $REMAINING -lt 0 ]; then
        REMAINING=0
    fi
    
    # Speeds
    INST_SPEED=0
    if [ $TICK_ELAPSED -gt 0 ]; then
        INST_SPEED=$(awk -v curr="$CURR_SIZE" -v last="$LAST_SIZE" -v dt="$TICK_ELAPSED" 'BEGIN { print (curr - last) / dt }')
        if (( $(awk -v s="$INST_SPEED" 'BEGIN { print (s < 0) }') )); then
            INST_SPEED=0
        fi
    fi
    
    if [ $FIRST_TICK -eq 1 ]; then
        if (( $(awk -v s="$INST_SPEED" 'BEGIN { print (s > 0) }') )); then
            EMA_SPEED=$INST_SPEED
            FIRST_TICK=0
        fi
    else
        EMA_SPEED=$(awk -v inst="$INST_SPEED" -v ema="$EMA_SPEED" 'BEGIN { print 0.15 * inst + 0.85 * ema }')
    fi
    
    AVG_SPEED=0
    if [ $ELAPSED -gt 0 ]; then
        AVG_SPEED=$(awk -v trans="$TRANSFERRED" -v elapsed="$ELAPSED" 'BEGIN { print trans / elapsed }')
    fi
    
    # ETAs
    ETA_EMA="Calculating..."
    ETA_AVG="Calculating..."
    
    if (( $(awk -v s="$EMA_SPEED" 'BEGIN { print (s > 0.1) }') )); then
        SEC_EMA=$(awk -v rem="$REMAINING" -v speed="$EMA_SPEED" 'BEGIN { printf "%.0f", rem / speed }')
        ETA_EMA=$(format_duration "$SEC_EMA")
    fi
    if (( $(awk -v s="$AVG_SPEED" 'BEGIN { print (s > 0.1) }') )); then
        SEC_AVG=$(awk -v rem="$REMAINING" -v speed="$AVG_SPEED" 'BEGIN { printf "%.0f", rem / speed }')
        ETA_AVG=$(format_duration "$SEC_AVG")
    fi
    
    # Progress percent
    PCT=$(awk -v curr="$CURR_SIZE" -v tot="$SOURCE_SIZE" 'BEGIN { printf "%.2f", (curr / tot) * 100 }')
    if (( $(awk -v pct="$PCT" 'BEGIN { print (pct > 100) }') )); then
        PCT="100.00"
    fi
    
    # Strings for display
    STR_TRANSFERRED=$(format_size "$CURR_SIZE")
    STR_TOTAL=$(format_size "$SOURCE_SIZE")
    if [ $FIRST_TICK -eq 1 ]; then
        STR_EMA_SPEED="Calculating..."
    else
        STR_EMA_SPEED=$(format_speed "$EMA_SPEED")
    fi
    if [ $ELAPSED -eq 0 ]; then
        STR_AVG_SPEED="Calculating..."
    else
        STR_AVG_SPEED=$(format_speed "$AVG_SPEED")
    fi
    STR_ELAPSED=$(format_duration "$ELAPSED")
    PROGRESS_BAR=$(draw_progress_bar "$PCT")
    
    # Clear previous lines if any were printed
    if [ $LINES_PRINTED -gt 0 ]; then
        echo -ne "\033[${LINES_PRINTED}A"
    fi
    
    # Print Dashboard
    printf "\033[36m------------------------------------------------------------\033[0m\n"
    printf "  \033[1;35mRSYNC BACKUP MONITOR\033[0m\n"
    printf "\033[36m------------------------------------------------------------\033[0m\n"
    printf "  \033[1;30mSource:\033[0m      %s\n" "$SOURCE"
    printf "  \033[1;30mDestination:\033[0m %s\n" "$DEST"
    printf "  \033[1;30mMethod:\033[0m      %s (using filesystem delta)\n" "$METHOD"
    printf "  \033[1;30mProgress:\033[0m    %s\n" "$PROGRESS_BAR"
    printf "  \033[1;30mTransferred:\033[0m %s / %s\n" "$STR_TRANSFERRED" "$STR_TOTAL"
    printf "\033[36m------------------------------------------------------------\033[0m\n"
    printf "  \033[1;30mCurrent Speed:\033[0m %s  (EMA-smoothed)\n" "$STR_EMA_SPEED"
    printf "  \033[1;30mAverage Speed:\033[0m %s  (Overall)\n" "$STR_AVG_SPEED"
    printf "  \033[1;30mTime Elapsed:\033[0m  %s\n" "$STR_ELAPSED"
    printf "\033[36m------------------------------------------------------------\033[0m\n"
    printf "  \033[1;32mETA (Current):\033[0m %s\n" "$ETA_EMA"
    printf "  \033[1;32mETA (Average):\033[0m %s\n" "$ETA_AVG"
    printf "\033[36m------------------------------------------------------------\033[0m\n"
    
    LINES_PRINTED=16
    
    # Save values for next interval
    LAST_TIME=$CURR_TIME
    LAST_SIZE=$CURR_SIZE
    
    sleep "$INTERVAL"
done
