# 12｜研究与官方参考资料

本页是研究地图，不代表任何单一模型已经完整解决 MeantByMe 的开放式残缺意图恢复任务。

## Atypical speech recognition

### Speech Accessibility Project

- https://speechaccessibilityproject.beckman.illinois.edu/
- https://machinelearning.apple.com/research/accessibility-project-challenge

意义：

- 专门异常语音数据和适配很重要；
-大型数据集可显著改善 ASR；
-WER 不等于开放式意图恢复准确率。

### Personalized ASR research

- https://research.google/pubs/personalizing-asr-for-dysarthric-and-accented-speech-with-limited-data/
- https://research.google/pubs/residual-adapters-for-parameter-efficient-asr-adaptation-to-atypical-and-accented-speech/
- https://research.google/pubs/an-analysis-of-degenerating-speech-due-to-progressive-dysarthria-on-asr-performance/

意义：

- 少量个人数据有价值；
-参数高效适配可行；
-进行性疾病需要近期数据更新。

### CDSD

- http://melab.psych.ac.cn/CDSD.html
- https://www.isca-archive.org/interspeech_2024/wan24b_interspeech.html

中文构音障碍 ASR 资源，不是开放式意图数据集。

## Intent and SLU

### HeyJay!

- https://www.nature.com/articles/s41597-026-07497-5

意义：

- 异常语音 + transcript + intent；
-适合未来英语 Quick Intent；
-主要是 scripted commands；
-不是开放式残缺表达模型；
-数据访问可能受限。

### Fluent Speech Commands

- https://fluent.ai/fluent-speech-commands-a-dataset-for-spoken-language-understanding-research/

### SLURP

- https://github.com/pswietojanski/slurp

## Cascade architecture

### Re-Sonance

团队使用的论文入口：

- https://arxiv.org/abs/2607.17615

意义：

- 支持 ASR → LLM → TTS 级联；
-LLM 在 ASR 保留证据时可改善语义；
-严重语音仍困难；
-MeantByMe 增加多候选、患者确认、授权和 Memory。

## Personal phrase matching

### PB-DSR

- https://arxiv.org/abs/2407.18461

### Apple latent phrase matching

- https://machinelearning.apple.com/research/latent-phrase-matching

适合少量高频个人短语，不是完整开放词汇系统。

## ASR models

- Qwen3-ASR: https://github.com/QwenLM/Qwen3-ASR
- Qwen3-ASR 1.7B: https://huggingface.co/Qwen/Qwen3-ASR-1.7B
- Whisper: https://github.com/openai/whisper
- Whisper paper: https://arxiv.org/abs/2212.04356
- whisper.cpp: https://github.com/ggml-org/whisper.cpp
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice
- FunASR: https://github.com/modelscope/FunASR
- Paraformer: https://arxiv.org/abs/2206.08317

## LLM and retrieval

- StepFun overview: https://platform.stepfun.com/docs/zh/guides/models/overview
- StepFun tool calling: https://platform.stepfun.com/docs/zh/api-reference/tool-call
- Qwen3: https://github.com/QwenLM/Qwen3
- Qwen3-Embedding: https://github.com/QwenLM/Qwen3-Embedding
- FAISS: https://github.com/facebookresearch/faiss

## TTS

- StepAudio TTS: https://platform.stepfun.com/docs/zh/guides/models/stepaudio-2.5-tts
- Voice creation: https://platform.stepfun.com/docs/zh/api-reference/audio/create-voice
- Audio creation: https://platform.stepfun.com/docs/zh/api-reference/audio/create-audio
- CosyVoice: https://github.com/FunAudioLLM/CosyVoice
- OpenVoice: https://github.com/myshell-ai/OpenVoice

## viaim

- https://pypi.org/project/viaim-ai-open/
- https://open.viaim.cn/tacit/portal/home

## macOS / Desktop

- PySide6: https://doc.qt.io/qtforpython-6/
- Deployment: https://doc.qt.io/qtforpython-6/deployment/index.html
- MLX: https://github.com/ml-explore/mlx
- MLX-LM: https://github.com/ml-explore/mlx-lm

## Provenance

- Ed25519 / RFC 8032: https://www.rfc-editor.org/info/rfc8032
- C2PA: https://spec.c2pa.org/about/
- W3C VC: https://www.w3.org/TR/vc-overview/

## AAC interaction

- https://www.asha.org/practice-portal/professional-issues/augmentative-and-alternative-communication/
- https://www.asha.org/practice/communication-access/communication-aids/

## Evidence boundary

不要声称：

- 通用模型能恢复患者唯一真实意图；
-英语 benchmark 可直接迁移到所有语言；
-LLM 能在声学证据缺失时可靠恢复；
-模拟数据是患者或临床验证。

安全表述：

> Existing research supports personalized atypical-speech recognition, cascade processing, and bounded intent classification. MeantByMe contributes a consent-first interaction and runtime architecture for handling unavoidable uncertainty.
