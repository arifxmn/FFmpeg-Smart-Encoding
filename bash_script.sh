#!/bin/bash
input="input_video.mp4"
output="output_video.mp4"
overlay_intervals=(
    "00:10:00 00:10:10"  # Overlay 1: 10s at 10-minute mark
    "00:30:00 00:30:10"  # Overlay 2: 10s at 30-minute mark
    # Add more intervals as needed
)

# Convert HH:MM:SS to seconds
to_seconds() {
    echo "$1" | awk -F: '{ print ($1 * 3600) + ($2 * 60) + $3 }'
}

# Extract keyframe timestamps
keyframes=($(ffprobe -loglevel error -select_streams v:0 \
    -show_entries frame=pkt_pts_time -of csv=print_section=0 \
    -skip_frame nokey "$input" | sort -n))

# Process each overlay interval
for interval in "${overlay_intervals[@]}"; do
    read start end <<< "$interval"
    start_sec=$(to_seconds "$start")
    end_sec=$(to_seconds "$end")
    
    # Find nearest keyframes
    kf_start=$(awk -v t="$start_sec" 'BEGIN {m=t} {if ($1<=t && t-$1<m) m=t-$1} END {print t-m}' keyframes.txt)
    kf_end=$(awk -v t="$end_sec" 'BEGIN {m=t} {if ($1>=t && $1-t<m) m=$1-t} END {print t+m}' keyframes.txt)
    
    # Extract segment (lossless)
    ffmpeg -ss "$kf_start" -to "$kf_end" -i "$input" -c copy "segment_${start_sec}.mp4"
    
    # Add text overlay (only re-encode this snippet)
    ffmpeg -i "segment_${start_sec}.mp4" -vf \
    "drawtext=text='YOUR OVERLAY TEXT':fontsize=40:fontcolor=white:box=1:boxcolor=black@0.5: \
    x=(w-tw)/2:y=h-th-10:enable='between(t,${start_sec}-${kf_start},${end_sec}-${kf_start})'" \
    -c:a copy -c:v libx264 -preset fast -crf 23 "overlay_${start_sec}.mp4"
done

# Rebuild video (concatenate all parts)
# 1. Pre-overlay segment (0s to first overlay start)
ffmpeg -ss 0 -to "$kf_start" -i "$input" -c copy "part1.mp4"

# 2. Overlay segments (already processed)

# 3. Post-overlay segment (last overlay end to video end)
ffmpeg -ss "$kf_end" -i "$input" -c copy "part_final.mp4"

# Generate concat list
for f in part1.mp4 overlay_*.mp4 part_final.mp4; do echo "file '$f'"; done > concat.txt
ffmpeg -f concat -safe 0 -i concat.txt -c copy "$output"

# Cleanup
rm segment_*.mp4 overlay_*.mp4 part*.mp4 concat.txt keyframes.txt