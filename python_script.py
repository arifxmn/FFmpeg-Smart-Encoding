import subprocess
import os
import tempfile
import shutil

# ===== USER SETTINGS - EDIT THESE VALUES =====
INPUT_VIDEO = "input_video.mp4"          # Your source video file
OUTPUT_VIDEO = "output_video.mp4"        # Output video file

# Text overlay settings
OVERLAYS = [
    # Format: [start_time, end_time, "Your text here"]
    ["00:10:00", "00:10:10", "First Message"],
    ["00:30:00", "00:30:10", "Second Message"],
    ["01:15:00", "01:15:10", "Final Reminder"]
]

FONT_SIZE = 40                     # Text size in pixels
FONT_COLOR = "white"               # Text color
BG_COLOR = "black@0.5"             # Background with opacity
X_POSITION = "(w-tw)/2"            # Center horizontally
Y_POSITION = "h-th-10"             # 10px from bottom
# ===== END OF USER SETTINGS =====

def time_to_seconds(t):
    h, m, s = map(float, t.split(':'))
    return h * 3600 + m * 60 + s

def get_keyframes(video):
    """Get keyframes with robust error handling"""
    try:
        cmd = [
            "ffprobe", "-loglevel", "error",
            "-select_streams", "v:0",
            "-show_entries", "frame=pkt_pts_time",
            "-of", "csv=p=0",
            "-skip_frame", "nokey",
            video
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return sorted(map(float, filter(None, result.stdout.splitlines())))
    except Exception as e:
        print(f"⚠️ Keyframe detection failed: {e}")
        print("⏩ Using default keyframes at start and end of video")
        return [0.0, 1e6]  # Fallback values

def main():
    # Verify input file exists
    if not os.path.exists(INPUT_VIDEO):
        print(f"❌ Error: Input file not found: {INPUT_VIDEO}")
        return
    
    # Create temporary workspace
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Temporary workspace: {temp_dir}")
    
    try:
        # Get video keyframes
        keyframes = get_keyframes(INPUT_VIDEO)
        print(f"🔑 Found {len(keyframes)} keyframes")
        
        # Process each overlay
        segments = []
        for i, (start, end, text) in enumerate(OVERLAYS):
            start_sec = time_to_seconds(start)
            end_sec = time_to_seconds(end)
            
            # Find nearest keyframes with fallbacks
            kf_start = max([k for k in keyframes if k <= start_sec] or [0])
            kf_end = min([k for k in keyframes if k >= end_sec] or [start_sec + 10])
            
            print(f"🎬 Processing overlay {i+1}: {start} to {end}")
            print(f"   📍 Using segment: {kf_start:.1f}s to {kf_end:.1f}s")
            
            # Extract segment
            seg_in = os.path.join(temp_dir, f"seg_{i}_in.mp4")
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(kf_start),
                "-to", str(kf_end),
                "-i", INPUT_VIDEO,
                "-c", "copy",
                seg_in
            ], check=True)
            
            # Add text overlay
            seg_out = os.path.join(temp_dir, f"seg_{i}_out.mp4")
            overlay_start = start_sec - kf_start
            overlay_end = end_sec - kf_start
            
            subprocess.run([
                "ffmpeg", "-y",
                "-i", seg_in,
                "-vf", f"drawtext=text='{text}':fontsize={FONT_SIZE}:"
                       f"fontcolor={FONT_COLOR}:box=1:boxcolor={BG_COLOR}:"
                       f"x={X_POSITION}:y={Y_POSITION}:"
                       f"enable='between(t,{overlay_start},{overlay_end})'",
                "-c:a", "copy",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                seg_out
            ], check=True)
            segments.append((kf_start, kf_end, seg_out))
        
        # Build concat list
        concat_file = os.path.join(temp_dir, "list.txt")
        with open(concat_file, "w") as f:
            current_time = 0
            
            for seg_start, seg_end, seg_file in segments:
                # Add segment before overlay
                if seg_start > current_time:
                    pre_seg = os.path.join(temp_dir, f"pre_{current_time}.mp4")
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-ss", str(current_time),
                        "-to", str(seg_start),
                        "-i", INPUT_VIDEO,
                        "-c", "copy",
                        pre_seg
                    ], check=True)
                    f.write(f"file '{pre_seg}'\n")
                    print(f"✅ Added unchanged segment: {current_time}s to {seg_start}s")
                
                # Add processed segment
                f.write(f"file '{seg_file}'\n")
                current_time = seg_end
                print(f"✅ Added overlay segment: {seg_start}s to {seg_end}s")
            
            # Add final segment
            final_seg = os.path.join(temp_dir, "final.mp4")
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(current_time),
                "-i", INPUT_VIDEO,
                "-c", "copy",
                final_seg
            ], check=True)
            f.write(f"file '{final_seg}'\n")
            print(f"✅ Added final segment: {current_time}s to end")
        
        # Combine segments
        print("🔗 Combining segments...")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            OUTPUT_VIDEO
        ], check=True)
        
        print(f"\n🎉 Success! Output saved to: {OUTPUT_VIDEO}")
    
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg command failed: {e.cmd}")
        print(f"Error output: {e.stderr.decode() if e.stderr else 'Unknown'}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
    finally:
        # Clean up temporary files
        shutil.rmtree(temp_dir)
        print("🧹 Temporary files cleaned up")

if __name__ == "__main__":
    main()