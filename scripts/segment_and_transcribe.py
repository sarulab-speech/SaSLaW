from transformers import WhisperProcessor, WhisperForConditionalGeneration
from datasets import load_dataset
from pathlib import Path
import os

from pyannote.audio import Model, Audio 
from pyannote.core import Annotation, Segment
from pyannote.audio.pipelines import VoiceActivityDetection
import torchaudio as ta
import soundfile as sf
from tqdm import tqdm

import sys

processor_asr = WhisperProcessor.from_pretrained("openai/whisper-large-v2")
model_asr = WhisperForConditionalGeneration.from_pretrained("openai/whisper-large-v2").cuda()
model_asr.config.forced_decoder_ids = None

model_vad = Model.from_pretrained(
    "pyannote/segmentation-3.0",
    use_auth_token=os.environ.get("HF_ACCESS_TOKEN")
)

pipeline = VoiceActivityDetection(segmentation=model_vad)
HYPER_PARAMETERS = {
  # remove speech regions shorter than that many seconds.
  "min_duration_on": 0.3,
  # fill non-speech regions shorter than that many seconds.
  "min_duration_off": 0.0
}
pipeline.instantiate(HYPER_PARAMETERS)

source_dir = Path(sys.argv[1]) / "speech" # argv example: ~/dataset/SaSLaW-ver1/spk01
segment_info_dir = source_dir.parent / "seg_info"
segment_info_dir.mkdir(exist_ok=True)
segment_dir = source_dir.parent / "speech_segment"
segment_dir.mkdir(exist_ok=True)
segment_script_dir = source_dir.parent / "transcript_segment"
segment_script_dir.mkdir(exist_ok=True)
audio_files = list(source_dir.iterdir())
audio_files.sort()

sample_rate = 44100

audio_processor = Audio(sample_rate=sample_rate, mono=True)

resampler = ta.transforms.Resample(orig_freq=sample_rate, new_freq=16000)

for audiopath in tqdm(audio_files):
    total_duration = audio_processor.get_duration(audiopath)
    vad: Annotation = pipeline(str(audiopath))
    with open(segment_info_dir / f"{audiopath.stem}.txt", mode="w") as o:
        o.write('\n'.join([' '.join(map(str, segment)) for segment in vad.get_timeline(copy=True)]))
    #print(vad.get_timeline())

    for i, (segment, _) in enumerate(vad.itertracks(yield_label=False)):
        
        segment = Segment(start=max(0, segment.start-0.25), end=min(segment.end+0.25, total_duration))
        waveform, sample_rate = audio_processor.crop(str(audiopath), segment)

        segment_save_path = segment_dir / f"{audiopath.stem}-seg{i:>02}.wav"
        sf.write(str(segment_save_path), 
                 waveform.squeeze().numpy(), 
                 sample_rate
                 )     
        
        # transcribe
        input_features = processor_asr(resampler(waveform.squeeze()), sampling_rate=16000, return_tensors="pt").input_features

        predicted_ids = model_asr.generate(input_features.cuda())
        transcription = processor_asr.batch_decode(predicted_ids, skip_special_tokens=True)

        script_path = segment_script_dir / f"{audiopath.stem}-seg{i:>02}.txt"
        with open(script_path, mode="w", encoding="utf-8") as o_script:
            o_script.write(transcription[0])

        #print(segment.start, segment.end)
        #...