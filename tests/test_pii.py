"""pii.mask to CONTRACT.md section 5: {text, entities}, placeholders EMAIL PHONE IP IBAN CARD ACCOUNT."""
import time

import pytest

from sentineldesk import pii


def m(text):
    return pii.mask(text)["text"]


def types(text):
    return [e["type"] for e in pii.mask(text)["entities"]]


def test_contract_shape():
    out = pii.mask("Mail me at jane.doe@example.com")
    assert set(out) == {"text", "entities"}
    assert out["text"] == "Mail me at [EMAIL]"
    assert out["entities"] == [{"type": "EMAIL", "start": 11, "end": 31}]


def test_offsets_point_into_the_original_text():
    text = "ip 10.0.12.5 and mail a@b.io"
    for e in pii.mask(text)["entities"]:
        assert text[e["start"]:e["end"]] in ("10.0.12.5", "a@b.io")


def test_original_values_never_in_output():
    text = "john.doe@example.com +1 617 555 0199 192.168.10.45 DE89370400440532013000"
    out = pii.mask(text)
    for secret in ("john.doe", "617 555", "192.168", "DE8937"):
        assert secret not in out["text"] and secret not in str(out["entities"])


def test_each_entity_type():
    assert types("a@b.io") == ["EMAIL"]
    assert types("host 10.0.12.5 is down") == ["IP"]
    assert types("addr 2001:db8::1 unreachable") == ["IP"]
    assert types("pay to DE89 3704 0044 0532 0130 00 please") == ["IBAN"]
    assert types("card 4111 1111 1111 1111 expired") == ["CARD"]
    assert types("call +49 170 1234567") == ["PHONE"]
    assert types("my account number 12345678 is locked") == ["ACCOUNT"]
    assert types("Kundennummer: 98765432") == ["ACCOUNT"]


def test_placeholders_are_exact():
    assert m("a@b.io") == "[EMAIL]" and m("10.0.12.5") == "[IP]" and m("4111 1111 1111 1111") == "[CARD]"
    assert m("DE89 3704 0044 0532 0130 00") == "[IBAN]" and m("+49 170 1234567") == "[PHONE]"


def test_phone_formats():
    assert m("call (555) 123-4567 today") == "call [PHONE] today"
    assert m("tel 0170 1234567.") == "tel [PHONE]."


def test_iban_is_not_also_a_phone_and_card_is_not_a_phone():
    assert types("DE89370400440532013000") == ["IBAN"]
    assert types("4111111111111111") == ["CARD"]


def test_non_luhn_digit_runs_are_not_cards():
    assert "CARD" not in types("ref 1234 5678 9012 3456")


def test_things_that_must_not_be_masked():
    for s in ("on 2024-01-15 order 12345 failed", "meeting at 10:30:45 today", "version 1.2.3.999",
              "The printer on floor 3 does not respond.", "error code 500 after 2 retries"):
        assert m(s) == s


def test_dataset_tokens_map_to_placeholders():
    assert m("Hi <name>, call <tel_num> about <acc_num>") == "Hi [NAME], call [PHONE] about [ACCOUNT]"


def test_multiple_entities_in_order():
    out = pii.mask("a@b.io then 10.0.0.1 then +49 170 1234567")
    assert [e["type"] for e in out["entities"]] == ["EMAIL", "IP", "PHONE"]
    assert out["text"] == "[EMAIL] then [IP] then [PHONE]"


def test_adjacent_numbers_are_each_masked():
    # a greedy phone pattern must not swallow its neighbours, or the phone number leaks
    assert m("+1 617 555 0199 192.168.10.45") == "[PHONE] [IP]"
    assert m("a@b.io +49 170 1234567") == "[EMAIL] [PHONE]"
    assert m("+49 170 1234567 +49 171 7654321") == "[PHONE] [PHONE]"
    assert m("DE89370400440532013000 +49 170 1234567") == "[IBAN] [PHONE]"


def test_phone_does_not_span_lines():
    assert m("ref 1234567890\n0987654321") == "ref [PHONE]\n[PHONE]"  # two numbers, one per line
    assert m("ref 12345678\n87654321") == "ref 12345678\n87654321"      # 8 digits each: too short to be phones


def test_none_empty_and_unicode_do_not_crash():
    assert pii.mask(None) == {"text": "", "entities": []}
    assert pii.mask("") == {"text": "", "entities": []}
    assert pii.mask("Größe überprüfen – déjà vu")["entities"] == []


def test_idempotent():
    once = m("a@b.io and 10.0.0.1")
    assert m(once) == once


def test_fast_enough_for_the_10ms_target():
    text = ("Hello team, our VPN has been down since 07:30. My email is john.doe@example.com and my phone is "
            "+1 617 555 0199. The laptop at 192.168.10.45 cannot sync. " * 4)
    pii.mask(text)  # warm up
    t0 = time.perf_counter()
    for _ in range(50):
        pii.mask(text)
    assert (time.perf_counter() - t0) / 50 * 1000 < 10
