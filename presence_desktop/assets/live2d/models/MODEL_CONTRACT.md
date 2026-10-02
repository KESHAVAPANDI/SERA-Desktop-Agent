# Live2D Model Asset Contract & License Documentation

## 1. Primary Evaluation Model: Niziiro Mao (Cubism 4)

- **Character Name**: Niziiro Mao (虹色まお)
- **Format**: Live2D Cubism 4 (.model3.json, .moc3)
- **Source**: Official Live2D Cubism Web Samples Repository  
  [https://github.com/Live2D/CubismWebSamples](https://github.com/Live2D/CubismWebSamples) (`develop` branch, path: `Samples/Resources/Mao`)  
  Official Live2D Sample Data Collection: [https://www.live2d.com/en/learn/sample/](https://www.live2d.com/en/learn/sample/)
- **Core Runtime**: Official Live2D Cubism Core (`live2dcubismcore.min.js`), hosted by Live2D Inc. at `https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js`
- **Copyright & License**:
  - Model Copyright: (C) Live2D Inc.
  - Usage Terms: Governed by the **Live2D Free Material License Agreement** and **Live2D Cubism Sample Data Terms of Use** ([https://www.live2d.com/en/terms/](https://www.live2d.com/en/terms/)).
  - Free for evaluation, research, and non-commercial/commercial usage by General Users and Small-Scale Enterprises under Live2D's sample model policy.
  - Live2D Cubism Core is subject to the Live2D Open Software License / Proprietary Core runtime agreement.

---

## 2. Model Asset Directory Structure

Any Live2D model compatible with SERA Presence must follow this standard Cubism 4 file hierarchy:

```
presence_desktop/assets/live2d/models/<model_name>/
├── <model_name>.model3.json       # Top-level model manifest (Version 3)
├── <model_name>.moc3              # Compiled Cubism geometry and mesh data
├── <model_name>.physics3.json     # Dynamic physics calculation settings
├── <model_name>.pose3.json        # Part opacity/pose switching configuration
├── <model_name>.cdi3.json         # Parameter and Part display metadata
├── <model_name>.2048/             # Texture atlas folder (or 1024/4096)
│   └── texture_00.png             # Texture atlas sheet(s)
├── expressions/                   # Facial expression definitions
│   ├── exp_01.exp3.json           # Expression 1 (Neutral / Present)
│   ├── exp_02.exp3.json           # Expression 2 (Gentle Smile / Happy)
│   ├── exp_03.exp3.json           # Expression 3 (Eyes Closed / Resting)
│   ├── exp_04.exp3.json           # Expression 4 (Sparkle / Active)
│   ├── exp_05.exp3.json           # Expression 5 (Deliberate / Focused)
│   ├── exp_06.exp3.json           # Expression 6 (Thoughtful / Inward)
│   ├── exp_07.exp3.json           # Expression 7 (Surprise / Alert)
│   └── exp_08.exp3.json           # Expression 8 (Pout / Concerned)
└── motions/                       # Skeletal & parameter motion sequences
    ├── mtn_01.motion3.json        # Idle posture cycle A
    ├── mtn_02.motion3.json        # Tap / gesture cycle 1
    ├── mtn_03.motion3.json        # Tap / gesture cycle 2
    ├── mtn_04.motion3.json        # Action cycle
    ├── sample_01.motion3.json     # Idle posture cycle B
    ├── special_01.motion3.json    # Special gesture 1
    ├── special_02.motion3.json    # Special gesture 2
    └── special_03.motion3.json    # Special gesture 3
```

---

## 3. Parameter Contract

The SERA Live2D Character Controller controls standard Cubism parameters:

| Parameter ID | Range | Semantics |
|---|---|---|
| `ParamAngleX` | -30 .. +30 | Head horizontal rotation (yaw) |
| `ParamAngleY` | -30 .. +30 | Head vertical pitch |
| `ParamAngleZ` | -30 .. +30 | Head roll / tilt |
| `ParamBodyAngleX` | -10 .. +10 | Torso horizontal twist |
| `ParamBodyAngleY` | -10 .. +10 | Torso pitch |
| `ParamBodyAngleZ` | -10 .. +10 | Torso lean / roll |
| `ParamEyeBallX` | -1.0 .. +1.0 | Eye gaze horizontal tracking |
| `ParamEyeBallY` | -1.0 .. +1.0 | Eye gaze vertical tracking |
| `ParamEyeLOpen` | 0.0 .. 1.2 | Left eye openness (1 = normal, 0 = closed, 1.2 = wide) |
| `ParamEyeROpen` | 0.0 .. 1.2 | Right eye openness |
| `ParamEyeLSmile` | 0.0 .. 1.0 | Left eye smiling shape |
| `ParamEyeRSmile` | 0.0 .. 1.0 | Right eye smiling shape |
| `ParamBrowLY` | -1.0 .. +1.0 | Left eyebrow height |
| `ParamBrowRY` | -1.0 .. +1.0 | Right eyebrow height |
| `ParamBrowLAngle` | -1.0 .. +1.0 | Left eyebrow angle |
| `ParamBrowRAngle` | -1.0 .. +1.0 | Right eyebrow angle |
| `ParamBreath` | 0.0 .. 1.0 | Continuous breathing chest expansion |
| `ParamA` / `ParamMouthOpenY` | 0.0 .. 1.0 | Lip sync mouth opening driven by TTS speech envelope |
| `ParamCheek` | 0.0 .. 1.0 | Blush intensity |

---

## 4. How to Replace the Character Model

1. Place the new model directory in `presence_desktop/assets/live2d/models/<your_model>/`.
2. Open `presence_desktop/src/live2d/Live2DConfig.js`.
3. Set `ACTIVE_MODEL: "<your_model>"` or specify the `modelPath`.
4. If your model uses non-standard parameter IDs or motion group names, customize them in `Live2DStateProfiles.js`.
5. Restart the presence window. The controller loads the configured model automatically.
