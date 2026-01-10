import socket
import time
import threading
import struct
import utils
import random

class BlackjackServer:
    def __init__(self, team_name):
        self.team_name = team_name
        self.tcp_port = 0 # Will be set by the os
        self.server_ip = self.get_local_ip()


    def get_local_ip(self):
        """This function finds our IP address of on the local network"""
        # We create a temporary connection only to get our ip
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # AF_INET-use ipv4, SOCK_DGRAM-upd
        try:
            # Trying to reach google's ip to get understand if to use the wifi or etehenet
            temp_socket.connect(('8.8.8.8', 1))
            ip_address = temp_socket.getsockname()[0] # getting only the ip no port
        except Exception:
            # If there is no internet, we will run localy by setting the ip to the local host
            ip_address = '127.0.0.1' 
        finally:
            temp_socket.close()
        return ip_address


    def setup_tcp_socket(self):
        """Creates TCP socket to listen for new players"""
        # Creating the socket: AF_INET = IPv4, SOCK_STREAM = TCP 
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        # SO_REUSEADDR tells the OS to release the port after the server stops
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # binding the socket to our IP. '0' lets the OS pick a random free port.
        self.tcp_socket.bind((self.server_ip, 0)) 
        # getting the port
        self.tcp_port = self.tcp_socket.getsockname()[1] 
        # start listening for up to 5 queued connections.
        self.tcp_socket.listen(5)
        
        print(f"TCP server established on port {self.tcp_port}")

    def start_udp_broadcast(self):
        """Create a UDP socket for broadcasting the offer"""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Making the socket to be sent by broadcast to every device in the local network
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # team_name must be encoded to bytes and padded to 32 bytes
        encoded_name = self.team_name.encode('utf-8')[:32].ljust(32, b'\x00')
        
        # struct.pack packs (Cookie, Type, Port, Name) into a sequence of bytes for utils
        offer_packet = struct.pack(
            utils.OFFER_FORMAT, 
            utils.MAGIC_COOKIE, 
            utils.MESSAGE_TYPE_OFFER, 
            self.tcp_port, # here the real port ia set
            encoded_name
        )

        while True:
            # Send the offer message
            udp_socket.sendto(offer_packet, ('<broadcast>', utils.UDP_PORT))
            time.sleep(1) # Send once every second 


    def start(self):
        """this func starts the server"""
        # Setting up the welcome socket
        # The 'Offer' packet MUST contain this TCP port 
        # so clients know where to send their 'Request' later.
        self.setup_tcp_socket()
        
        # Start the UDP 'Offer' broadcast in a separate thread.
        # This keeps the 'while True' loop from stopping the rest of our code
        broadcast_thread = threading.Thread(target=self.start_udp_broadcast, daemon=True)
        broadcast_thread.start()
        
        print(f"Server started, listening on IP address {self.server_ip}")
        
        # Main thread waits to accept players
        self.accept_players()

    def accept_players(self):
        """Main loop that waits for clients to connect with TCP.
        Handling transition from 'Offer' to 'Request'."""
        print("Waiting for players to connect...")
        while True:
            # .accept() waits for a client who heard our UDP 'Offer' to 'Request' a game.
            #  + creating TCP for the player.
            client_socket, client_address = self.tcp_socket.accept()
            print(f"New player connected from {client_address}")
            
            try:
                # Request (Client -> Server, TCP)
                # We expect a 0x3 Request packet. 
                # Total size = 4 (Cookie) + 1 (Type) + 1 (Rounds) + 32 (Name) = 38 bytes.
                packet_data = client_socket.recv(38)
                
                if len(packet_data) < 38:
                    print("Error: Received incomplete request packet.")
                    client_socket.close()
                    continue

                # Unpack the binary data using the format we defined in utils
                cookie, msg_type, rounds, raw_name = struct.unpack(utils.REQUEST_FORMAT, packet_data)

                # Checking Magic Cookie   
                if cookie != utils.MAGIC_COOKIE:
                    print("Rejected: Invalid Magic Cookie.")
                    client_socket.close()
                    continue

                # Check if it is actually a Request packet
                if msg_type != utils.MESSAGE_TYPE_REQUEST:
                    print(f"Rejected: Expected Request (0x3), got {msg_type}")
                    client_socket.close()
                    continue

                # Clean up the team name remove padding bytes
                client_name = raw_name.decode('utf-8').strip('\x00')
                print(f"Player '{client_name}' wants to play {rounds} rounds.")

                # Start the actual Game Rounds - Payloads 
                print(f"Starting {rounds} rounds of Blackjack with {client_name}...")
                self.run_game_session(client_socket, rounds, client_name)

            except Exception as e:
                print(f"Error handling player: {e}")
            # After the rounds are finished- closing the connection
            client_socket.close()
            print(f"Connection with {client_address} closed.")

                
    def run_game_session(self, client_socket, rounds, client_name):
        """Handles the full Blackjack logic including scores and Dealer turn"""
        for r in range(1, rounds + 1):
            print(f"--- Round {r} vs {client_name} ---")
            player_total = 0
            dealer_total = 0
            in_round = True

            # --- PLAYER'S TURN ---
            while in_round:
                # 1. Generate a new card and update player total
                rank = random.randint(1, 13)
                suit = random.randint(0, 3)
                player_total += utils.get_card_value(rank)
                
                print(f"Dealt {rank} to {client_name}. Total: {player_total}")

                # 2. Check if player busted (over 21)
                if player_total > 21:
                    # Send final result (0x2 for LOSS)
                    self.send_payload(client_socket, utils.RESULT_LOSS, rank, suit)
                    print(f"{client_name} Busted! Dealer wins.")
                    in_round = False
                    break # Exit the round loop immediately

                # 3. Send current card and wait for client's move
                # Result is 0x0 (Not Over) because the player hasn't busted or stayed yet
                self.send_payload(client_socket, utils.RESULT_NOT_OVER, rank, suit)
                
                # 4. Wait for Player Decision (0x4 Payload, 10 bytes)
                decision_packet = client_socket.recv(10)
                if not decision_packet:
                    in_round = False
                    break

                # Unpack the decision using !IB5s
                cookie, msg_type, raw_decision = struct.unpack(utils.PAYLOAD_CLIENT_FORMAT, decision_packet)
                decision = raw_decision.decode('utf-8').strip('\x00').strip().capitalize()

                print(f"Player {client_name} decided to: {decision}")

                # 5. Handle decision logic
                if decision == "Stand":
                    # --- DEALER'S TURN ---
                    # Only triggered if player stops and hasn't busted
                    print(f"{client_name} stands at {player_total}. Dealer's turn...")
                    
                    # Dealer must draw until total is at least 17
                    while dealer_total < 17:
                        dealer_card = random.randint(1, 13)
                        dealer_total += utils.get_card_value(dealer_card)
                    
                    print(f"Dealer finished with {dealer_total}")
                    
                    # 6. Determine final round result
                    if dealer_total > 21 or player_total > dealer_total:
                        result = utils.RESULT_WIN # Player wins
                    elif player_total < dealer_total:
                        result = utils.RESULT_LOSS # Dealer wins
                    else:
                        result = utils.RESULT_TIE # Push/Tie
                    
                    # 7. Send final result packet to close the round
                    # We use dummy values (0,0) for rank/suit as the round is now over
                    self.send_payload(client_socket, result, 0, 0)
                    in_round = False # Exit the while loop to move to next round
                
                # If decision is "Hittt", the 'while in_round' continues and deals another card

    def send_payload(self, client_socket, result, rank, suit):
        """Helper to pack and send the 0x4 Payload packet"""
        payload = struct.pack(utils.PAYLOAD_SERVER_FORMAT, utils.MAGIC_COOKIE, 
                            utils.MESSAGE_TYPE_PAYLOAD, result, rank, suit)
        client_socket.send(payload)








# Main execution
if __name__ == "__main__":
    # Setting the server and our team name
    server = BlackjackServer(team_name="Vegas Best Casino")
    
    server.start()