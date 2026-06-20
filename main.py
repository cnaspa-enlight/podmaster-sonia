import os
import json
import shutil
import subprocess
import webrtcvad
import time

# Define folders
drive_input_folder = {your input path}
drive_output_folder = {your output path}
local_temp_folder = "/content/local_temp_process" #running in google colab so it's the path for local run 

os.makedirs(drive_output_folder, exist_ok=True)
os.makedirs(local_temp_folder, exist_ok=True)

# Padding window to ensure breath transitions sound natural
PADDING_START = 0.1
PADDING_END = 0.3

print("Starting True Single-Export Mastering & Silence Removal Engine...\n")

for filename in os.listdir(drive_input_folder):
    _, ext = os.path.splitext(filename.lower())
    if ext in [".wav", ".mp3", ".flac", ".ogg", ".m4a"]:
        start_time = time.time()
        base_filename, _ = os.path.splitext(filename)
        
        drive_input_path = os.path.join(drive_input_folder, filename)
        local_input_path = os.path.join(local_temp_folder, filename)
        drive_output_path = os.path.join(drive_output_folder, f"{base_filename}{ext}")

        print(f"⚡ Processing File: '{filename}'")
        print("  [1/4] Copying to high-speed local workspace...")
        shutil.copy(drive_input_path, local_input_path)

        # -----------------------------------------------------------------
        # STEP 1: 2-PASS LOUDNESS PROFILE ANALYSIS
        # -----------------------------------------------------------------
        print("  [2/4] Analyzing audio profile metrics...")
        pass1_cmd = [
            "ffmpeg", "-i", local_input_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(pass1_cmd, capture_output=True, text=True)
        
        stderr_output = result.stderr
        json_start = stderr_output.find("{")
        json_end = stderr_output.rfind("}") + 1
        
        if json_start == -1 or json_end == 0:
            print(f"  ❌ Analysis Failed for {filename}. Skipping file.")
            continue
        stats = json.loads(stderr_output[json_start:json_end])

        # -----------------------------------------------------------------
        # STEP 2: RUNNING AI VAD SPEECH SCANNER
        # -----------------------------------------------------------------
        print("  [3/4] Running AI Voice Activity Detection (VAD)...")
        from pydub import AudioSegment
        vad_audio = AudioSegment.from_file(local_input_path).set_frame_rate(16000).set_channels(1)
        
        vad = webrtcvad.Vad(1)  # Aggressiveness profile (1)
        frame_duration = 30  # ms
        vad_frame_bytes = int(vad_audio.frame_rate * (frame_duration / 1000) * 2)
        
        vad_raw_data = vad_audio.raw_data
        offset = 0
        total_bytes = len(vad_raw_data)
        
        speech_timings = []
        is_recording = False
        current_start = 0.0
        
        time_step = frame_duration / 1000.0
        current_sec = 0.0

        while offset + vad_frame_bytes <= total_bytes:
            vad_frame = vad_raw_data[offset : offset + vad_frame_bytes]
            is_speech = vad.is_speech(vad_frame, vad_audio.frame_rate)

            if is_speech and not is_recording:
                current_start = max(0.0, current_sec - PADDING_START)
                is_recording = True
            elif not is_speech and is_recording:
                current_end = min(vad_audio.duration_seconds, current_sec + PADDING_END)
                speech_timings.append((current_start, current_end))
                is_recording = False

            offset += vad_frame_bytes
            current_sec += time_step
            
        if is_recording:
            speech_timings.append((current_start, vad_audio.duration_seconds))

        del vad_audio

        # Merge intersecting timing paths
        merged_timings = []
        if speech_timings:
            speech_timings.sort(key=lambda x: x[0])
            curr_start, curr_end = speech_timings[0]
            for start, end in speech_timings[1:]:
                if start <= curr_end:
                    curr_end = max(curr_end, end)
                else:
                    merged_timings.append((curr_start, curr_end))
                    curr_start, curr_end = start, end
            merged_timings.append((curr_start, curr_end))

        # -----------------------------------------------------------------
        # STEP 3: MASTER CLEAN + MULTI-TRIM & SINGLE EXPORT
        # -----------------------------------------------------------------
        if merged_timings:
            print(f"  [4/4] Executing Master Chain & Silence Purge ({len(merged_timings)} sections)...")
            
            # 1. Build the lightweight slice filters directly from the input stream [0:a]
            filter_parts = []
            for i, (start, end) in enumerate(merged_timings):
                filter_parts.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}];")
            
            # 2. Stitch the slices together first into a temporary map [stitched]
            concat_inputs = "".join([f"[a{i}]" for i in range(len(merged_timings))])
            filter_parts.append(f"{concat_inputs}concat=n={len(merged_timings)}:v=0:a=1[stitched];")
            
            # 3. Apply the heavy mastering chain exactly ONCE onto the final [stitched] timeline
            # FIXED: Swapped 'soft-oncoming=1' to 'soft-knee=1' for FFmpeg 4.4 compatibility
            master_chain_filter = (
                f"[stitched]agate=threshold=0.0056:ratio=2:range=0.01,highpass=f=80,"
                f"compand=attacks=0.3:decays=0.8:points=-90/-90|-45/-25|-15/-15|0/-11:soft-knee=1,"
                f"loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:"
                f"measured_i={stats['input_i']}:measured_tp={stats['input_tp']}:"
                f"measured_lra={stats['input_lra']}:measured_thresh={stats['input_thresh']}[outa]"
            )
            filter_parts.append(master_chain_filter)
            
            final_filter_script = "".join(filter_parts)
            
            filter_file_path = os.path.join(local_temp_folder, "master_filter.txt")
            with open(filter_file_path, "w", encoding="utf-8") as f:
                f.write(final_filter_script)

            # Build command parameters
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", local_input_path,
                "-filter_complex_script", filter_file_path,
                "-map", "[outa]"
            ]

            if ext == ".mp3":
                ffmpeg_cmd += ["-c:a", "libmp3lame", "-q:a", "0"]
            elif ext == ".m4a":
                ffmpeg_cmd += ["-c:a", "aac", "-q:a", "2"]
            elif ext in [".wav", ".flac"]:
                ffmpeg_cmd += ["-c:a", "pcm_s16le" if ext == ".wav" else "flac"]

            ffmpeg_cmd.append(drive_output_path)
            
            # Run the command and save the file directly to your Drive
            render_res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            
            if os.path.exists(filter_file_path):
                os.remove(filter_file_path)

            if render_res.returncode == 0:
                elapsed = time.time() - start_time
                print(f"  🎉 SUCCESS: Processed and Saved Mastered Track directly to Drive!")
                print(f"  👉 Path: {drive_output_path} (Took {elapsed:.1f} seconds)\n")
            else:
                print(f"  ❌ FFmpeg Engine Render Error:\n{render_res.stderr.decode('utf-8')}\n")
        else:
            print("  ⚠️ Warning: No speech segments detected inside file.\n")

        if os.path.exists(local_input_path):
            os.remove(local_input_path)

# Final complete folder purge
shutil.rmtree(local_temp_folder, ignore_errors=True)
print("All podcast tasks completed successfully!")
