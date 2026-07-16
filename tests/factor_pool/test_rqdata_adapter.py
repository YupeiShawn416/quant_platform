import pytest

from factor_pool.data_adapter.rqdata import CredentialMissingError, RQDataAdapter, resolve_credential


class FakeSDK:
    __version__ = "3.5.5-test"

    def __init__(self):
        self.login = None

    def init(self, **kwargs):
        self.login = kwargs

    def get_all_factor_names(self, type=None, market="cn"):
        values = {
            "income_statement": ["revenue", "net_profit"],
            "eod_indicator": ["pe_ratio_ttm"],
            "other": ["legacy_field"],
        }
        return values.get(type, [])


def test_credential_resolution_prefers_primary_environment_name():
    credential = resolve_credential({"RQDATAC_KEY": "primary", "RQDATA_HTTP_TOKEN": "legacy"})
    assert credential.source == "environment:RQDATAC_KEY"
    assert credential.secret == "primary"


def test_missing_credential_fails_without_secret_material():
    with pytest.raises(CredentialMissingError, match="RQDATAC_KEY"):
        resolve_credential({})


def test_adapter_authenticates_and_enumerates_category_records():
    sdk = FakeSDK()
    adapter = RQDataAdapter(sdk=sdk, credential="secret-value", market="cn")

    records = adapter.enumerate_fields(["income_statement", "eod_indicator", "other"])

    assert sdk.login == {"username": "license", "password": "secret-value", "lazy": False}
    assert records == [
        {"vendor_field_name": "revenue", "vendor_category": "income_statement"},
        {"vendor_field_name": "net_profit", "vendor_category": "income_statement"},
        {"vendor_field_name": "pe_ratio_ttm", "vendor_category": "eod_indicator"},
        {"vendor_field_name": "legacy_field", "vendor_category": "other"},
    ]
    assert adapter.capabilities(field_count=4)["authenticated"] is True
    assert "secret-value" not in str(adapter.capabilities(field_count=4))

