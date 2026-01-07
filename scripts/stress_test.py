import sys
import os
import random
import time
from collections import Counter

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.models import GameState, Player, MoveType
from engine.gamelogic import GameLogic

def run_simulation(seed):
    random.seed(seed)
    # Load Real Data
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'data.json'))
    gs = GameState.from_json(data_path)
    
    # Setup Players
    # 4 Players
    gs.players = [Player(id=i) for i in range(4)]
    
    # Setup Deck
    # Standard: 12 cards of 8 colors + 14 Locomotives = 110 cards
    # TrainColor has 9 values including ANY.
    from engine.models import TrainColor, Card, Deck
    colors = [c for c in TrainColor if c != TrainColor.ANY and c != TrainColor.LOCOMOTIVE]
    cards = []
    for c in colors:
        cards.extend([Card(c) for _ in range(12)])
    cards.extend([Card(TrainColor.LOCOMOTIVE) for _ in range(14)])
    
    gs.wagon_deck = Deck(cards)
    gs.wagon_deck.shuffle()
    
    # Initial Draw
    for p in gs.players:
        for _ in range(4):
            c = gs.wagon_deck.draw()
            if c: p.hand[c.color] += 1
            
    gs.face_up_cards = [gs.wagon_deck.draw() for _ in range(5)]
    # (Checking reset rules ignored for speed here, or assume engine handles it on first draw?)
    # Actually engine only checks on Draw FaceUp.
    
    # Simulation Loop
    turn_limit = 500
    turns = 0
    
    while turns < turn_limit:
        active_pid = gs.active_player_index
        moves = GameLogic.get_legal_moves(gs, active_pid)
        
        if not moves:
            # Stalemate or bug?
            # Could happen if deck empty and discard empty?
            # Or Game End triggered and finished?
            if gs.final_turns_remaining == 0:
                break
            # print(f"No legal moves for P{active_pid}. Game Over?")
            break
            
        # Random choice
        action = random.choice(moves)
        
        prev_player = gs.active_player_index
        GameLogic.apply_action(gs, action)
        
        if prev_player != gs.active_player_index:
             turns += 1
             
        if gs.final_turns_remaining == 0:
            break
            
    GameLogic.calculate_score(gs)
    # print(f"Game {seed} finished. Turns: {turns}. Scores: {[p.score for p in gs.players]}")
    return True

if __name__ == "__main__":
    count = 1000
    failures = 0
    start = time.time()
    
    print(f"Starting stress test of {count} games...")
    
    for i in range(count):
        try:
            run_simulation(i)
            if i % 100 == 0:
                print(f"Completed {i} games...", end="\r")
        except Exception as e:
            print(f"Game {i} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failures += 1
            if failures >= 5:
                print("Too many failures. Stopping.")
                break
                
    end = time.time()
    print(f"\nDone. {count} games. Failures: {failures}. Time: {end-start:.2f}s")
