import json
import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Counter as CounterType
from collections import Counter
import copy

class TrainColor(Enum):
    PINK = "pink"
    WHITE = "white"
    BLUE = "blue"
    YELLOW = "yellow"
    ORANGE = "orange"
    BLACK = "black"
    RED = "red"
    GREEN = "green"
    LOCOMOTIVE = "locomotive"
    ANY = "any"  # Used for grey routes representation in static data, not for cards

class MoveType(Enum):
    DRAW_WAGON = auto() # From Deck
    DRAW_TICKET = auto()
    CLAIM_ROUTE = auto()
    BUILD_STATION = auto()
    TUNNEL_RESOLVE = auto() # For paying extra cards or forfeiting
    DRAW_FACE_UP = auto() # Specific face up card index

@dataclass
class Card:
    color: TrainColor

@dataclass
class Ticket:
    id: int
    cities: tuple[str, str]
    points: int

@dataclass
class Action:
    move_type: MoveType
    target_id: Optional[int] = None # Route ID, Station City ID, or FaceUp Card Index (0-4)
    color_used: Optional[TrainColor] = None # Specifically chosen color for grey routes
    count: int = 0
    # For Tunnel resolution:
    # count can be used for "number of cards paying"
    # if count == 0 in TUNNEL_RESOLVE, it means forfeit.

    def to_index(self) -> int:
        # Vectorization
        # 0-917: Claim Route (102 routes * 9 colors)
        # 918-1340: Build Station (47 cities * 9 colors)
        # 1341: Draw Wagon Deck
        # 1342: Draw Ticket Deck
        # 1343-1347: Draw FaceUp (5 slots)
        # 1348: Tunnel Pay
        # 1349: Tunnel Forfeit
        
        if self.move_type == MoveType.CLAIM_ROUTE:
             # target_id is route_id
             color_idx = list(TrainColor).index(self.color_used) if self.color_used else 0
             return self.target_id * 9 + color_idx
             
        elif self.move_type == MoveType.BUILD_STATION:
            # target_id is city_id
            color_idx = list(TrainColor).index(self.color_used) if self.color_used else 0
            return 918 + self.target_id * 9 + color_idx
            
        elif self.move_type == MoveType.DRAW_WAGON:
            return 1341
            
        elif self.move_type == MoveType.DRAW_TICKET:
            return 1342
            
        elif self.move_type == MoveType.DRAW_FACE_UP: 
            return 1343 + (self.target_id if self.target_id is not None else 0)
            
        elif self.move_type == MoveType.TUNNEL_RESOLVE:
            if self.count > 0: return 1348
            else: return 1349
            
        raise NotImplementedError(f"Action type {self.move_type} not supported for vectorization")

    @staticmethod
    def from_index(index: int) -> 'Action':
        # Placeholder for reverse mapping
        pass

class Deck:
    def __init__(self, cards: List[Card]):
        self.cards = cards
        self.discards: List[Card] = []

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self) -> Optional[Card]:
        if not self.cards:
            if not self.discards:
                return None
            self.cards = self.discards
            self.discards = []
            self.shuffle()
        
        if not self.cards: # Still empty?
            return None
            
        return self.cards.pop()

    def add_discard(self, cards: List[Card]):
        self.discards.extend(cards)
        
    def total_count(self) -> int:
        return len(self.cards) + len(self.discards)

@dataclass
class Route:
    id: int
    u: str
    v: str
    length: int
    color: TrainColor # If ANY, it's grey
    locomotives_required: int
    is_tunnel: bool
    owner: Optional[int] = None # Player ID

    @property
    def is_ferry(self) -> bool:
        return self.locomotives_required > 0 and not self.is_tunnel # Actually ferries are distinct, but usually defined by loco reqs in data. 
        # Checking data.json: "tunel": false, "tiles": [{'color': 'locomotive', ...}] -> This is likely a ferry.
        # But wait, tunnels can also have locomotives? No, usually ferries have explicit locomotive symbols.
        # In TTR Europe, Ferries require locomotives. Tunnels require 'risk'.
        # Data.json distinguishes logic by 'tunel' boolean and 'locomotive' presence in tiles.

@dataclass
class Player:
    id: int
    wagons: int = 45
    stations: int = 3
    hand: CounterType[TrainColor] = field(default_factory=Counter)
    tickets: List[Ticket] = field(default_factory=list)
    score: int = 0
    
    def copy(self) -> 'Player':
        # Efficient shallow copy where possible
        new_player = Player(
            id=self.id,
            wagons=self.wagons,
            stations=self.stations,
            hand=self.hand.copy(),
            tickets=list(self.tickets), # Shallow copy of list of immutable Tickets
            score=self.score
        )
        return new_player

