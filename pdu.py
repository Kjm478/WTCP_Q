from enum import Enum, auto
import struct

class PDUType(Enum):
    AUTH_REQUEST = auto()
    AUTH_RESPONSE = auto()
    TELEMETRY_REQUEST = auto()
    CONTROL = auto()
    EMERGENCY = auto()
    TERMINATE = auto()
    
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