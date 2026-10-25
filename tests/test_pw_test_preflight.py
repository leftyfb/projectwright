"""Safety contract for read-only SSH container preflight."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"preflight-pw-test.py"
spec=importlib.util.spec_from_file_location("pw_test_preflight", SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PreflightTests(unittest.TestCase):
    def test_invocation_is_read_only_and_validated(self):
        calls=[]
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args,0,"user=ubuntu\nhostname=pw-test\nuid=1000\nvirt=lxc\nos=ubuntu\nsystemd=running\n","")
        facts=module.inspect(runner=runner)
        self.assertEqual(facts["virt"],"lxc")
        self.assertEqual(calls[0][0][0],"ssh")
        self.assertEqual(calls[0][0][8],"ubuntu@pw-test")
        self.assertIn("StrictHostKeyChecking=yes",calls[0][0])
        self.assertNotIn("sudo",calls[0][0][-1])
        self.assertNotIn("apt ",calls[0][0][-1])

    def test_noncontainer_or_root_denied(self):
        for response in ("user=ubuntu\nuid=1000\nvirt=none\n","user=root\nuid=0\nvirt=lxc\n"):
            with self.subTest(response=response),self.assertRaises(RuntimeError):
                module.inspect(runner=lambda args, **kwargs:subprocess.CompletedProcess(args,0,response,""))

    def test_other_targets_denied_without_ssh(self):
        with self.assertRaises(ValueError):
            module.inspect("root@tux",runner=lambda *a,**kw:self.fail("SSH invoked"))

if __name__=="__main__":
    unittest.main()
