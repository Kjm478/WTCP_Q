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