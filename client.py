import socket
import struct
import utils 
import select

class BlackjackClient:
    def __init__(self, team_name):
        self.team_name = team_name
        self.udp_port = utils.UDP_PORT # Set to 13122 

    def start(self):
        """The main loop for the client"""
        # Step 3 in Example: Ask for rounds first
        try:
            self.rounds = int(input("How many rounds would you like to play? "))
        except ValueError:
            print("Invalid input, defaulting to 1 round.")
            self.rounds = 1

        print("Client started, listening for offer requests...")
        
        while True:
            # Listening for UDP Offer
            server_ip, server_tcp_port, server_name = self.listen_for_offer()
            # PDF Example: "Received offer from 172.1.0.4"
            print(f"Received offer from {server_ip}")

            # Connecting with TCP and Play
            self.play_game(server_ip, server_tcp_port, self.rounds)


    def listen_for_offer(self):
        """Listens on UDP port 13122 for a server"""
        # Creating UDP socket
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allowing more than one client on the same computer to listen to the same port
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        
        # Bind to the broadcast port
        udp_socket.bind(('', self.udp_port))

        while True:
            # Wait for a packet, we set the max buffer size to 1024
            data, addr = udp_socket.recvfrom(1024) # data is the offer, addr is (ip, port)
            
            try:
                # Unpacking offer:
                cookie, msg_type, tcp_port, raw_name = struct.unpack(utils.OFFER_FORMAT, data)

                # Checking if the offer is valid:
                if cookie == utils.MAGIC_COOKIE and msg_type == utils.MESSAGE_TYPE_OFFER:
                    server_name = raw_name.decode('utf-8').strip('\x00')
                    udp_socket.close() # Close UDP once we find a server
                    return addr[0], tcp_port, server_name
            except Exception:
                # If packet is corrupted, just keep listening
                continue


    def play_game(self, server_ip, server_port, rounds):
        """Connects to the server and handles the Requests and Payloads"""
        try:
            # Open a TCP connection
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((server_ip, server_port))

            # Getting rounds from player - Argument passed now.
            wins = 0 # Track wins for statistics

            # Packing a request and sending to server ( Magic(4), Type(1), Rounds(1), Name(32))
            padded_name = self.team_name.encode('utf-8')[:32].ljust(32, b'\x00')
            request_packet = struct.pack(utils.REQUEST_FORMAT, utils.MAGIC_COOKIE, utils.MESSAGE_TYPE_REQUEST, rounds, padded_name)
            tcp_socket.send(request_packet)

            # Payload - getting cards for each round
            for i in range(rounds):
                print(f"\n--- Starting Round {i+1} ---")
                playing_round = True
                player_points = 0
                
                while playing_round:
                    # Getting card from server
                    data = tcp_socket.recv(9)
                    if not data: break
                    
                    cookie, msg_type, result, rank, suit = struct.unpack(utils.PAYLOAD_SERVER_FORMAT, data)
                    
                    if msg_type == utils.MESSAGE_TYPE_PAYLOAD:
                        # Check if the game is over based on the result byte
                        if result != utils.RESULT_NOT_OVER:
                            outcomes = {utils.RESULT_WIN: "YOU WIN!!!", 
                                       utils.RESULT_LOSS: "YOU LOSE :(", 
                                       utils.RESULT_TIE: "IT'S A TIE..."}
                            print(f"Round Over: {outcomes.get(result, 'Unknown Result')}")
                            # Increment win counter if applicable
                            if result == utils.RESULT_WIN:
                                wins += 1
                            playing_round = False
                            break
                        
                        card_val = utils.get_card_value(rank)
                        player_points += card_val
                        suit_names = ["Hearts", "Diamonds", "Clubs", "Spades"]
                        suit_str = suit_names[suit] if 0 <= suit <= 3 else str(suit)
                        print(f"Dealt: Rank {rank} (Points: {card_val}), Suit {suit_str}. Total: {player_points}")

                        # NON-BLOCKING CHECK:
                        # If the server sent multiple cards (e.g. Initial deal of 2),
                        # we want to process the next card without blocking on input.
                        readable, _, _ = select.select([tcp_socket], [], [], 0.05)
                        if readable:
                            continue

                        # Getting user input
                        try:
                            choice = input("Your move (Hittt/Stand): ").capitalize()
                            # Capitalize makes "hittt" -> "Hittt"
                        except EOFError:
                           choice = "Stand"
                           
                        if choice not in ["Hittt", "Stand"]:
                            print("Invalid choice, defaulting to Stand.")
                            choice = "Stand" # Default safety

                        # Pack and send Decision- !IB5s (Magic, Type, 5-byte string)
                        # Both "Hittt" and "Stand" are exactly 5 bytes, no padding needed if correct
                        decision_bytes = choice.encode('utf-8')
                        decision_packet = struct.pack(utils.PAYLOAD_CLIENT_FORMAT, 
                                                    utils.MAGIC_COOKIE, utils.MESSAGE_TYPE_PAYLOAD, decision_bytes)
                        tcp_socket.send(decision_packet)

                        if choice == "Stand":
                            # Do NOT set playing_round = False here. Let the next Recv handle the result.
                            # The server will send the final result after the player stands.
                            pass 
            
            win_rate = (wins / rounds) * 100 if rounds > 0 else 0
            print(f"\nFinished playing {rounds} rounds, win rate: {win_rate}%")
            tcp_socket.close()
            print("------------------------------------------")
        except Exception as e:
            print(f"Error during game: {e}")

if __name__ == "__main__":
    client = BlackjackClient(team_name="Sin City Boyz")
    client.start()