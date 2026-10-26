"""Hermes-installed adapter offline callback registration probe."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

path = Path("/usr/share/projectwright/hermes/projectwright-approvals/__init__.py")
spec = importlib.util.spec_from_file_location("pw_adapter_probe", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
factories = []
module.register(SimpleNamespace(register_telegram_handler=factories.append))
assert len(factories) == 1
handlers = []
factories[0](SimpleNamespace(add_handler=handlers.append), SimpleNamespace())
assert len(handlers) == 1
pattern = handlers[0].pattern
assert pattern.fullmatch("pwa:a:fixture:" + "a"*20)
assert pattern.fullmatch("pwa:r:fixture:" + "b"*20)
assert not pattern.fullmatch("unrelated:callback")
print("PASS: native adapter Telegram callback factory and scoped handler")
