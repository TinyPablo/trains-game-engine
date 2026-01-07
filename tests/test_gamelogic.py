import sys
import os
import unittest
from engine.models import GameState, Player, Action, MoveType, TrainColor, Card, Deck, Route
from engine.gamelogic import GameLogic

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestGameLogic(unittest.TestCase):
    def setUp(self):
        self.data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'data.json'))
        self.gamestate = GameState.from_json(self.data_path)
        
        # Setup 2 players
        self.gamestate.players = [Player(id=0), Player(id=1)]
        self.gamestate.wagon_deck = Deck([Card(TrainColor.RED) for _ in range(50)])
        self.gamestate.wagon_deck.shuffle()
        # Ensure face up cards
        self.gamestate.face_up_cards = [self.gamestate.wagon_deck.draw() for _ in range(5)]

    def test_vectorization(self):
        # Claim Route 0 (Color Pink = 0)
        a = Action(MoveType.CLAIM_ROUTE, target_id=0, color_used=TrainColor.PINK)
        idx = a.to_index()
        self.assertEqual(idx, 0)
        
        # Draw Wagon
        a = Action(MoveType.DRAW_WAGON)
        self.assertEqual(a.to_index(), 1341)
        
        # Tunnel Pay
        a = Action(MoveType.TUNNEL_RESOLVE, count=1)
        self.assertEqual(a.to_index(), 1348)

    def test_turn_logic_draw(self):
        # Initial State: 0 cards drawn
        self.assertEqual(self.gamestate.cards_drawn_this_turn, 0)
        self.assertEqual(self.gamestate.active_player_index, 0)
        
        # Action: Draw Wagon
        action = Action(MoveType.DRAW_WAGON)
        GameLogic.apply_action(self.gamestate, action)
        
        # State: 1 card drawn, still player 0
        self.assertEqual(self.gamestate.cards_drawn_this_turn, 1)
        self.assertEqual(self.gamestate.active_player_index, 0)
        
        # Legal Moves should be restricted
        moves = GameLogic.get_legal_moves(self.gamestate, 0)
        move_types = set(m.move_type for m in moves)
        self.assertIn(MoveType.DRAW_WAGON, move_types)
        self.assertNotIn(MoveType.CLAIM_ROUTE, move_types)
        
        # Action: Draw Wagon again
        GameLogic.apply_action(self.gamestate, action)
        
        # State: 0 cards drawn, player 1 active
        self.assertEqual(self.gamestate.cards_drawn_this_turn, 0)
        self.assertEqual(self.gamestate.active_player_index, 1)

    def test_claim_route_simple(self):
        # Setup: Player 0 has cards for Route 0 (Edinburgh-London, length 4, Black?)
        # Let's verify Route 0 details first
        r0 = self.gamestate.routes[0]
        # Data load order might vary? 
        # Actually from_json uses list order.
        # r0 is Edinburgh-London (Black / Orange based on data.json dump line 10/24)
        # Let's force a known route
        # Route 0 in previous view was [Edinburgh, London, Orange, 4]
        
        player = self.gamestate.players[0]
        player.hand[TrainColor.ORANGE] = 4
        player.wagons = 45
        
        # Action
        action = Action(MoveType.CLAIM_ROUTE, target_id=r0.id, color_used=TrainColor.ORANGE, count=4)
        
        # Check legality
        legal = GameLogic.get_legal_moves(self.gamestate, 0)
        # Identify our action in legal (Action equality check needed?)
        # Action dataclass has equality by value.
        # Note: count might be implicit in legal generation logic.
        # The generator produced actions with count=length.
        self.assertIn(action, legal)
        
        # Apply
        GameLogic.apply_action(self.gamestate, action)
        
        # Route owned
        self.assertEqual(r0.owner, 0)
        # Score updated (Length 4 -> 7 points)
        self.assertEqual(player.score, 7)
        # Wagons reduced
        self.assertEqual(player.wagons, 41)
        # Turn ended
        self.assertEqual(self.gamestate.active_player_index, 1)

    def test_tunnel_trigger(self):
        # Find Tunnel: Pamplona-Madrid (Length 3)
        tunnels = [r for r in self.gamestate.routes if r.is_tunnel]
        self.assertTrue(len(tunnels) > 0)
        tunnel = tunnels[0]
        
        player = self.gamestate.players[0]
        # Give tons of cards
        player.hand[TrainColor.BLUE] = 10 
        player.hand[TrainColor.LOCOMOTIVE] = 5
        
        # Attempt claim with Blue (assuming tunnel allows blue/any)
        # We need to know tunnel color.
        # If tunnel is specific signal color or Grey.
        # Pamplona-Madrid is [Black, 3] and [White, 3] and [Any, 2] based on json lines 170-200
        # Let's find the Grey one if possible, or Any.
        
        # Let's just create a mock route/situation if finding is hard, 
        # or just inspect the one we found.
        # print(f"Testing Tunnel: {tunnel.u}-{tunnel.v} Color: {tunnel.color}")
        
        # Let's fake the tunnel color requirements for the test if needed,
        # or ensure we pick the right color.
        # Assume we picked a Grey tunnel or matching color.
        req_color = tunnel.color
        if req_color == TrainColor.ANY:
            req_color = TrainColor.BLUE # Player chooses Blue
            
        player.hand[req_color] = 5
        
        action = Action(MoveType.CLAIM_ROUTE, target_id=tunnel.id, color_used=req_color, count=tunnel.length)
        
        # Apply Claim (Step 1)
        GameLogic.apply_action(self.gamestate, action)
        
        # State: Tunnel Active
        self.assertTrue(self.gamestate.tunnel_active)
        self.assertEqual(self.gamestate.tunnel_pending_route_id, tunnel.id)
        # Pending cards could be 0-3 depending on draw.
        # Start of game WagonDeck has RED cards (test setup).
        # If we claim with Blue, and deck is all RED, pending should be 0.
        # If we claim with RED, pending is 3.

if __name__ == '__main__':
    unittest.main()
