from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _extract_powershell_string_array(script, variable_name):
    match = re.search(
        rf"\${re.escape(variable_name)}\s*=\s*@\((.*?)\)",
        script,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"Missing PowerShell array: ${variable_name}")
    return re.findall(r'"([^"]+)"', match.group(1))


class PackagingStaticTest(unittest.TestCase):
    def test_pyinstaller_spec_includes_required_assets(self):
        spec = (ROOT / "YDManager.spec").read_text(encoding="utf-8")

        self.assertIn('("assets/icon.ico", "assets")', spec)
        self.assertIn('("assets/fonts", "assets/fonts")', spec)
        self.assertIn('collect_data_files("qtawesome")', spec)
        self.assertIn('icon="assets/icon.ico"', spec)
        self.assertNotIn('("assets", "assets")', spec)

    def test_pyinstaller_spec_excludes_installer_only_assets_and_upx(self):
        spec = (ROOT / "YDManager.spec").read_text(encoding="utf-8")

        self.assertNotIn("installer_sidebar.bmp", spec)
        self.assertNotIn("installer_header.bmp", spec)
        self.assertNotIn("upx=True", spec)
        self.assertGreaterEqual(spec.count("upx=False"), 2)

    def test_pyinstaller_spec_keeps_runtime_hidden_imports(self):
        spec = (ROOT / "YDManager.spec").read_text(encoding="utf-8")

        self.assertIn('"BlurWindow.blurWindow"', spec)
        self.assertIn('"send2trash"', spec)

    def test_inno_setup_installs_pyinstaller_output(self):
        setup = (ROOT / "setup.iss").read_text(encoding="utf-8")

        self.assertIn('AppVersion={#MyAppVersion}', setup)
        self.assertIn('Source: "dist\\YDManager\\*"', setup)
        self.assertIn('OutputBaseFilename=YDManager_Setup_v{#MyAppVersion}', setup)

    def test_inno_setup_references_existing_installer_assets(self):
        setup = (ROOT / "setup.iss").read_text(encoding="utf-8")

        expected_assets = {
            "SetupIconFile": "assets\\icon.ico",
            "WizardImageFile": "assets\\installer_sidebar.bmp",
            "WizardSmallImageFile": "assets\\installer_header.bmp",
        }
        for directive, relative_path in expected_assets.items():
            with self.subTest(directive=directive):
                self.assertIn(f"{directive}={relative_path}", setup)
                self.assertTrue((ROOT / relative_path).is_file())

    def test_inno_setup_preserves_recursive_package_install_flags(self):
        setup = (ROOT / "setup.iss").read_text(encoding="utf-8")

        self.assertRegex(
            setup,
            re.compile(
                r'^Source: "dist\\YDManager\\\*"; DestDir: "\{app\}"; '
                r"Flags: (?=.*ignoreversion)(?=.*recursesubdirs)(?=.*createallsubdirs).*$",
                re.MULTILINE,
            ),
        )

    def test_inno_setup_uses_stable_guid_app_id(self):
        setup = (ROOT / "setup.iss").read_text(encoding="utf-8")

        self.assertRegex(
            setup,
            re.compile(
                r"^AppId=\{\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-"
                r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$",
                re.MULTILINE,
            ),
        )

    def test_build_guide_documents_verified_build_command(self):
        build_doc = (ROOT / "BUILD.md").read_text(encoding="utf-8")

        self.assertIn("YDManager.spec", build_doc)
        self.assertIn("dist\\YDManager\\YDManager.exe", build_doc)
        self.assertIn(".\\tools\\package_smoke.ps1", build_doc)
        self.assertIn(".\\tools\\build_installer.ps1", build_doc)
        self.assertIn("--workpath", build_doc)
        self.assertIn("$ExePath", build_doc)
        self.assertNotIn(str(ROOT), build_doc)
        self.assertNotIn(str(ROOT).replace("\\", "\\\\"), build_doc)

    def test_build_guide_uses_setup_version_placeholder_for_installer_output(self):
        build_doc = (ROOT / "BUILD.md").read_text(encoding="utf-8")

        self.assertIn("installer\\YDManager_Setup_v<version-from-setup.iss>.exe", build_doc)
        self.assertNotIn("installer\\YDManager_Setup_v8.1.exe", build_doc)

    def test_package_smoke_script_uses_lock_and_isolated_pyinstaller_paths(self):
        script = (ROOT / "tools" / "package_smoke.ps1").read_text(encoding="utf-8")

        self.assertIn("requirements-lock.txt", script)
        self.assertIn("--workpath", script)
        self.assertIn("--distpath", script)
        self.assertIn("YDManager.spec", script)
        self.assertIn("Start-Process", script)
        self.assertIn("PACKAGE_SMOKE_OK", script)

    def test_python_version_preflight_is_wired_into_release_checks(self):
        preflight_path = ROOT / "tools" / "check_python_version.py"
        self.assertTrue(preflight_path.exists())

        preflight = preflight_path.read_text(encoding="utf-8")
        run_checks = (ROOT / "tools" / "run_checks.ps1").read_text(encoding="utf-8")
        package_smoke = (ROOT / "tools" / "package_smoke.ps1").read_text(encoding="utf-8")
        build_doc = (ROOT / "BUILD.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("SUPPORTED_MAJOR_MINOR = (3, 10)", preflight)
        self.assertIn("check_python_version.py", run_checks)
        self.assertIn("check_python_version.py", package_smoke)
        self.assertIn("Python 3.10.x", build_doc)
        self.assertIn("Python 3.10.x", readme)

    def test_release_audit_is_wired_into_local_checks(self):
        audit_path = ROOT / "tools" / "release_audit.py"
        self.assertTrue(audit_path.exists())

        audit = audit_path.read_text(encoding="utf-8")
        run_checks = (ROOT / "tools" / "run_checks.ps1").read_text(encoding="utf-8")
        report = (ROOT / "docs" / "maintenance" / "stabilization-report-2026-06-12.md").read_text(encoding="utf-8")
        plan = (ROOT / "docs" / "superpowers" / "plans" / "2026-06-12-project-stabilization-master-plan.md").read_text(encoding="utf-8")

        self.assertIn("RELEASE_AUDIT_OK", audit)
        self.assertIn("git", audit)
        self.assertIn("ls-files", audit)
        self.assertIn("forbidden_generated_roots", audit)
        self.assertIn("forbidden_text_patterns", audit)
        self.assertIn("release_audit.py", run_checks)
        self.assertIn("Release audit", report)
        self.assertIn("release audit", plan.lower())

    def test_package_smoke_allows_successful_native_stderr(self):
        script = (ROOT / "tools" / "package_smoke.ps1").read_text(encoding="utf-8")

        self.assertIn("$PreviousErrorActionPreference", script)
        self.assertIn("Verbose native tools can write progress to stderr", script)
        self.assertIn("function Invoke-NativeCommand", script)
        self.assertIn("Get-Command $FilePath -ErrorAction Stop", script)
        self.assertIn('$ErrorActionPreference = "Continue"', script)
        self.assertNotIn("& $Block *>> $Log", script)
        self.assertRegex(script, re.compile(r"\$ErrorActionPreference = \$PreviousErrorActionPreference"))

    def test_package_smoke_verifies_packaged_assets_and_qt_plugins(self):
        script = (ROOT / "tools" / "package_smoke.ps1").read_text(encoding="utf-8")

        self.assertIn("function Test-RequiredPackagedPath", script)
        self.assertIn('Invoke-Step "packaged-assets"', script)
        self.assertIn("_internal\\assets\\icon.ico", script)
        self.assertIn("_internal\\assets\\fonts\\Pretendard-Medium.ttf", script)
        self.assertIn("_internal\\assets\\fonts\\Pretendard-Bold.ttf", script)
        self.assertIn("_internal\\qtawesome", script)
        self.assertIn("_internal\\PyQt6\\Qt6\\plugins\\platforms", script)
        self.assertIn("_internal\\PyQt6\\Qt6\\plugins\\multimedia", script)
        self.assertIn("Test-ForbiddenPackagedPath", script)
        self.assertIn("_internal\\assets\\installer_sidebar.bmp", script)
        self.assertIn("_internal\\assets\\installer_header.bmp", script)

    def test_package_smoke_preserves_temp_root_on_failure(self):
        script = (ROOT / "tools" / "package_smoke.ps1").read_text(encoding="utf-8")

        self.assertIn("$PackageSmokeSucceeded = $false", script)
        self.assertIn("$PackageSmokeSucceeded = $true", script)
        self.assertIn("Preserving failed package smoke temp output", script)
        self.assertRegex(script, re.compile(r"if \(\$PackageSmokeSucceeded\) \{\s*Remove-TempRootSafely \$TempRoot\s*\}", re.DOTALL))

    def test_installer_build_script_does_not_point_to_temp_smoke_output(self):
        script = (ROOT / "tools" / "build_installer.ps1").read_text(encoding="utf-8")

        self.assertNotIn("Run .\\tools\\package_smoke.ps1", script)
        self.assertIn("Run a local PyInstaller build that writes to .\\dist", script)

    def test_installer_build_script_detects_inno_compiler(self):
        script = (ROOT / "tools" / "build_installer.ps1").read_text(encoding="utf-8")

        self.assertIn("ISCC.exe", script)
        self.assertIn("setup.iss", script)
        self.assertIn("INSTALLER_BUILD_OK path=$ExpectedInstallerDisplay", script)
        self.assertIn("INNO_SETUP_NOT_FOUND", script)

    def test_installer_build_script_derives_expected_filename_from_setup_version(self):
        script = (ROOT / "tools" / "build_installer.ps1").read_text(encoding="utf-8")

        self.assertIn("function Get-InnoAppVersion", script)
        self.assertIn('$AppVersion = Get-InnoAppVersion $SetupScript', script)
        self.assertIn('"installer\\YDManager_Setup_v$AppVersion.exe"', script)
        self.assertNotIn('$ExpectedInstaller = Join-Path $Root "installer\\YDManager_Setup_v8.1.exe"', script)

    def test_installer_build_script_validates_packaged_runtime_tree(self):
        script = (ROOT / "tools" / "build_installer.ps1").read_text(encoding="utf-8")

        self.assertIn("function Test-PackagePreflight", script)
        self.assertIn("function Test-RequiredPackagedPath", script)
        self.assertIn("function Test-ForbiddenPackagedPath", script)
        self.assertIn('Test-PackagePreflight $PackageRoot', script)
        self.assertIn('_internal\\assets\\icon.ico', script)
        self.assertIn('_internal\\assets\\fonts\\Pretendard-Medium.ttf', script)
        self.assertIn('_internal\\PyQt6\\Qt6\\plugins\\platforms', script)
        self.assertIn('_internal\\PyQt6\\Qt6\\plugins\\multimedia', script)
        self.assertIn('_internal\\assets\\installer_sidebar.bmp', script)
        self.assertIn('_internal\\assets\\installer_header.bmp', script)

    def test_packaged_runtime_preflight_lists_stay_aligned(self):
        package_smoke = (ROOT / "tools" / "package_smoke.ps1").read_text(encoding="utf-8")
        build_installer = (ROOT / "tools" / "build_installer.ps1").read_text(encoding="utf-8")

        self.assertEqual(
            _extract_powershell_string_array(package_smoke, "requiredPaths"),
            _extract_powershell_string_array(build_installer, "requiredPaths"),
        )
        self.assertEqual(
            _extract_powershell_string_array(package_smoke, "forbiddenPaths"),
            _extract_powershell_string_array(build_installer, "forbiddenPaths"),
        )

    def test_release_version_strings_stay_aligned(self):
        consts = (ROOT / "src" / "core" / "consts.py").read_text(encoding="utf-8")
        setup = (ROOT / "setup.iss").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        app_version = re.search(r'^APP_VERSION = "([^"]+)"$', consts, re.MULTILINE).group(1)
        setup_version = re.search(r'^#define MyAppVersion "([^"]+)"$', setup, re.MULTILINE).group(1)

        self.assertEqual(app_version, setup_version)
        self.assertIn(f"Version-{app_version}-", readme)
        self.assertIn(f"YDManager_Setup_v{app_version}.exe", readme)

    def test_requirements_are_pinned_for_reproducible_builds(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        package_lines = [
            line.strip() for line in requirements
            if line.strip() and not line.strip().startswith("#")
        ]

        self.assertGreater(len(package_lines), 0)
        for line in package_lines:
            self.assertIn("==", line)
            self.assertNotIn(">=", line)
            self.assertNotIn("<=", line)

    def test_runtime_and_build_requirements_are_split(self):
        runtime_lines = {
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        build_path = ROOT / "requirements-build.txt"
        self.assertTrue(build_path.exists())
        build_lines = {
            line.strip()
            for line in build_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

        self.assertIn("PyQt6==6.11.0", runtime_lines)
        self.assertIn("qtawesome==1.4.2", runtime_lines)
        self.assertIn("BlurWindow==1.2.1", runtime_lines)
        self.assertIn("send2trash==2.1.0", runtime_lines)
        self.assertNotIn("pyinstaller==6.20.0", runtime_lines)
        self.assertEqual({"pyinstaller==6.20.0"}, build_lines)

    def test_release_lock_file_pins_transitive_dependencies(self):
        lock_path = ROOT / "requirements-lock.txt"
        self.assertTrue(lock_path.exists())

        lock_lines = [
            line.strip()
            for line in lock_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        self.assertIn("PyQt6-Qt6==6.11.1", lock_lines)
        self.assertIn("qtawesome==1.4.2", lock_lines)
        self.assertIn("pyinstaller-hooks-contrib==2026.6", lock_lines)
        for line in lock_lines:
            self.assertIn("==", line)

    def test_release_lock_includes_every_direct_requirement_pin(self):
        requirements = set()
        for requirement_file in ("requirements.txt", "requirements-build.txt"):
            requirements.update(
                line.strip()
                for line in (ROOT / requirement_file).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            )
        lock_lines = {
            line.strip()
            for line in (ROOT / "requirements-lock.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

        self.assertTrue(requirements)
        self.assertTrue(requirements.issubset(lock_lines))

    def test_readme_download_badge_matches_current_release_name(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertNotIn("YDManager_v1.0.0.exe", readme)
        self.assertIn("YDManager_Setup_v8.1.exe", readme)

    def test_stabilization_docs_record_current_automated_count(self):
        expected = unittest.defaultTestLoader.discover(str(ROOT / "tests")).countTestCases()
        report = (ROOT / "docs" / "maintenance" / "stabilization-report-2026-06-12.md").read_text(encoding="utf-8")
        plan = (ROOT / "docs" / "superpowers" / "plans" / "2026-06-12-project-stabilization-master-plan.md").read_text(encoding="utf-8")

        self.assertIn(f"{expected} unittest cases passed", report)
        self.assertIn(f"{expected} unittests pass", plan)
        self.assertNotIn("55 unittest", report)
        self.assertNotIn("55 unittest", plan)

    def test_github_actions_ci_runs_the_project_check_script(self):
        workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow_path.exists())

        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn("windows-latest", workflow)
        self.assertIn("actions/setup-python", workflow)
        self.assertIn("requirements.txt", workflow)
        self.assertIn("tools\\run_checks.ps1", workflow)
        self.assertIn("tools\\smoke_video_workflow.py", workflow)


if __name__ == "__main__":
    unittest.main()
