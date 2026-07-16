import os
import subprocess
import whisper
import json
import math
from utils.config import WHISPER_MODEL,CHUNK_SIZE

WHISPER_MODEL_SELECTED = whisper.load_model(WHISPER_MODEL)

def process_video_pipeline(video_path,base_data_dir="data"):
    filename = os.path.splitext(os.path.basename(video_path))[0]

    audio_dir = os.path.join(base_data_dir, "audios")
    json_dir = os.path.join(base_data_dir, "jsons")
    prep_dir = os.path.join(base_data_dir, "preprocessed")
    for d in [audio_dir, json_dir, prep_dir]: os.makedirs(d, exist_ok=True)

    #1.Extract Audio
    audio_path = os.path.join(audio_dir, f"{filename}.mp3")
    if not os.path.exists(audio_path):
        subprocess.run(["ffmpeg", "-y", "-i", video_path, audio_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    #2.Transcribe
    result = WHISPER_MODEL_SELECTED.transcribe(
        audio = audio_path,
        task = "translate",
        word_timestamps = False
    )
    chunks = []
    for segment in result['segments']:
        chunks.append({
            "source":os.path.basename(video_path),
            "start":segment['start'],
            "end":segment['end'],
            "text":segment['text']
        })

    #3.chunk preprocessing (n grouping for better results from LLM)
    n = CHUNK_SIZE
    new_chunks = []
    num_chunks = len(chunks)
    num_groups = math.ceil(num_chunks/n)

    for i in range(num_groups):
        start_idx = i*n
        end_idx = min((i+1)*n,num_chunks)
        chunk_group = chunks[start_idx:end_idx]

        new_chunks.append({
            'source':chunk_group[0]['source'],
            'start':chunk_group[0]['start'],
            'end':chunk_group[-1]['end'],
            'text':" ".join(c['text'].strip() for c in chunk_group)
        })

    #4.save preprocessed json
    prep_json_path = os.path.join(prep_dir,f"{filename}.json")
    with open(prep_json_path,"w",encoding="utf-8") as f:
        json.dump(
            {
                "chunks":new_chunks,
                "text":result['text']
            },
            f,indent=4,
            ensure_ascii=False
        )

    return prep_json_path