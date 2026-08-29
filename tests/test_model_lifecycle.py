import json
import threading
import time
import unittest

from graci.model_lifecycle import ModelLifecycleError, PrimaryModelLifecycle
from graci.provider import LocalLlamaCppProvider
from graci.phase3b import RoutedConfig
from graci.registry import GLM_MODEL_ID, PRIMARY_BASE_URL, QWEN_MODEL_ID


class RouterFixture:
    def __init__(self, *, available=(QWEN_MODEL_ID, GLM_MODEL_ID), loaded=None,
                 fail_load=False, wrong_after_load=False):
        self.available = tuple(available)
        self.loaded = loaded
        self.fail_load = fail_load
        self.wrong_after_load = wrong_after_load
        self.calls = []
        self.active_inference = 0
        self.max_active_inference = 0
        self.guard = threading.Lock()

    def lifecycle(self, request, timeout):
        path = request.full_url.removeprefix("http://127.0.0.1:8080")
        if path == "/v1/models":
            path = "/models"
        self.calls.append((path, json.loads(request.data) if request.data else None))
        if path == "/models/load":
            target = json.loads(request.data)["model"]
            if self.fail_load:
                return 500, b'{}'
            self.loaded = "wrong-model" if self.wrong_after_load else target
            return 200, b'{"success":true}'
        data = [{"id": model, "status": {"value": (
            "loaded" if model == self.loaded else "unloaded")}} for model in self.available]
        return 200, json.dumps({"data": data}).encode()

    def inference(self, request, timeout):
        body = json.loads(request.data)
        with self.guard:
            self.active_inference += 1
            self.max_active_inference = max(self.max_active_inference, self.active_inference)
        time.sleep(0.01)
        with self.guard:
            self.active_inference -= 1
        return 200, json.dumps({"model": body["model"], "choices": [
            {"message": {"content": "{}"}}]}).encode()


def manager(fixture, **kwargs):
    return PrimaryModelLifecycle(PRIMARY_BASE_URL, transport=fixture.lifecycle,
                                 poll_interval_seconds=0.001, **kwargs)


class ModelLifecycleTests(unittest.TestCase):
    def test_qwen_and_glm_already_available(self):
        for model in (QWEN_MODEL_ID, GLM_MODEL_ID):
            fixture = RouterFixture(loaded=model)
            with manager(fixture).lease(model) as ready:
                self.assertEqual((ready.model, ready.status), (model, "loaded"))
            self.assertFalse(any(path == "/models/load" for path, _ in fixture.calls))

    def test_switches_qwen_to_glm_and_glm_to_qwen(self):
        for current, requested in ((QWEN_MODEL_ID, GLM_MODEL_ID),
                                   (GLM_MODEL_ID, QWEN_MODEL_ID)):
            fixture = RouterFixture(loaded=current)
            with manager(fixture).lease(requested):
                self.assertEqual(fixture.loaded, requested)
            loads = [body["model"] for path, body in fixture.calls if path == "/models/load"]
            self.assertEqual(loads, [requested])

    def test_requested_model_must_be_reported_and_loaded(self):
        fixture = RouterFixture(available=(QWEN_MODEL_ID,), loaded=QWEN_MODEL_ID)
        with self.assertRaisesRegex(ModelLifecycleError, "does not expose router status"):
            with manager(fixture).lease(GLM_MODEL_ID):
                pass

        wrong = RouterFixture(loaded=QWEN_MODEL_ID, wrong_after_load=True)
        clock = iter((0.0, 0.0, 2.0))
        with self.assertRaisesRegex(ModelLifecycleError, "timed out"):
            with manager(wrong, timeout_seconds=1.0, monotonic=lambda: next(clock),
                         sleep=lambda seconds: None).lease(GLM_MODEL_ID):
                pass

    def test_launcher_failure_and_timeout_fail_closed(self):
        failed = RouterFixture(loaded=QWEN_MODEL_ID, fail_load=True)
        with self.assertRaisesRegex(ModelLifecycleError, "HTTP status 500"):
            with manager(failed).lease(GLM_MODEL_ID):
                pass

        class Loading(RouterFixture):
            def lifecycle(self, request, timeout):
                path = request.full_url.removeprefix("http://127.0.0.1:8080")
                if path == "/v1/models":
                    path = "/models"
                if path == "/models/load":
                    return 200, b'{"success":true}'
                data = [{"id": model, "status": {"value": "loading"}}
                        for model in self.available]
                return 200, json.dumps({"data": data}).encode()
        clock = iter((0.0, 0.0, 2.0))
        with self.assertRaisesRegex(ModelLifecycleError, "timed out"):
            with manager(Loading(), timeout_seconds=1.0, monotonic=lambda: next(clock),
                         sleep=lambda seconds: None).lease(QWEN_MODEL_ID):
                pass

    def test_switch_and_inference_share_one_race_protected_lease(self):
        fixture = RouterFixture(loaded=QWEN_MODEL_ID)
        lifecycle = manager(fixture)
        providers = [LocalLlamaCppProvider(
            RoutedConfig(PRIMARY_BASE_URL, model, "local-llama-cpp", "3090", None),
            transport=fixture.inference, model_lifecycle=lifecycle)
            for model in (GLM_MODEL_ID, QWEN_MODEL_ID)]
        barrier = threading.Barrier(3)
        errors = []
        def run(provider):
            try:
                barrier.wait()
                provider.review({"bounded": True})
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)
        threads = [threading.Thread(target=run, args=(provider,)) for provider in providers]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(fixture.max_active_inference, 1)
        self.assertFalse(any("192.168.0.101" in path for path, _ in fixture.calls))

    def test_unapproved_model_fails_before_contact(self):
        fixture = RouterFixture()
        with self.assertRaisesRegex(ModelLifecycleError, "unapproved"):
            with manager(fixture).lease("other"):
                pass
        self.assertEqual(fixture.calls, [])


if __name__ == "__main__":
    unittest.main()
