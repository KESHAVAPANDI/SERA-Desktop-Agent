import os
import unittest
import numpy as np

from app.speech.wakeword import (
    LocalCustomWakeWordProvider,
    WakeWordEvaluator,
    WakeWordRegistry,
    WakeWordStatus,
)


class TestPhase5DWakeWordProvider(unittest.TestCase):
    def test_01_default_local_custom_provider_unconfigured(self):
        provider = LocalCustomWakeWordProvider(
            model_path="models/wakeword/nonexistent_model.tflite",
            enabled=False,
        )
        self.assertFalse(provider.initialize())
        self.assertEqual(provider.get_status(), WakeWordStatus.DISABLED)
        self.assertFalse(provider.is_configured)

    def test_02_enabled_without_weights_is_not_configured(self):
        provider = LocalCustomWakeWordProvider(
            model_path="models/wakeword/nonexistent_model.tflite",
            enabled=True,
        )
        self.assertFalse(provider.initialize())
        self.assertEqual(provider.get_status(), WakeWordStatus.NOT_CONFIGURED)
        self.assertEqual(provider.get_status().value, "NOT CONFIGURED")
        self.assertFalse(provider.is_configured)

    def test_03_registry_factory_creates_local_custom(self):
        prov = WakeWordRegistry.create(
            name="local_custom",
            model_path="models/wakeword/hey_sera.tflite",
            enabled=False,
        )
        self.assertIsInstance(prov, LocalCustomWakeWordProvider)
        self.assertEqual(prov.get_status(), WakeWordStatus.DISABLED)

    def test_04_audio_chunk_inference_safe_when_unconfigured(self):
        provider = LocalCustomWakeWordProvider(enabled=False)
        chunk = np.zeros(1280, dtype=np.int16)
        res = provider.process_audio_chunk(chunk)
        self.assertFalse(res.detected)
        self.assertEqual(res.confidence, 0.0)

    def test_05_evaluator_runs_on_stream(self):
        provider = LocalCustomWakeWordProvider(enabled=False)
        evaluator = WakeWordEvaluator(provider)
        stream = np.zeros(16000 * 2, dtype=np.int16)
        results = evaluator.evaluate_stream(stream)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
