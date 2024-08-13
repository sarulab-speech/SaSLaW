import numpy as np
import os
from pathlib import Path
import re
from pyannote.audio import Audio
from pyannote.core import Segment
import bisect
import soundfile as sf

import sys

target_dir = Path(sys.argv[1]) # argv example: ~/dataset/SaSLaW-ver1/spk01
listen_dir = target_dir / "listen"
assert listen_dir.exists()

listen_segmented_dir = target_dir / "listen_segment"
listen_segmented_dir.mkdir(exist_ok=True)

target_speech_dir = target_dir / "speech_segment"
assert target_speech_dir.exists()

target_seginfo_dir = target_dir / "seg_info"
assert target_seginfo_dir.exists()

aite_seginfo_dir = target_dir.parent / sys.argv[2] / "seg_info" # argv example: spk02
assert aite_seginfo_dir.exists()

audio_processor = Audio(sample_rate=44100, mono=False)

sample_rate = 44100

audio_processor = Audio(sample_rate=sample_rate, mono=False)

listen_max_segment_second = 99. # 直前ターンの受聴音の上限長

i = 1
while True:
    start_pattern = f"dialogue{i:>03}"
    print(start_pattern)
    speech_list = list(target_speech_dir.glob(f'{start_pattern}*'))
    if len(speech_list) == 0:
        break
    speech_list.sort(key=lambda x: x.name)

    target_seginfo = np.loadtxt(target_seginfo_dir / f"{start_pattern}.txt", dtype=np.float64)
    aite_seginfo = np.loadtxt(aite_seginfo_dir / f"{start_pattern}.txt", dtype=np.float64)
    aite_segendinfo = aite_seginfo.T.tolist()[-1]
    # print(aite_segendinfo)
    for j, speech in enumerate(speech_list):
        aite_segpos = bisect.bisect_right(aite_segendinfo, target_seginfo[j,0]) - 1
        if aite_segpos < 0:
            res_seg = np.array([0, max(target_seginfo[0, 0], 0.2)]) # 0.2 秒の環境音を確保する
        else:
            res_seg = aite_seginfo[aite_segpos]

        segment = Segment(start=max(res_seg[0], res_seg[1] - listen_max_segment_second), 
                          end=res_seg[1])
        
        waveform, sample_rate = audio_processor.crop(str(listen_dir / f"{start_pattern}.wav"), segment)

        segment_save_path = listen_segmented_dir / speech.name
        sf.write(str(segment_save_path), 
                 waveform.squeeze().numpy().T, 
                 sample_rate
                 )

    i += 1