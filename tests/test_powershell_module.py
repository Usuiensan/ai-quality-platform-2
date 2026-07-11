from pathlib import Path
import subprocess
import unittest


class PowerShellModuleTests(unittest.TestCase):
    def test_module_imports_and_exports_phase4_commands(self) -> None:
        module = Path("powershell/AiQuality/AiQuality.psd1").resolve()
        script = (
            f"Import-Module '{module}' -Force; "
            "$names = (Get-Command -Module AiQuality).Name | Sort-Object; "
            "$names -join ','"
        )
        result = subprocess.run(
            ["pwsh", "-NoLogo", "-NoProfile", "-Command", script],
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip()
        for name in ["New-AiManagedRepo", "Enable-AiQuality", "Update-AiQuality", "Test-AiQuality", "Get-AiQualityStatus", "Set-AiQualityRuleset"]:
            self.assertIn(name, output)


if __name__ == "__main__":
    unittest.main()
