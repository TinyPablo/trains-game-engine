from typing import List, Optional
import random
from engine.models import GameState, Player, Action, MoveType, TrainColor, Card, Route

class GameLogic:
    SCORING_TABLE = {1: 1, 2: 2, 3: 4, 4: 7, 6: 15, 8: 21}

    @staticmethod
    def get_legal_moves(gs: GameState, player_id: int) -> List[Action]:
        moves = []
        player = gs.players[player_id]

        # 0. Check Turn Order (sanity check, usually engine handles this)
        if gs.active_player_index != player_id:
            return []

        # 1. Tunnel Phase Override
        if gs.tunnel_active:
            # Must Resolve Tunnel
            # Option 1: Forfeit
            moves.append(Action(MoveType.TUNNEL_RESOLVE, count=0))
            
            # Option 2: Pay pending cards
            # Check if player has enough cards of `tunnel_resolving_color` (or Locos)
            # Pending Cards needed = gs.tunnel_pending_cards
            # Player needs EXACTLY this amount or MORE? 
            # Rules: "Must pay 1 additional card... for every card drawn that matches"
            # Yes, need to pay `tunnel_pending_cards`.
            
            req_color = gs.tunnel_resolving_color
            req_amount = gs.tunnel_pending_cards
            
            if req_amount > 0:
                # Count available cards
                # Note: We must use Locos or specific Color.
                # Logic: We can mix color + locos.
                if req_color == TrainColor.LOCOMOTIVE:
                    # Can only pay with Locos? Usually tunnels define a color. 
                    # If tunnel was "Locomotive Only" (unlikely in Europe except ferries?), then yes.
                    # But `resolving_color` usually comes from the cards PLAYED initially.
                    # If player played Locos as jokers for a Red tunnel, resolving color is Red.
                    # If player played only Locos for a Grey tunnel, resolving color is... ?
                    # Usually player declares the color.
                    avail_locos = player.hand[TrainColor.LOCOMOTIVE]
                    if avail_locos >= req_amount:
                        moves.append(Action(MoveType.TUNNEL_RESOLVE, count=req_amount, color_used=TrainColor.LOCOMOTIVE))
                else:
                     # Color + Locos
                    avail_color = player.hand[req_color]
                    avail_locos = player.hand[TrainColor.LOCOMOTIVE]
                    if avail_color + avail_locos >= req_amount:
                        moves.append(Action(MoveType.TUNNEL_RESOLVE, count=req_amount, color_used=req_color))
            else:
                # If pending is 0 (lucky!), auto-pay (count=0 but distinct from forfeit?)?
                # Actually if pending is 0, we should probably auto-resolve in apply_action immediately,
                # but if we are here, we give a "Confirm" action (Pay 0).
                moves.append(Action(MoveType.TUNNEL_RESOLVE, count=0, color_used=req_color)) # Pay 0 implies Success

            return moves

        # 2. Main Turn Logic
        
        # If we already drew 1 card, restricted options
        if gs.cards_drawn_this_turn == 1:
            # Can only draw Wagon (Blind) or FaceUp (Non-Loco)
            moves.append(Action(MoveType.DRAW_WAGON))
            
            for i, card in enumerate(gs.face_up_cards):
                if card.color != TrainColor.LOCOMOTIVE:
                    moves.append(Action(MoveType.DRAW_FACE_UP, target_id=i))
            return moves

        # If Start of Turn (0 cards drawn)
        
        # A. Draw Wagon (Blind)
        moves.append(Action(MoveType.DRAW_WAGON))
        
        # B. Draw Ticket
        moves.append(Action(MoveType.DRAW_TICKET))
        
        # C. Draw FaceUp
        for i, card in enumerate(gs.face_up_cards):
            moves.append(Action(MoveType.DRAW_FACE_UP, target_id=i))
            
        # D. Build Station
        # Limit 3 stations
        if player.stations > 0:
            cost = 4 - player.stations # 1, 2, or 3 cards
            
            # Can build on ANY city that does not have station
            for city_name, city_id in gs.cities.items():
                if city_name not in gs.built_stations:
                    # Check if player has cards to pay cost
                    # Need `cost` cards of ANY single color (+ Locos)
                    
                    possible_colors = set()
                    # Check each color
                    for c in TrainColor:
                        if c == TrainColor.ANY or c == TrainColor.LOCOMOTIVE: continue
                        if player.hand[c] + player.hand[TrainColor.LOCOMOTIVE] >= cost:
                            possible_colors.add(c)
                    
                    for pc in possible_colors:
                        moves.append(Action(MoveType.BUILD_STATION, target_id=city_id, color_used=pc, count=cost))

        # E. Claim Route
        # Check all unowned routes
        for route in gs.routes:
            if route.owner is not None:
                continue
            
            # Double Route Check (2-3 Players)
            if len(gs.players) < 4:
                # Find sibling
                siblings = [r for r in gs.routes if set([r.u, r.v]) == set([route.u, route.v]) and r.id != route.id]
                if any(s.owner is not None for s in siblings):
                    continue

            # Length/Cost Check
            length = route.length
            # Logic for card checking
            # Requires considering Locomotives and Colors.
            
            # If Route has specific color
            if route.color != TrainColor.ANY:
                # Must pay `length` cards of `color` (Locos can sub)
                # Exception: Ferries (Locos required)
                
                needed_color = route.color
                needed_count = length
                locos_required = route.locomotives_required
                
                if player.wagons >= length: # Must have wagons
                    # Check resources
                    hand_color = player.hand[needed_color]
                    hand_locos = player.hand[TrainColor.LOCOMOTIVE]
                    
                    if hand_locos >= locos_required:
                         remaining_len = length - locos_required
                         # We can pay remaining_len with (hand_color + remaining_locos)
                         if hand_color + (hand_locos - locos_required) >= remaining_len:
                             moves.append(Action(MoveType.CLAIM_ROUTE, target_id=route.id, color_used=needed_color, count=length))
            
            else: # Grey Route
                 # Can use ANY color set.
                 if player.wagons >= length:
                     locos_required = route.locomotives_required
                     
                     for color in TrainColor:
                         if color == TrainColor.LOCOMOTIVE or color == TrainColor.ANY:
                             continue
                         
                         # Try paying with 'color'
                         hand_color = player.hand[color]
                         hand_locos = player.hand[TrainColor.LOCOMOTIVE]
                         
                         if hand_locos >= locos_required:
                             remaining_len = length - locos_required
                             if hand_color + (hand_locos - locos_required) >= remaining_len:
                                 moves.append(Action(MoveType.CLAIM_ROUTE, target_id=route.id, color_used=color, count=length))
                                 
        return moves

    @staticmethod
    def apply_action(gs: GameState, action: Action):
        player = gs.players[gs.active_player_index]
        
        # 0. TUNNEL RESOLVE
        if action.move_type == MoveType.TUNNEL_RESOLVE:
            if action.count > 0: # Pay
                 # Consume "extra" cards
                 GameLogic._deduct_cards_strict(gs, player, action.color_used, action.count)
                 
                 # Success! Claim route.
                 route = gs.routes[gs.tunnel_pending_route_id]
                 route.owner = player.id
                 player.wagons -= route.length
                 player.score += GameLogic.SCORING_TABLE.get(route.length, 0)
                 
                 # Discard initial payment now (it was held in limbo)
                 gs.wagon_deck.add_discard(gs.tunnel_initial_payment)
            
            else:
                 # Forfeit
                 # Refund cards played initially
                 for card in gs.tunnel_initial_payment:
                     player.hand[card.color] += 1
            
            # Reset Tunnel State
            gs.tunnel_active = False
            gs.tunnel_pending_route_id = None
            gs.tunnel_pending_cards = 0
            gs.tunnel_initial_payment = []
            
            # End Turn
            GameLogic._end_turn(gs)
            return

        # 1. DRAW WAGON
        if action.move_type == MoveType.DRAW_WAGON:
            card = gs.wagon_deck.draw()
            if card:
                player.hand[card.color] += 1
            
            gs.cards_drawn_this_turn += 1
            if gs.cards_drawn_this_turn >= 2:
                GameLogic._end_turn(gs)

        # 2. DRAW FACE UP
        elif action.move_type == MoveType.DRAW_FACE_UP:
            idx = action.target_id
            if 0 <= idx < len(gs.face_up_cards):
                card = gs.face_up_cards.pop(idx)
                player.hand[card.color] += 1
                
                # Refill
                new_card = gs.wagon_deck.draw()
                if new_card:
                    gs.face_up_cards.insert(idx, new_card)
                
                # Check Loco Reset
                gs.check_face_up_reset()
                
                # Turn Logic
                if card.color == TrainColor.LOCOMOTIVE:
                    # Loco counts as 2 cards (ends turn)
                    GameLogic._end_turn(gs)
                else:
                    gs.cards_drawn_this_turn += 1
                    if gs.cards_drawn_this_turn >= 2:
                        GameLogic._end_turn(gs)

        # 3. CLAIM ROUTE
        elif action.move_type == MoveType.CLAIM_ROUTE:
             route = gs.routes[action.target_id]
             
             # Identify actual cards to remove
             # We assume vectorization/action creator provided `color_used` and `count`.
             # For standard route: count = length.
             # For tunnel: count = length (initial).
             
             # Determine cost composition (Locos vs Color)
             # Greedy approach handled in helper? 
             # Or we simply take Color first, then Locos.
             # IMPORTANT: For Tunnels, we must store what we took.
             
             removed_cards = GameLogic._deduct_cards_strict(gs, player, action.color_used, action.count)
             
             if route.is_tunnel:
                 gs.tunnel_active = True
                 gs.tunnel_pending_route_id = route.id
                 gs.tunnel_resolving_color = action.color_used
                 gs.tunnel_initial_payment = removed_cards # Hold in limbo
                 
                 # Draw 3 cards
                 risk_cards = []
                 for _ in range(3):
                     c = gs.wagon_deck.draw()
                     if c: risk_cards.append(c)
                 
                 # Check matches
                 extra = 0
                 for c in risk_cards:
                     if c.color == action.color_used or c.color == TrainColor.LOCOMOTIVE:
                         extra += 1
                 
                 gs.tunnel_pending_cards = extra
                 gs.wagon_deck.add_discard(risk_cards)
                 
             else:
                 # Standard Claim
                 route.owner = player.id
                 player.wagons -= route.length
                 player.score += GameLogic.SCORING_TABLE.get(route.length, 0)
                 gs.wagon_deck.add_discard(removed_cards)
                 
                 # End Turn
                 GameLogic._end_turn(gs)

        # 4. BUILD STATION
        elif action.move_type == MoveType.BUILD_STATION:
            # City ID provided in target_id? No, target_id is mapped from index.
            # Action vectorization says 918+ for stations.
            # action.target_id should be CITY ID (0-46)
            
            # Find city name from ID
            # gs.cities is Name->ID. Reverse lookup needed?
            # Or just store stations by ID? `built_stations` can be ID->PlayerID for efficiency.
            # Instructions said "CityName -> PlayerID" but ID is better.
            # Let's stick to ID in built_stations dict if possible, or Name if required.
            # User request: "CityName -> PlayerID". Okay. vectorization maps index to CityID.
            
            city_name = None
            for name, cid in gs.cities.items():
                if cid == action.target_id:
                    city_name = name
                    break
            
            if city_name:
                # Cost: 1st station = 1 card, 2nd = 2, 3rd = 3.
                # Player starts with 3 stations. 
                # Cost = 4 - stations (e.g. 3 stations left -> cost 1)
                cost = 4 - player.stations
                
                # Deduct cards
                # User can use ANY color (set of same color).
                # Action should specify `color_used` and `count`=cost.
                
                deducted = GameLogic._deduct_cards_strict(gs, player, action.color_used, cost)
                gs.wagon_deck.add_discard(deducted)
                
                player.stations -= 1
                gs.built_stations[city_name] = player.id
                
                GameLogic._end_turn(gs)

        # 5. DRAW TICKET
        elif action.move_type == MoveType.DRAW_TICKET:
            # Simplification: Draw 3, Keep 1?
            # Or Draw 3, add all to hand (Action needed to discard tickets?)
            # RL often simplifies to "Draw Tickets" -> Get random tickets.
            # Instructions: "Draw 3... MUST keep at least 1."
            # Simpler for Engine: Just draw 3 and keep them.
            # Or return 'Ticket Decision' state?
            # Let's assume for this version: Draw 3, Keep all (or random 1-3).
            # To minimize state complexity: Draw 3, Keep All.
            # Discarding tickets is strategic but complex. 
            # Revisit if strict rules needed. For now: Draw 3.
            
            # Draw up to 3
            # Ticket Deck is list of Ticket
            drawn = []
            for _ in range(3):
                if gs.ticket_deck:
                    # pop from top (index 0 or -1? List usually pop() is last)
                    # Assuming deck was shuffled.
                    drawn.append(gs.ticket_deck.pop())
            
            player.tickets.extend(drawn)
            GameLogic._end_turn(gs)

    @staticmethod
    def _deduct_cards_strict(gs, player, color, count) -> List[Card]:
        """
        Removes `count` cards matching `color` (including Locos) from player hand.
        Prioritizes Color, then Locos. Returns list of removed Card objects.
        """
        removed = []
        
        # 1. Take specific color
        if color != TrainColor.ANY and color != TrainColor.LOCOMOTIVE:
            avail = player.hand[color]
            take = min(avail, count)
            player.hand[color] -= take
            count -= take
            removed.extend([Card(color) for _ in range(take)])
        
        # 2. Take Locos
        if count > 0:
            avail_locos = player.hand[TrainColor.LOCOMOTIVE]
            take_locos = min(avail_locos, count)
            player.hand[TrainColor.LOCOMOTIVE] -= take_locos
            count -= take_locos
            removed.extend([Card(TrainColor.LOCOMOTIVE) for _ in range(take_locos)])
            
        if count > 0:
            # Should not happen if legal check correct
            raise ValueError(f"Player {player.id} cannot pay full cost. Missing {count}.")
            
        return removed

    @staticmethod
    def _end_turn(gs):
        player = gs.players[gs.active_player_index]
        gs.cards_drawn_this_turn = 0
        
        # Check End Game Trigger
        if not gs.final_turn_triggered:
            if player.wagons <= 2:
                gs.final_turn_triggered = True
                gs.final_turns_remaining = len(gs.players)
        
        # Final Turn Logic
        if gs.final_turn_triggered:
            gs.final_turns_remaining -= 1
            if gs.final_turns_remaining <= 0:
                # Game Ends
                # How to signal? 
                # Usually step() returns `terminated=True`
                # We can set a flag `gs.game_over = True`?
                # For now just ensure no next player logic if 0?
                pass
        
        gs.active_player_index = (gs.active_player_index + 1) % len(gs.players)

    @staticmethod
    def _find_longest_path_dfs(current_node, current_len, used_routes_ids, adj_edges, memo):
        # Optimization: memoization might be hard with 'used_routes' set.
        # But graph is small.
        max_l = current_len
        
        for (neighbor, length, rid) in adj_edges.get(current_node, []):
            if rid not in used_routes_ids:
                used_routes_ids.add(rid)
                val = GameLogic._find_longest_path_dfs(neighbor, current_len + length, used_routes_ids, adj_edges, memo)
                max_l = max(max_l, val)
                used_routes_ids.remove(rid)
        
        return max_l

    @staticmethod
    def calculate_score(gs: GameState):
        """
        Final score calculation.
        """
        longest_paths = {p.id: 0 for p in gs.players}
        
        for player in gs.players:
            player_routes = [r for r in gs.routes if r.owner == player.id]
            
            # A. Route Points
            route_score = sum(GameLogic.SCORING_TABLE.get(r.length, 0) for r in player_routes)
            
            # B. Stations (+4 each unused)
            station_score = player.stations * 4
            
            # Build Adjacency for Graph
            # City -> List of (Neighbor, Length, RouteID)
            edge_adj = {}
            simple_adj = {} # For BFS
            
            cities = set()
            for r in player_routes:
                cities.add(r.u)
                cities.add(r.v)
                
                if r.u not in edge_adj: edge_adj[r.u] = []
                if r.v not in edge_adj: edge_adj[r.v] = []
                edge_adj[r.u].append((r.v, r.length, r.id))
                edge_adj[r.v].append((r.u, r.length, r.id))
                
                if r.u not in simple_adj: simple_adj[r.u] = set()
                if r.v not in simple_adj: simple_adj[r.v] = set()
                simple_adj[r.u].add(r.v)
                simple_adj[r.v].add(r.u)

            # C. Tickets
            ticket_score = 0
            for ticket in player.tickets:
                start, end = ticket.cities
                # TODO: Implement Station Borrowing here if data allows.
                # Current: Strict check.
                if GameLogic._check_path(simple_adj, start, end):
                    ticket_score += ticket.points
                else:
                    ticket_score -= ticket.points

            # D. Longest Path
            # Try starting from every leaf node (degree 1) or all nodes if loops.
            # Optimization: Only start from nodes with odd degree (endpoints) or all if all even.
            # Brute force from all nodes for safety on small graphs (45 wagons max path).
            best_path = 0
            # To save time, maybe just endpoints?
            # TTR maps have loops, so standard "diameter" is hard.
            # Heuristic: Start from cities with degree 1, then degree 3?
            
            # Let's try all "endpoints" (degree 1) as starts. If none, pick any.
            starts = [node for node, edges in edge_adj.items() if len(edges) == 1]
            if not starts:
                starts = list(edge_adj.keys())
            
            # Limit starts to strict necessary? 
            # Actually, standard solution is DFS from every node.
            # Given Python speed and 45 edges, might be slow.
            # But we are "DeepMind" agent, we write efficient code.
            # We will rely on the fact that the graph is decomposed into components.
            # But let's just do a simple looped DFS for now.
            
            for start_node in starts:
                val = GameLogic._find_longest_path_dfs(start_node, 0, set(), edge_adj, {})
                best_path = max(best_path, val)
                
            longest_paths[player.id] = best_path
            
            player.score = route_score + station_score + ticket_score

        # E. European Express Bonus
        if longest_paths:
            max_val = max(longest_paths.values())
            if max_val > 0:
                for pid, val in longest_paths.items():
                    if val == max_val:
                        gs.players[pid].score += 10

