"""Regression checks for production Stripe bindings."""
from pathlib import Path
import subprocess


def test_cloud_run_environment_keeps_stripe_checkout_settings() -> None:
    environment = Path("deploy/cloud-run.env.yaml.example").read_text(
        encoding="utf-8"
    )

    assert 'STRIPE_BILLING_ENABLED: "true"' in environment
    assert 'STRIPE_EXPECTED_LIVEMODE: "true"' in environment
    for variable in (
        "STRIPE_PRICE_TRIAL_5DAY",
        "STRIPE_PRICE_HOMEWORK_MONTHLY",
        "STRIPE_PRICE_ELEVENPLUS_MONTHLY",
    ):
        assert f'{variable}: "REPLACE_{variable}"' in environment


def test_deploy_script_preserves_and_validates_stripe_secrets() -> None:
    source = Path("deploy/deploy_gcp.sh").read_text(encoding="utf-8")

    assert "homeworkmagic-stripe-secret-key" in source
    assert "homeworkmagic-stripe-webhook-secret" in source
    assert "STRIPE_SECRET_KEY=" in source
    assert "STRIPE_WEBHOOK_SECRET=" in source
    assert "--update-secrets" in source
    assert "--set-secrets" not in source
    assert "/api/billing/plans" in source


def test_deploy_script_requires_encrypted_reward_delivery_secret() -> None:
    source = Path("deploy/deploy_gcp.sh").read_text(encoding="utf-8")
    code_deploy = Path("deploy/deploy_code_gcp.sh").read_text(encoding="utf-8")
    helper = Path("deploy/ensure_reward_delivery_secret.sh").read_text(
        encoding="utf-8"
    )
    guide = Path("deploy/README.md").read_text(encoding="utf-8")

    assert "homeworkmagic-reward-delivery-secret" in source
    assert "REWARD_DELIVERY_SECRET=" in source
    assert "REWARD_DELIVERY_SECRET_SECRET" in source
    assert "ensure_reward_delivery_secret" in source
    assert "ensure_reward_delivery_secret" in code_deploy
    assert (
        "REWARD_DELIVERY_SECRET="
        "${REWARD_DELIVERY_SECRET_SECRET}:latest"
    ) in code_deploy
    assert "secrets.token_urlsafe(48)" in helper
    assert "roles/secretmanager.secretAccessor" in helper
    assert "versions access latest" in helper
    assert "encrypt" in guide.lower()


def test_code_deploy_preflights_and_rebinds_provider_secrets() -> None:
    source = Path("deploy/deploy_code_gcp.sh").read_text(encoding="utf-8")
    guide = Path("deploy/README.md").read_text(encoding="utf-8")

    expected = {
        "DEEPSEEK_API_KEY": (
            "aitutor-deepseek-api-key",
            "DEEPSEEK_API_KEY_SECRET",
            "--deepseek-secret",
        ),
        "SMTP_PASSWORD": (
            "aitutor-smtp-password",
            "SMTP_PASSWORD_SECRET",
            "--smtp-password-secret",
        ),
    }
    for env_name, (secret_name, variable, option) in expected.items():
        assert secret_name in source
        assert variable in source
        assert option in source
        assert f"{env_name}=${{{variable}}}:latest" in source
        assert secret_name in guide
        assert option in guide

    assert "validate_runtime_secret" in source
    assert '--filter="state=ENABLED"' in source
    assert "roles/secretmanager.secretAccessor" in source
    assert source.index('log "Checking required provider') < source.index(
        'log "Building'
    )


def test_code_deploy_is_valid_shell_and_uses_existing_elevenplus_plan() -> None:
    source = Path("deploy/deploy_code_gcp.sh").read_text(encoding="utf-8")
    result = subprocess.run(
        ["bash", "-n", "deploy/deploy_code_gcp.sh"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--mock-price-id" not in source
    assert "STRIPE_PRICE_ELEVENPLUS_MOCK_MONTHLY" not in source


def test_repair_script_updates_only_stripe_configuration() -> None:
    source = Path("deploy/repair_stripe_checkout_gcp.sh").read_text(
        encoding="utf-8"
    )
    commands = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )

    assert "gcloud run services update" in source
    assert "--update-env-vars" in source
    assert "--update-secrets" in source
    assert "--env-vars-file" not in commands
    assert "--set-secrets" not in commands
    assert "STRIPE_PRICE_TRIAL_5DAY" in source
    assert "STRIPE_PRICE_HOMEWORK_MONTHLY" in source
    assert "STRIPE_PRICE_ELEVENPLUS_MONTHLY" in source
    assert "STRIPE_PRICING_TABLE_ID" in source
    assert "STRIPE_PUBLISHABLE_KEY" in source
    assert "price_1Tvl" not in source
