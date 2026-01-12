import struct

MAGIC_COOKIE = 0xabcddcba # Size of the cookie 4 bytes always
UDP_PORT = 13117 # The client must listen at this port

# Message types
MESSAGE_TYPE_OFFER = 0x2 # Server's offer
MESSAGE_TYPE_REQUEST = 0x3 # Client's request
MESSAGE_TYPE_PAYLOAD = 0x4 # Game Payload

# Packet formats:

# !   - Network byte order 
# I   - Unsigned Int (4 bytes): Magic Cookie
# B   - Unsigned Char (1 byte):  Message Type/Rounds/Result/Card Suit
# H   - Unsigned Short (2 bytes): TCP Port/Card Rank
# 32s - 32 byte string: Team Names 
# 5s  - 5 byte string: Player decisions ("Hit"/"Stand")

# Offer (server to client) messege format:
OFFER_FORMAT = '!IBH32s' # Magic(4), Type(1), Port(2), Name(32)
# Request (client to server) messege format:
REQUEST_FORMAT = '!IBB32s' # Magic(4), Type(1), Rounds(1), Name(32)
# Payload (server to client) message format:
PAYLOAD_SERVER_FORMAT = '!IBBHB' # Magic(4), Type(1), Result(1), Rank(2), Suit(1)
# Payload (client to server) message format:
PAYLOAD_CLIENT_FORMAT = '!IB5s' # Magic(4), Type(1), Decision(5)

# Game constants
RESULT_NOT_OVER = 0x0 # Round is ongoing
RESULT_TIE = 0x1 # Tie
RESULT_LOSS = 0x2 # Loss
RESULT_WIN = 0x3 # Win

SUIT_HEART = 0 # Card suit encoded 0-3
SUIT_DIAMOND = 1
SUIT_CLUB = 2
SUIT_SPADE = 3

# Helper func
def get_card_value(rank):
    # Ace (1) is 11 points
    if rank == 1:
        return 11
    # Face cards (11, 12, 13) are 10 points
    if rank >= 11:
        return 10
    # Number cards (2-10) are their numeric value
    return rank