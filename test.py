# test_pdu.py

import struct
import pytest
from uuid import UUID, uuid4

from pdu import PDU, PDUType

def test_auth_req_roundtrip():
    device_uuid    = uuid4()
    sampling_rate  = 10
    geofence_radius= 5.5

    # Build and serialize
    pdu1 = PDU.build_auth_req(device_uuid, sampling_rate, geofence_radius)
    data = pdu1.to_bytes()

    # Parse header & payload back
    pdu2 = PDU.from_bytes(data)
    assert pdu2.pdu_type    == PDUType.AUTH_REQUEST
    assert pdu2.version      == 1
    # session_id for AUTH_REQ is 0 in our builder
    assert pdu2.session_id   == 0

    # Manually unpack payload
    uuid_bytes = pdu2.payload[:16]
    sr         = int.from_bytes(pdu2.payload[16:20], 'big')
    gr         = struct.unpack('!f', pdu2.payload[20:24])[0]

    assert uuid_bytes == device_uuid.bytes
    assert sr         == sampling_rate
    assert pytest.approx(gr, rel=1e-6) == geofence_radius

def test_auth_resp_parser():
    status     = 0
    session_id = 42
    payload    = struct.pack("!B I", status, session_id)

    # Create a PDU with AUTH_RESP and parse it
    pdu = PDU(PDUType.AUTH_RESPONSE, version=1, session_id=session_id, payload=payload)
    parsed = PDU.parse_auth_resp(pdu.payload)

    assert parsed["status"]      == status
    assert parsed["session_id"]  == session_id

def test_telemetry_roundtrip():
    ts       = 1_625_000_000
    lat, lon = 37.7749, -122.4194
    activity = 2
    battery  = 80
    flags    = 1

    pdu1 = PDU.build_telemetry(ts, lat, lon, activity, battery, flags)
    pdu2 = PDU.from_bytes(pdu1.to_bytes())
    parsed = PDU.parse_telemetry(pdu2.payload)

    assert parsed == {
        "timestamp":  ts,
        "latitude":   pytest.approx(lat, rel=1e-6),
        "longitude":  pytest.approx(lon, rel=1e-6),
        "activity":   activity,
        "battery":    battery,
        "diag_flags": flags,
    }

def test_control_roundtrip():
    new_rate   = 20
    new_radius = 15.75

    pdu1 = PDU.build_control(new_rate, new_radius)
    pdu2 = PDU.from_bytes(pdu1.to_bytes())
    parsed = PDU.parse_control(pdu2.payload)

    assert parsed["sampling_rate"]    == new_rate
    assert pytest.approx(parsed["geofence_radius"], rel=1e-6) == new_radius

def test_emergency_roundtrip():
    ts    = 987_654_321
    code  = 3
    detail= "Test alert"

    pdu1 = PDU.build_emergency(ts, code, detail)
    pdu2 = PDU.from_bytes(pdu1.to_bytes())
    parsed = PDU.parse_emergency(pdu2.payload)

    assert parsed["timestamp"]  == ts
    assert parsed["alert_code"] == code
    assert parsed["details"]    == detail

def test_incomplete_header_raises():
    # fewer bytes than HEADER_SIZE
    with pytest.raises(ValueError):
        PDU.from_bytes(b'\x00\x05\x01')

def test_unknown_type_raises():
    # craft a valid-length header but with type=0xFF
    length = PDU.header_size
    fake_hdr = struct.pack("!H B B I", length, 0xFF, 1, 0)
    with pytest.raises(ValueError):
        PDU.from_bytes(fake_hdr)
