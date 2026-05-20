"""Structural assertions for the GitHub Actions CI workflow.

If the workflow file disappears or stops running the unit/build/integration
jobs the README + docs/SECRETS.md reference, this test fails loudly so the
mismatch is caught in PR review rather than at deploy time.
"""
import os

import pytest
import yaml


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_WORKFLOW = os.path.join(_REPO_ROOT, ".github", "workflows", "test.yml")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(_read(_WORKFLOW))


def test_workflow_file_exists():
    assert os.path.exists(_WORKFLOW), f"missing {_WORKFLOW}"


def test_workflow_runs_on_push_and_pr_to_main(workflow):
    # PyYAML parses `on:` as True (yaml boolean) because of the legacy YAML 1.1
    # spec — handle both keys.
    trig = workflow.get("on") or workflow.get(True)
    assert trig, "workflow must declare triggers"
    push = trig.get("push") or {}
    pr = trig.get("pull_request") or {}
    assert "main" in (push.get("branches") or []), "should run on push to main"
    assert "main" in (pr.get("branches") or []), "should run on PR to main"


def test_workflow_has_backend_and_frontend_jobs(workflow):
    jobs = set(workflow["jobs"].keys())
    assert "backend" in jobs
    assert "frontend" in jobs


def test_backend_job_runs_unit_pytest_excluding_integration(workflow):
    steps = workflow["jobs"]["backend"]["steps"]
    cmds = " ".join(s.get("run", "") for s in steps)
    assert "pytest" in cmds
    assert '-m "not integration"' in cmds or "-m 'not integration'" in cmds


def test_backend_job_installs_requirements(workflow):
    steps = workflow["jobs"]["backend"]["steps"]
    cmds = " ".join(s.get("run", "") for s in steps)
    assert "pip install -r backend/requirements.txt" in cmds


def test_frontend_job_runs_tsc_and_build(workflow):
    steps = workflow["jobs"]["frontend"]["steps"]
    cmds = " ".join(s.get("run", "") for s in steps)
    assert "tsc --noEmit" in cmds
    assert "npm run build" in cmds


def test_frontend_job_enforces_bundle_budget(workflow):
    """Bundle-size budget was a key Phase F deliverable — must stay enforced."""
    steps = workflow["jobs"]["frontend"]["steps"]
    cmds = " ".join(s.get("run", "") for s in steps)
    assert "BUDGET" in cmds.upper()


def test_integration_job_exists_and_is_manual_only(workflow):
    """docs/SECRETS.md promises an integration job — it must exist."""
    jobs = workflow["jobs"]
    assert "integration" in jobs, "docs/SECRETS.md references this job"
    integ = jobs["integration"]
    # Must be gated to workflow_dispatch so PRs don't burn API credits
    cond = integ.get("if", "")
    assert "workflow_dispatch" in cond, (
        "integration job must be manual-trigger only — set "
        "`if: github.event_name == 'workflow_dispatch'`"
    )


def test_integration_job_uses_required_secrets(workflow):
    """The secrets named in docs/SECRETS.md must actually be wired into the
    integration job's env block — otherwise the docs are a lie."""
    steps = workflow["jobs"]["integration"]["steps"]
    env_blob = ""
    for s in steps:
        env = s.get("env") or {}
        env_blob += " ".join(f"{k}={v}" for k, v in env.items())
    for secret in ["OPENROUTER_API_KEY", "GROQ_API_KEY"]:
        assert f"secrets.{secret}" in env_blob, (
            f"integration job must wire ${{{{ secrets.{secret} }}}} per docs/SECRETS.md"
        )


def test_workflow_supports_workflow_dispatch_for_manual_runs(workflow):
    trig = workflow.get("on") or workflow.get(True)
    assert "workflow_dispatch" in trig, (
        "must allow manual triggers from the Actions tab"
    )
