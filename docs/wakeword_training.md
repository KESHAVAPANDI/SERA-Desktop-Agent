# SERA 1.0 — Local Custom Wake-Word Training Specification
**Future "Hey SERA" Keyword Detection Architecture**

---

## 1. Architectural Strategy
SERA will utilize a **100% local, zero-cloud custom acoustic keyword model** (e.g. lightweight TFLite / ONNX acoustic CNN or embedding classifier).
- **Target Phrase:** `"Hey SERA"`.
- **Target Model Path:** `models/wakeword/hey_sera.tflite`.
- **Current State:** `NOT CONFIGURED` (No fake models, no cloud calls).

---

## 2. Dataset Collection & Structure

```
dataset/wakeword/
├── positive/          # 2,000+ clean recordings of "Hey SERA" across diverse accents & genders
├── hard_negative/     # Phonetically similar phrases ("Hey Siri", "Hey Sarah", "Hey Sierra", "Sara")
├── general_negative/  # General conversational speech (LibriSpeech / CommonVoice subsets)
├── background_noise/  # Ambient domestic and office sounds (fans, typing, music, clicks)
└── test/              # Balanced validation suite for ROC curve & false-accept evaluation
```

---

## 3. Training & Evaluation Pipeline
1. **Audio Feature Extraction:** 16kHz mono audio $\to$ 40-band Log-Mel Spectrograms with 30ms window and 10ms hop.
2. **Augmentation:** SpecAugment (frequency and time masking), background noise mixing (SNR 5dB to 20dB), pitch shift, and volume scaling.
3. **Model Architecture:** Depthwise separable convolutional neural network (DS-CNN) or micro-transformer (<500K parameters).
4. **Quantization:** Int8 post-training quantization for low-latency CPU inference (<15ms per chunk).
5. **False Positive Rejection:** Benchmark against 100+ hours of continuous conversational audio; target False Accept Rate (FAR) $<0.1$ per hour at $>98\%$ True Accept Rate (TAR).

---

## 4. Subsystem Integration
The `app/speech/wakeword/` directory provides the runtime interfaces:
- `WakeWordProvider`: Base abstract provider.
- `LocalCustomWakeWordProvider`: Loads `.tflite` model when present, falling back cleanly to `is_available = False` and status `NOT CONFIGURED`.
- `WakeWordEvaluator`: Diagnostic scoring and benchmark runner.
