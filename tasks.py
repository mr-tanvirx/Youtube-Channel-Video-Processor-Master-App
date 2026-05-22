import os
import subprocess
import queue
import threading
import time
import gc
from pathlib import Path
import whisper
import torch

def get_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

# --- NEW: SRT Time mathematical adjustment engine ---
def adjust_srt_speed(input_srt, output_srt, speed):
    def parse_srt_time(time_str):
        h, m, s_ms = time_str.replace(',', '.').split(':')
        return int(h) * 3600 + int(m) * 60 + float(s_ms)

    def format_srt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            s += 1
            ms -= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(input_srt, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(output_srt, 'w', encoding='utf-8') as f:
        for line in lines:
            if '-->' in line:
                try:
                    parts = line.strip().split('-->')
                    start_sec = parse_srt_time(parts[0].strip()) / speed
                    end_sec = parse_srt_time(parts[1].strip()) / speed
                    f.write(f"{format_srt_time(start_sec)} --> {format_srt_time(end_sec)}\n")
                except Exception:
                    f.write(line) # Fallback if line is malformed
            else:
                f.write(line)
# ---------------------------------------------------

def build_ffmpeg_cmd(in_file, original_file, out_file, out_dir, task, config, device, duration, active_srt=None):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    
    is_gpu = "cuda" in device
    if is_gpu:
        device_id = device.split(":")[1] if ":" in device else "0"
        cmd.extend(["-hwaccel", "cuda", "-hwaccel_device", device_id])

    cmd.extend(["-i", str(in_file)])

    if task == "upscale":
        speed = float(config.get("speed", 1.0))
        speed_only = config.get("speedOnly", False)
        trim_dur = max(duration - 2.5, 0.1)

        if speed_only:
            v_filter = f"[0:v]setpts={1/speed}*PTS[vout]"
            a_filter = "[0:a]"
            if speed != 1.0:
                if speed > 2.0:
                    a_filter += f"atempo=2.0,atempo={speed/2.0}[aout]"
                elif speed < 0.5:
                    a_filter += f"atempo=0.5,atempo={speed/0.5}[aout]"
                else:
                    a_filter += f"atempo={speed}[aout]"
            else:
                a_filter += "anull[aout]"
                
            cmd.extend(["-filter_complex", f"{v_filter};{a_filter}", "-map", "[vout]", "-map", "[aout]"])
        else:
            banner_path = Path("banner.png").absolute()
            if not banner_path.exists():
                raise FileNotFoundError("banner.png is missing from the root directory.")
                
            banner_str = str(banner_path).replace('\\', '/')
            if banner_str[1] == ':':
                banner_str = banner_str[0] + '\\:' + banner_str[2:]
                
            cmd.extend(["-i", str(banner_path)])
            
            v_filter = f"[0:v]trim=end={trim_dur},unsharp=5:5:1.5:5:5:0.8,scale=3840:2160:flags=lanczos,setpts={1/speed}*PTS[bg];"
            v_filter += f"[1:v]scale=iw*0.43:-1[fg];"
            v_filter += f"[bg][fg]overlay=W-w-120:H-h-(-50)[vout]"
            
            a_filter = f"[0:a]atrim=end={trim_dur}"
            if speed != 1.0:
                if speed > 2.0:
                    a_filter += f",atempo=2.0,atempo={speed/2.0}"
                elif speed < 0.5:
                    a_filter += f",atempo=0.5,atempo={speed/0.5}"
                else:
                    a_filter += f",atempo={speed}"
            a_filter += "[aout]"
            
            cmd.extend(["-filter_complex", f"{v_filter};{a_filter}", "-map", "[vout]", "-map", "[aout]"])

    elif task == "burn":
        if active_srt is None or not active_srt.exists():
            raise FileNotFoundError(f"Subtitle file not found.")

        srt_str = str(active_srt.absolute()).replace('\\', '/')
        if srt_str[1] == ':':
            srt_str = srt_str[0] + '\\:' + srt_str[2:]
            
        size = config.get("fontSize", 18)
        # BENGALI FONT FIX: Explicitly enforce Nirmala UI
        style = f"FontName=Nirmala UI,FontSize={size},PrimaryColour=&H00FFFFFF,BackColour=&H00000000,BorderStyle=1,Outline=0.5,Shadow=0"
        cmd.extend(["-vf", f"subtitles='{srt_str}':force_style='{style}'"])

    if is_gpu:
        cmd.extend(["-c:v", "hevc_nvenc", "-preset", "p4", "-cq", "26", "-gpu", device_id, "-c:a", "aac", "-b:a", "192k"])
    else:
        threads = max(1, os.cpu_count() - 2)
        cmd.extend(["-c:v", "libx264", "-preset", "faster", "-crf", "23", "-threads", str(threads), "-c:a", "aac", "-b:a", "192k"])

    cmd.append(str(out_file))
    return cmd

def process_file_task(in_file, original_file, out_dir, task, config, device, update_fn, models_cache, cancel_event):
    if cancel_event.is_set(): return False, None
    
    try:
        if task == "extract":
            srt_out = out_dir / f"{original_file.stem}.srt"
            
            if not srt_out.exists():
                extract_mode = config.get("extractTask", "transcribe")
                log_action = "Translating to English" if extract_mode == "translate" else "Extracting subtitles"
                update_fn(log=f"[{device}] {log_action} for {original_file.name}...")
                
                model_name = config.get("model", "medium")
                lang = config.get("language", "")
                
                # --- MEMORY OPTIMIZATION: Load into System RAM initially ---
                if device not in models_cache:
                    if "cuda" in device: torch.set_num_threads(1)
                    models_cache[device] = whisper.load_model(model_name, device="cpu")
                
                if cancel_event.is_set(): return False, None
                
                # --- Shift model from RAM to Target Device (GPU) for active processing ---
                active_model = models_cache[device].to(device)
                
                # --- WHISPER CONFIGURATION ---
                options = {
                    "fp16": "cuda" in device,
                    "word_timestamps": True,
                    "no_speech_threshold": 0.45,
                    "compression_ratio_threshold": 2.0,
                    "logprob_threshold": -1.0,
                    "task": extract_mode 
                }
                
                if extract_mode == "translate":
                    if lang and lang != "auto":
                        options["language"] = lang
                    options["condition_on_previous_text"] = False
                else:
                    if lang and lang != "auto": 
                        options["language"] = lang
                        if lang == "bn":
                            options["initial_prompt"] = "এখানে পরিষ্কার বাংলায় কথা বলা হয়েছে।" 
                        elif lang == "hi":
                            options["initial_prompt"] = "यहाँ साफ़ हिंदी में बात की गई है।"
                    options["condition_on_previous_text"] = False
                
                result = active_model.transcribe(str(in_file), **options)
                
                with open(srt_out, "w", encoding="utf-8") as f:
                    for i, seg in enumerate(result["segments"], 1):
                        f.write(f"{i}\n")
                        start = time.strftime('%H:%M:%S', time.gmtime(seg['start'])) + f",{int(seg['start']%1*1000):03d}"
                        end = time.strftime('%H:%M:%S', time.gmtime(seg['end'])) + f",{int(seg['end']%1*1000):03d}"
                        f.write(f"{start} --> {end}\n{seg['text'].strip()}\n\n")

                # --- MEMORY OPTIMIZATION: Shift model back to System RAM & Clear GPU Cache ---
                active_model.to("cpu")
                if "cuda" in device:
                    gc.collect()
                    torch.cuda.empty_cache()
                    
            return True, in_file

        elif task == "upscale":
            suffix = "_processed" if config.get("speedOnly") else "_4k"
            out_file = out_dir / f"{in_file.stem}{suffix}.mp4"
            
            if not out_file.exists():
                update_fn(log=f"[{device}] Running upscale/speed adjustment for {original_file.name}...")
                duration = get_duration(in_file)
                cmd = build_ffmpeg_cmd(in_file, original_file, out_file, out_dir, task, config, device, duration)
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                
                while process.poll() is None:
                    if cancel_event.is_set():
                        process.terminate()
                        update_fn(log=f"[{device}] Process terminated: {original_file.name}")
                        if out_file.exists(): out_file.unlink()
                        return False, None
                    time.sleep(0.5)
                
                if process.returncode != 0:
                    _, err = process.communicate()
                    update_fn(log=f"[{device}] FFmpeg Error on {original_file.name}: {err}")
                    return False, None

            return True, out_file

        elif task == "burn":
            automate = config.get("automate", False)
            speed = float(config.get("speed", 1.0))
            
            # Subtitle file path logic
            original_srt = out_dir / f"{original_file.stem}.srt"
            active_srt = original_srt
            
            # --- Auto-Adjust Subtitles for Speed Modifications ---
            if speed != 1.0:
                active_srt = out_dir / f"{original_file.stem}_speed_{speed}.srt"
                if not active_srt.exists() and original_srt.exists():
                    adjust_srt_speed(original_srt, active_srt, speed)
                    update_fn(log=f"[{device}] Mathematically synced subtitles to {speed}x speed.")
            
            if automate:
                final_dir = out_dir / "final"
                final_dir.mkdir(exist_ok=True)
                out_file = final_dir / f"Final_Processed_{original_file.stem}.mp4"
            else:
                out_file = out_dir / f"{in_file.stem}_burned.mp4"

            if not out_file.exists():
                update_fn(log=f"[{device}] Burning subtitles into {original_file.name}...")
                duration = get_duration(in_file)
                cmd = build_ffmpeg_cmd(in_file, original_file, out_file, out_dir, task, config, device, duration, active_srt=active_srt)
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                
                while process.poll() is None:
                    if cancel_event.is_set():
                        process.terminate()
                        if out_file.exists(): out_file.unlink()
                        return False, None
                    time.sleep(0.5)
                
                if process.returncode != 0:
                    _, err = process.communicate()
                    update_fn(log=f"[{device}] FFmpeg Error on {original_file.name}: {err}")
                    return False, None

            return True, out_file

    except Exception as e:
        update_fn(log=f"[{device}] ERROR on {original_file.name} ({task}): {str(e)}")
        return False, None

def worker_logic(q, device, update_fn, models_cache, progress_state, cancel_event):
    while not q.empty():
        if cancel_event.is_set(): break
        try:
            job = q.get_nowait()
        except queue.Empty:
            break
            
        original_file, out_dir, task_list, config = job
        current_file = original_file
        
        for task in task_list:
            success, next_file = process_file_task(current_file, original_file, out_dir, task, config, device, update_fn, models_cache, cancel_event)
            
            if not success: break
            current_file = next_file
            
            if not cancel_event.is_set():
                with progress_state["lock"]:
                    progress_state["completed"] += 1
                    percent = int((progress_state["completed"] / progress_state["total"]) * 100)
                    update_fn(progress=percent)
                
        q.task_done()

def process_jobs(config, update_fn, cancel_event):
    input_type = config.get("inputType", "folder")
    same_as_input = config.get("sameAsInput", False)
    
    files = []
    video_exts = {'.mp4', '.mkv', '.avi', '.mov'}

    if input_type == "file":
        in_path = Path(config["inputFile"])
        if not in_path.exists() or not in_path.is_file():
            raise FileNotFoundError("Specified input file does not exist.")
        if in_path.suffix.lower() in video_exts:
            files.append(in_path)
    else:
        in_path = Path(config["inputFolder"])
        if not in_path.exists() or not in_path.is_dir():
            raise FileNotFoundError("Specified input directory does not exist.")
        files = [f for f in in_path.iterdir() if f.suffix.lower() in video_exts]

    if not files:
        raise ValueError("No valid video files found in the specified input path.")

    start_tab = int(config["startTab"])
    automate = config["automate"]
    
    workflow = []
    if start_tab == 1:
        workflow = ["extract", "upscale", "burn"] if automate else ["extract"]
    elif start_tab == 2:
        workflow = ["upscale", "burn"] if automate else ["upscale"]
    elif start_tab == 3:
        workflow = ["burn"]

    devices = []
    if config.get("gpu0"): devices.append("cuda:0")
    if config.get("gpu1"): devices.append("cuda:1")
    if config.get("cpu") or not devices: devices.append("cpu")

    update_fn(log=f"Delegating {len(files)} files across {len(devices)} device(s).")

    job_queue = queue.Queue()
    for f in files:
        if same_as_input:
            out_dir = f.parent / "output"
        else:
            out_dir = Path(config["outputFolder"])
            
        if not out_dir.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
            
        job_queue.put((f, out_dir, workflow, config))

    models_cache = {}
    progress_state = {
        "completed": 0,
        "total": len(files) * len(workflow),
        "lock": threading.Lock()
    }
    
    threads = []
    for device in devices:
        t = threading.Thread(target=worker_logic, args=(job_queue, device, update_fn, models_cache, progress_state, cancel_event))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()