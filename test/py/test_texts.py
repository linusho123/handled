"""The live texts senders, against a recorded stand-in for the network (no test reaches
Photon or Twilio): the keys present choose the sender; Photon replies into the user's
own conversation or falls through; nothing logs a key or a header."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from app.desk.texts import ChainTexts, LoggedTexts, PhotonTexts, TwilioTexts, texts_from_env

KEY = "pho_sk_test_secret_value"
PROJECT = "pho_prj_00000000000000000000000000"
SPACE = "pho_spc_00000000000000000000000001"
LINE = "pho_usr_00000000000000000000000002"
HUMAN = "pho_usr_00000000000000000000000003"


def _inbound(space=SPACE, line=LINE, line_handle="+13105550100"):
    return {
        "id": "pho_msg_00000000000000000000000004",
        "platform": "imessage",
        "space": {"id": space, "platform": "imessage"},
        "receivedBy": {"id": line, "handle": line_handle, "platform": "imessage"},
        "sentBy": {"id": HUMAN, "handle": "+13105550199", "platform": "imessage"},
        "content": {"type": "text", "format": "plain", "text": "hi"},
    }


class Net:
    """Records every request a sender makes and answers from a script."""

    def __init__(self, listing=None, list_status=200, send_status=202):
        self.calls = []
        self.listing = listing if listing is not None else []
        self.list_status = list_status
        self.send_status = send_status

    def __call__(self, method, url, headers, body):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        if method == "GET":
            return self.list_status, json.dumps({"items": self.listing}).encode()
        return self.send_status, b"{}"


class Log(list):
    def __call__(self, line):
        self.append(line)


def test_the_keys_present_choose_the_senders():
    net, log = Net(), Log()
    both = texts_from_env(
        {"PHOTON_API_KEY": KEY, "PHOTON_PROJECT_ID": PROJECT, "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "t", "TWILIO_FROM": "+1", "TWILIO_TO": "+2"},
        http=net,
        log=log,
    )
    assert [type(s) for s in both.senders] == [PhotonTexts, TwilioTexts]
    assert [type(s) for s in texts_from_env({"PHOTON_API_KEY": KEY}, http=net, log=log).senders] == []
    assert [type(s) for s in texts_from_env({"TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "t", "TWILIO_FROM": "+1"}, http=net, log=log).senders] == []
    none = texts_from_env({}, http=net, log=log)
    assert none.senders == [] and isinstance(none.fallback, LoggedTexts)
    assert none.send("Paid citation 4512087733. Due Nov 2, 2026.", "2026-10-17T00:00:00", "k")
    assert net.calls == [] and any("Paid citation 4512087733" in line for line in log)


def test_photon_replies_into_the_users_conversation_with_a_stable_key():
    net, log = Net(listing=[_inbound()]), Log()
    photon = PhotonTexts(KEY, PROJECT, http=net, log=log)
    assert photon.send("Ready to pay citation 4512087733, waiting for you. Due Nov 2, 2026.", "2026-10-17T00:00:00", "key-1")
    listing, send = net.calls
    parts = urlsplit(listing["url"])
    assert listing["method"] == "GET" and parts.netloc == "api.photon.codes" and parts.path == f"/v1/projects/{PROJECT}/messages"
    query = parse_qs(parts.query)
    assert query["direction"] == ["received"] and query["platform"] == ["imessage"]
    assert listing["headers"]["Authorization"] == f"Bearer {KEY}"
    assert send["method"] == "POST" and urlsplit(send["url"]).path == f"/v1/projects/{PROJECT}/messages"
    assert send["headers"]["idempotency-key"] == "key-1"
    assert json.loads(send["body"]) == {
        "spaceId": SPACE,
        "senderId": LINE,
        "content": {"type": "text", "format": "plain", "text": "Ready to pay citation 4512087733, waiting for you. Due Nov 2, 2026."},
    }
    # The conversation is kept: the next text goes straight into it.
    assert photon.send("Paid citation 4512087733. Due Nov 2, 2026.", "2026-10-17T00:01:00", "key-2")
    assert [c["method"] for c in net.calls] == ["GET", "POST", "POST"]
    assert net.calls[2]["headers"]["idempotency-key"] == "key-2"


def test_photon_picks_the_shared_line_it_was_given():
    other = _inbound(space="pho_spc_00000000000000000000000009", line="pho_usr_00000000000000000000000009", line_handle="+13105550111")
    net = Net(listing=[other, _inbound()])
    photon = PhotonTexts(KEY, PROJECT, agent_handle="+13105550100", http=net, log=Log())
    assert photon.send("hello", "2026-10-17T00:00:00", "k")
    assert json.loads(net.calls[-1]["body"])["spaceId"] == SPACE


@pytest.mark.parametrize("listing, status", [([], 200), ([{"space": {}, "receivedBy": {"id": LINE}}], 200), ([_inbound()], 401)])
def test_photon_with_no_handshake_logs_it_and_the_text_falls_through(listing, status):
    net, log = Net(listing=listing, list_status=status), Log()
    twilio_net = Net()
    chain = ChainTexts([PhotonTexts(KEY, PROJECT, http=net, log=log), TwilioTexts("AC1", "tok", "+15550001", "+15550002", http=twilio_net, log=log)], LoggedTexts(log), log)
    assert chain.send("Paid citation 4512087733. Due Nov 2, 2026.", "2026-10-17T00:00:00", "k")
    assert [c["method"] for c in net.calls] == ["GET"]  # nothing was sent through Photon
    assert any("handshake is missing" in line for line in log)
    (twilio,) = twilio_net.calls
    assert urlsplit(twilio["url"]).path == "/2010-04-01/Accounts/AC1/Messages.json"
    assert parse_qs(twilio["body"].decode()) == {"From": ["+15550001"], "To": ["+15550002"], "Body": ["Paid citation 4512087733. Due Nov 2, 2026."]}


def test_a_refused_send_falls_through_to_the_log():
    log = Log()
    chain = ChainTexts([PhotonTexts(KEY, PROJECT, http=Net(listing=[_inbound()], send_status=500), log=log)], LoggedTexts(log), log)
    assert chain.send("Paid citation 4512087733. Due Nov 2, 2026.", "2026-10-17T00:00:00", "k")
    assert any("not sent" in line and "Paid citation 4512087733" in line for line in log)


def test_no_sender_logs_a_key_or_a_header():
    log = Log()
    chain = texts_from_env(
        {"PHOTON_API_KEY": KEY, "PHOTON_PROJECT_ID": PROJECT, "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "twilio_secret_token", "TWILIO_FROM": "+1", "TWILIO_TO": "+2"},
        http=Net(listing=[], send_status=401),
        log=log,
    )
    chain.prepare()
    chain.send("hello", "2026-10-17T00:00:00", "k")
    text = "\n".join(log)
    assert log and KEY not in text and "twilio_secret_token" not in text and "Bearer" not in text and "Basic" not in text
