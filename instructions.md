# TECHNICAL SPECIFICATIONS: TRAIN GAME ENGINE

## 1. Architecture Goal
The engine must be "headless" (pure logic, no GUI) and designed for Reinforcement Learning (RL). 
It must follow the OpenAI Gym/Farama Gymnasium interface style: `observation, reward, terminated, truncated, info = step(action)`.

## 2. Data Management
- **Source:** Use `data/data.json` as the source of truth for the board graph.
- **Graph:** Represent cities as nodes and connections as edges. Store attributes: color, length, is_tunnel, and required_locomotives.
- **State:** The `GameState` must be fully serializable (e.g., to JSON or a NumPy array) so it can be saved and loaded for AI training.

## 3. Class Structure Requirements
- **`CardStack`**: Handles the Wagon deck (110 cards) and Ticket deck. Must include shuffling and discard pile recycling logic.
- **`Player`**: Tracks 45 wagons, 3 stations, cards in hand, and kept tickets.
- **`Engine`**: 
    - `get_legal_moves(player_id)`: Returns a list of all valid actions in the current state.
    - `apply_action(player_id, action)`: Validates and executes the move, updating the state.
    - `calculate_score()`: Implements the full scoring table, including the 10pt European Express bonus.

## 4. Specific Mechanics to Handle
- **Tunnel Logic**: Implementation must handle the "draw 3 cards" risk phase and allow the player to "fail" or "pay extra".
- **Ferry Logic**: Must strictly require the correct number of Locomotives as defined in `data.json`.
- **Double Routes**: In 2-3 player games, ensure that taking one track locks the other.
- **Station Usage**: Implement pathfinding that can "borrow" an opponent's route if a station is present.

## 5. Performance
Code should be optimized for speed to allow running thousands of simulations per second.