"""Regression checks for production Stripe bindings."""
from pathlib import Path


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
