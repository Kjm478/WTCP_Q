from enum import Enum, auto
import struct
from uuid import UUID

class PDUType(Enum):
    AUTH_REQUEST = 0x01
    AUTH_RESPONSE = 0x02
    TELEMETRY_REQUEST = 0x03
    CONTROL = 0x04
    EMERGENCY = 0x05
    SLEEP = 0x06
    WAKE = 0x07
    TERMINATE = 0x08
    
class PDU:
    """
    Represents a single WTCP-Q PDU (Protocol Data Unit).
    -length: uint16 
    -pdu_type : uint8
    -version : uint8
    -session_id : uint32
    payload : bytes
    """
    header_format = '!H B B I' 
    header_size = struct.calcsize(header_format)
    
    def __init__(self, pdu_type: PDUType, version: int, session_id: int, payload: bytes = b""):
        self.pdu_type = pdu_type
        self.version = version
        self.session_id = session_id 
        self.payload = payload
        self.payload = payload or b""
        
    def to_bytes(self) -> bytes:
        """        Serializes the PDU to bytes.
        """
        length = PDU.header_size + len(self.payload)
        header = struct.pack(
            PDU.header_format, length, 
            self.pdu_type.value, self.version, 
            self.session_id)
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes)-> "PDU":
        """ parse bytes into PDU instance. 
        """
        
        if len(data) < PDU.header_size: 
            raise ValueError(f"incomplete header: {len(data)} bytes recieved, {cls.header_size} requred")
       
        length, type_val, version, session_id = struct.unpack(
            cls.header_format, data[:cls.header_size])
        
        if len(data) < length:
            raise ValueError(f"incomplete PDU: {len(data)} bytes received, {length} required")
        
        payload = data[cls.header_size:length]
        
        try: 
            pdu_type = PDUType(type_val)
        except ValueError:
            raise ValueError(f"Unknown PDU type: {type_val}")
        
        return cls(pdu_type, version, session_id, payload)
    
    def __repr__(self):
        return (f"PDU(type={self.pdu_type.name}, version={self.version}, "
                f"session_id={self.session_id}, payload_length={len(self.payload)})")
        
    @staticmethod
    def build_auth_req(device_uuid: UUID, sampling_rate: int, geofence_radius: float) -> "PDU":
        payload = device_uuid.bytes
        payload += struct.pack("!I", sampling_rate)
        payload += struct.pack("!f", geofence_radius)
        return PDU(PDUType.AUTH_REQUEST, version=1, session_id=0, payload=payload)
    
    @staticmethod
    def build_telemetry(session_id: int,timestamp: int, lat: float, lon: float,
                        activity: int, battery: int, diag_flags: int) -> "PDU":
        # timestamp: uint64, lat/lon: float32, activity: uint16, battery: uint8, diag_flags: uint8
        payload = struct.pack("!Q f f H B B",
                              timestamp, lat, lon, activity, battery, diag_flags)
        return PDU(PDUType.TELEMETRY_REQUEST, version=1,session_id= session_id, payload=payload)

    @staticmethod
    def build_control(session_id: int , new_rate: int = None, new_radius: float = None) -> "PDU":
        # CONTROL TLVs
        tlv = b""
        if new_rate is not None:
            tlv += struct.pack("!B B I", 0x01, 4, new_rate)
        if new_radius is not None:
            tlv += struct.pack("!B B f", 0x02, 4, new_radius)
        return PDU(PDUType.CONTROL, version=1, session_id=session_id, payload=tlv)
    
    @staticmethod
    def build_sleep(session_id: int, wake: bool = False) -> "PDU":
        # No payload for sleep
        return PDU(PDUType.SLEEP, version=1, session_id=session_id, payload=struct.pack("!B", 1 if wake else 0))
    
    @staticmethod
    def build_wake(session_id: int) -> "PDU":
        # No payload for wake
        return PDU(PDUType.WAKE, version=1, session_id=session_id)

    @staticmethod
    def build_emergency(session_id:int, timestamp: int, alert_code: int, details: str="") -> "PDU":
        # timestamp: uint64, alert_code: uint8, details: UTF-8 string
        detail_bytes = details.encode("utf-8")
        payload = struct.pack("!Q B B", timestamp, alert_code, len(detail_bytes))
        payload += detail_bytes
        return PDU(PDUType.EMERGENCY, version=1, session_id=session_id, payload=payload)

    @staticmethod
    def parse_auth_resp(payload: bytes):
        # status: uint8, session_id: uint32
        status, session_id = struct.unpack("!B I", payload[:5])
        return {"status": status, "session_id": session_id}

    @staticmethod
    def build_auth_resp(status: int, session_id: int) -> "PDU":
        payload = struct.pack("!B I", status, session_id)  
        return PDU(PDUType.AUTH_RESPONSE, 1, session_id, payload)

    @staticmethod
    def parse_telemetry(payload: bytes):
        ts, lat, lon, act, bat, flags = struct.unpack("!Q f f H B B", payload)
        return {"timestamp": ts, "latitude": lat, "longitude": lon,
                "activity": act, "battery": bat, "diag_flags": flags}

    @staticmethod
    def parse_control(payload: bytes):
        i = 0; result = {}
        while i < len(payload):
            t, l = struct.unpack("!B B", payload[i:i+2]); i += 2
            v = payload[i:i+l]; i += l
            if t == 0x01:
                result["sampling_rate"] = struct.unpack("!I", v)[0]
            elif t == 0x02:
                result["geofence_radius"] = struct.unpack("!f", v)[0]
        return result

    @staticmethod
    def parse_emergency(payload: bytes):
        ts, code, dlen = struct.unpack("!Q B B", payload[:10])
        details = payload[10:10+dlen].decode("utf-8")
        return {"timestamp": ts, "alert_code": code, "details": details}
    
    @staticmethod
    def parse_sleep(payload: bytes):
        if len(payload) != 1:
            raise ValueError("Invalid SLEEP PDU payload length")
        return struct.unpack("!B", payload)[0] == 1  # Returns True for wake, False for sleep