class GameState:
    def __init__(self):
        self.players: List[Player] = []
        self.routes: List[Route] = []
        self.wagon_deck: Optional[Deck] = None
        self.ticket_deck: List[Ticket] = [] # Simple list for now, or Deck class if we recycle tickets (usually put to bottom)
        self.face_up_cards: List[Card] = []
        self.active_player_index: int = 0
        self.cards_drawn_this_turn: int = 0
        
        # Static/Global Game Data
        self.cities: Dict[str, int] = {} # Map city name -> ID
        
        # Tunnel State
        self.tunnel_active: bool = False
        self.tunnel_pending_route_id: Optional[int] = None
        self.tunnel_pending_cards: int = 0
        self.tunnel_resolving_color: Optional[TrainColor] = None 
        self.tunnel_initial_payment: List[Card] = [] # Cards committed initially, to be refunded on forfeit

        # Station State
        self.built_stations: Dict[str, int] = {} # City Name -> Player ID

        # End Game State
        self.final_turn_triggered: bool = False
        self.final_turns_remaining: int = -1 # When triggered, set to len(players)
    
    @staticmethod
    def from_json(path: str) -> 'GameState':
        with open(path, 'r') as f:
            data = json.load(f)
            
        gs = GameState()
        
        # Collect all city names for consistent ID mapping
        all_cities = set()
        for entry in data:
            all_cities.add(entry["stations"][0])
            all_cities.add(entry["stations"][1])
        
        gs.cities = {city: i for i, city in enumerate(sorted(list(all_cities)))}
        
        # Parse Routes
        # data is list of objects
        # Each object has "stations" (list of 2), "tunel" (bool), "tiles" (list of dicts)
        
        route_id_counter = 0
        for entry in data:
            u, v = entry["stations"][0], entry["stations"][1]
            is_tunnel = entry["tunel"]
            
            # tiles logic can be complex in JSON.
            # Example: [{"color": "any", "amount": 1}, {"color": "locomotive", "amount": 1}]
            # Or: [{"color": "orange", "amount": 4}]
            
            # Helper to consolidate tiles
            total_length = 0
            locos_req = 0
            route_color = TrainColor.ANY
            
            for tile in entry["tiles"]:
                amount = tile["amount"]
                total_length += amount
                color_str = tile["color"]
                
                if color_str == "locomotive":
                    locos_req += amount
                elif color_str != "any":
                    # If specific color is mentioned, that's the route color.
                    # Note: There shouldn't be mixed colors usually, except Locomotive + Color.
                    try:
                        route_color = TrainColor(color_str)
                    except ValueError:
                        print(f"Warning: Unknown color {color_str}")
            
            # If everything was "any" or "locomotive" (and locos don't define route color usually), it stays ANY (Grey).
            # If we had ANY + LOCO, it's Grey with Locos required (Ferry).
            
            route = Route(
                id=route_id_counter,
                u=u, 
                v=v,
                length=total_length,
                color=route_color,
                is_tunnel=is_tunnel,
                locomotives_required=locos_req
            )
            gs.routes.append(route)
            route_id_counter += 1
            
        return gs

    def clone(self) -> 'GameState':
        # Manual optimized copy
        new_gs = GameState()
        
        # Copy Players
        new_gs.players = [p.copy() for p in self.players]
        
        # Copy Routes (Immutable structure mostly, but 'owner' changes)
        # Since owner is the only mutable field on Route, we might need to copy Route if we modify it.
        # Alternatively, keep Routes static and store ownership in a separate array in GameState?
        # For now, let's deep copy routes to be safe, or just copy the list if we assume we swap instances on modification.
        # Better: Mutable Route objects are dangerous for shallow copies.
        # Optimization: Store ownership in a simple dict or array in GameState [route_id] -> player_id
        # BUT, conforming to existing design, let's just shallow copy the Route object itself (it's a dataclass).
        # We need new instances because we change 'owner'.
        new_gs.routes = [
            Route(r.id, r.u, r.v, r.length, r.color, r.is_tunnel, r.locomotives_required, r.owner)
            for r in self.routes
        ]
        
        # Decks
        # Assuming Deck has mutable list
        if self.wagon_deck:
            new_gs.wagon_deck = Deck(list(self.wagon_deck.cards)) # Shallow copy of list
            new_gs.wagon_deck.discards = list(self.wagon_deck.discards)
            
        new_gs.ticket_deck = list(self.ticket_deck) # Copy list
        
        new_gs.face_up_cards = list(self.face_up_cards)
        new_gs.active_player_index = self.active_player_index
        new_gs.cards_drawn_this_turn = self.cards_drawn_this_turn
        new_gs.cities = self.cities # Dictionary is read-only essentially, reference is fine
        
        # Tunnel State
        new_gs.tunnel_active = self.tunnel_active
        new_gs.tunnel_pending_route_id = self.tunnel_pending_route_id
        new_gs.tunnel_pending_cards = self.tunnel_pending_cards
        new_gs.tunnel_resolving_color = self.tunnel_resolving_color
        new_gs.tunnel_initial_payment = list(self.tunnel_initial_payment) # List of cards

        # Station State
        new_gs.built_stations = self.built_stations.copy() # Dict copy

        # End Game State
        new_gs.final_turn_triggered = self.final_turn_triggered
        new_gs.final_turns_remaining = self.final_turns_remaining
        
        return new_gs

    def check_face_up_reset(self):
        """
        Instructions: If 3 face-up cards are Locomotives, discard all 5 and refresh.
        Repeat if necessary.
        """
        while True:
            loco_count = sum(1 for c in self.face_up_cards if c.color == TrainColor.LOCOMOTIVE)
            if loco_count >= 3:
                # Discard all
                if self.wagon_deck:
                    self.wagon_deck.add_discard(self.face_up_cards)
                self.face_up_cards = []
                # Draw 5 new ones
                for _ in range(5):
                    if self.wagon_deck:
                        c = self.wagon_deck.draw()
                        if c:
                            self.face_up_cards.append(c)
            else:
                break
