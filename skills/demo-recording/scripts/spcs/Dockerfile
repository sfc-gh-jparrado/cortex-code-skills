FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir numpy

RUN pip3 install --no-cache-dir \
    torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121

RUN pip3 install --no-cache-dir packaging ninja psutil

RUN MAX_JOBS=4 pip3 install --no-cache-dir flash-attn --no-build-isolation

RUN mkdir -p /flash_attn_export && \
    cp -r /usr/local/lib/python3.10/dist-packages/flash_attn /flash_attn_export/ && \
    cp /usr/local/lib/python3.10/dist-packages/flash_attn_2_cuda*.so /flash_attn_export/ && \
    cp -r /usr/local/lib/python3.10/dist-packages/flash_attn*.dist-info /flash_attn_export/

FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

LABEL org.opencontainers.image.title="voice-cloner" \
      org.opencontainers.image.description="SPCS voice cloning with Qwen3-TTS + flash-attn + whisper" \
      org.opencontainers.image.version="3.0.2" \
      skill.name="demo-recording"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg sox && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir numpy

RUN pip3 install --no-cache-dir \
    torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121

RUN pip3 install --no-cache-dir \
    qwen-tts \
    soundfile \
    openai-whisper

RUN python3 -c "import whisper; whisper.load_model('tiny', download_root='/app/whisper_models')"

COPY --from=builder /flash_attn_export/ /usr/local/lib/python3.10/dist-packages/
RUN python3 -c "import flash_attn; print(f'flash_attn {flash_attn.__version__} verified OK')"

COPY job_clone_voice.py /app/job_clone_voice.py

WORKDIR /app

ENTRYPOINT ["python3", "-u", "job_clone_voice.py"]
