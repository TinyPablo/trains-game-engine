import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.models import GameState, TrainColor, Card, Deck, Route, MoveType, Action

class TestModels(unittest.TestCase):
    def setUp(self):
        self.data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'data.json'))
        self.gamestate = GameState.from_json(self.data_path)

    def test_routes_loaded(self):
        # We expect a specific number of routes. 
        # Based on file lines (~800 lines shown, but file is 1376 lines), likely around 100 routes.
        # Let's just assert it's not empty and reasonable.
        self.assertTrue(len(self.gamestate.routes) > 50)
        print(f"Loaded {len(self.gamestate.routes)} routes.")

    def test_tunnel_parsing(self):
        # Find Pamplona-Madrid
        routes = [r for r in self.gamestate.routes if set([r.u, r.v]) == set(['pamplona', 'madrid'])]
        self.assertTrue(len(routes) > 0)
        tunnel = routes[0]
        self.assertTrue(tunnel.is_tunnel)
        # One of them is length 3, Black or White
        # Check specific one if possible, or just Ensure one exists.

    def test_ferry_parsing(self):
        # Dieppe-London is a ferry (1 any + 1 loco)
        routes = [r for r in self.gamestate.routes if set([r.u, r.v]) == set(['dieppe', 'london'])]
        self.assertTrue(len(routes) > 0)
        ferry = routes[0] # There might be two
        self.assertTrue(ferry.locomotives_required >= 1)
        self.assertFalse(ferry.is_tunnel)

    def test_deck_mechanics(self):
        cards = [Card(TrainColor.RED), Card(TrainColor.BLUE), Card(TrainColor.WHITE)]
        deck = Deck(cards)
        self.assertEqual(deck.total_count(), 3)
        
        c1 = deck.draw()
        self.assertIsNotNone(c1)
        self.assertEqual(deck.total_count(), 2) # Discard is separate until added back or implicit?
        # Deck logic: cards pop, discards separate. total_count sums them?
        # My implementation: total_count = len(cards) + len(discards)
        # So drawing reduces total_count by 1 until discarded properly? 
        # Wait, usually total_count should track all cards in system (deck + discard).
        # My implementation:
        # def total_count(self) -> int: return len(self.cards) + len(self.discards)
        # So if I draw, it's in hand/played, not in deck/discard. Correct.
        
        deck.add_discard([c1])
        self.assertEqual(deck.total_count(), 3)

    def test_gamestate_clone(self):
        # Modify original
        self.gamestate.active_player_index = 1
        self.gamestate.tunnel_active = True
        
        # Clone
        clone = self.gamestate.clone()
        
        # Assert equality of values
        self.assertEqual(clone.active_player_index, 1)
        self.assertTrue(clone.tunnel_active)
        
        # Modify clone, ensure original untouched
        clone.active_player_index = 2
        clone.tunnel_active = False
        
        self.assertEqual(self.gamestate.active_player_index, 1)
        self.assertTrue(self.gamestate.tunnel_active)
        
        # Check list independence
        clone.routes[0].owner = 99
        self.assertIsNone(self.gamestate.routes[0].owner)

    def test_locomotive_reset(self):
        # Setup specific face up cards
        self.gamestate.face_up_cards = [
            Card(TrainColor.RED),
            Card(TrainColor.LOCOMOTIVE),
            Card(TrainColor.LOCOMOTIVE),
            Card(TrainColor.LOCOMOTIVE),
            Card(TrainColor.BLUE)
        ]
        # Needs a deck to draw from
        self.gamestate.wagon_deck = Deck([Card(TrainColor.GREEN) for _ in range(10)])
        
        self.gamestate.check_face_up_reset()
        
        # Should have discarded the 5 cards and drawn 5 new (Green + others)
        # Note: Deck originally had 10 Greens.
        # Discards should now contain the 3 Locos + Red + Blue.
        # Face up should be 5 Greens.
        
        self.assertEqual(len(self.gamestate.face_up_cards), 5)
        for c in self.gamestate.face_up_cards:
            self.assertEqual(c.color, TrainColor.GREEN)
            
        self.assertTrue(self.gamestate.wagon_deck.total_count() > 0) # Discards are in total count?
        # check_face_up_reset: "self.wagon_deck.add_discard(self.face_up_cards)"
        # So discards grow.
        self.assertEqual(len(self.gamestate.wagon_deck.discards), 5)

if __name__ == '__main__':
    unittest.main()
