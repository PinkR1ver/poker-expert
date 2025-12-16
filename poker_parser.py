import re
import datetime

class PokerHand:
    def __init__(self):
        self.hand_id = ""
        self.date_time = None
        self.hero_seat = 0
        self.hero_name = "Hero"
        self.hero_hole_cards = ""
        self.total_pot = 0.0
        self.rake = 0.0
        self.jackpot = 0.0
        self.hero_wagered = 0.0
        self.hero_collected = 0.0
        self.insurance_premium = 0.0  # All-in Insurance premium paid by Hero
        self.net_profit = 0.0
        self.blinds = ""
        self.game_type = ""
        
        # Graph analysis data
        self.went_to_showdown = False  # Did hero go to showdown?
        self.showdown_winnings = 0.0   # Money won at showdown (can be negative)
        self.non_showdown_winnings = 0.0  # Money won without showdown (can be negative)
        self.is_all_in = False  # Was hero all-in at any point?
        self.is_all_in_showdown = False  # Was this an all-in that went to showdown?
        self.all_in_ev = 0.0  # Expected value when all-in
        self.all_in_street = ""  # Street when all-in happened (for EV calculation)
        self.all_in_pot = 0.0  # Pot size at all-in moment
        self.villain_cards = ""  # Opponent's hole cards shown at showdown
        self.showdown_players = {}  # {player_name: hole_cards} for all players who showed
        
        # EV calculation data
        self.board_at_allin = []  # Board cards when all-in happened (for EV calculation)
        
    def __str__(self):
        return f"Hand: {self.hand_id} | Date: {self.date_time} | Profit: {self.net_profit:.2f} | Pot: {self.total_pot} | Rake: {self.rake}"

def parse_file(filepath):
    hands = []
    current_lines = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() == "":
                if current_lines:
                    hand = parse_hand(current_lines)
                    if hand:
                        hands.append(hand)
                    current_lines = []
            else:
                current_lines.append(line.strip())
                
    if current_lines:
        hand = parse_hand(current_lines)
        if hand:
            hands.append(hand)
            
    return hands

def parse_hand(lines):
    hand = PokerHand()
    
    # Hero wager tracking
    street_wagers = {'Preflop': 0.0, 'Flop': 0.0, 'Turn': 0.0, 'River': 0.0}
    current_street = 'Preflop'
    street_committed = {} # player -> amount committed in current street
    
    # Track current board for EV calculation (not stored in hand)
    current_board = []
    
    # Regex patterns
    re_hand_info = re.compile(r"Poker Hand #([^:]+): (.*?) \((.*?)\) - (.*)")
    re_table_info = re.compile(r"Table '(.*?)' 6-max Seat #(\d+) is the button")
    re_seat = re.compile(r"Seat (\d+): (.*) \(\$(\d+(\.\d+)?) in chips\)")
    re_post = re.compile(r"(.*?): posts (small|big|straddle) blind \$(\d+(\.\d+)?)")
    re_dealt = re.compile(r"Dealt to (.*) \[(.*)\]")
    re_street = re.compile(r"\*\*\* (FLOP|TURN|RIVER) \*\*\* (\[.*?\])(?: (\[.*?\]))?")
    re_action_bet_call = re.compile(r"(.*?): (bets|calls|checks|folds) ?\$?(\d+(\.\d+)?)?")
    re_action_raise = re.compile(r"(.*?): raises \$(\d+(\.\d+)?) to \$(\d+(\.\d+)?)")
    re_uncalled = re.compile(r"Uncalled bet \(\$(\d+(\.\d+)?)\) returned to (.*)")
    re_collected = re.compile(r"(.*) collected \$(\d+(\.\d+)?) from pot")
    re_summary_pot = re.compile(r"Total pot \$(\d+(\.\d+)?) \| Rake \$(\d+(\.\d+)?)")
    re_summary_jackpot = re.compile(r"Jackpot \$(\d+(\.\d+)?)")
    re_showdown = re.compile(r"\*\*\* SHOW DOWN \*\*\*")
    re_shows = re.compile(r"(.*?): shows \[(.*?)\]")
    re_insurance = re.compile(r"(.*?): Pays All-in Insurance premium \(\$(\d+(\.\d+)?)\)")
    re_allin = re.compile(r"(.*?) and is all-in")
    
    for line in lines:
        # Hand Info
        m = re_hand_info.match(line)
        if m:
            hand.hand_id = m.group(1)
            hand.game_type = m.group(2)
            hand.blinds = m.group(3)
            # Date parsing might need adjustment based on format
            try:
                hand.date_time = datetime.datetime.strptime(m.group(4), "%Y/%m/%d %H:%M:%S")
            except:
                pass
            continue
            
        # Table Info (Button) - Skip
        m = re_table_info.match(line)
        if m:
            continue

        # Street change
        m = re_street.match(line)
        if m:
            street_name = m.group(1).title() # Flop, Turn, River
            
            # GGPoker format:
            # FLOP: *** FLOP *** [Ah Kd Qc] - 3 new cards
            # TURN: *** TURN *** [Ah Kd Qc] [Js] - only [Js] is new
            # RIVER: *** RIVER *** [Ah Kd Qc Js] [Th] - only [Th] is new
            if street_name == 'Flop':
                # Flop has 3 cards in first bracket
                cards = m.group(2).replace('[', '').replace(']', '')
            else:
                # Turn/River: new card is in second bracket
                if m.group(3):
                    cards = m.group(3).replace('[', '').replace(']', '')
                else:
                    cards = ""
            
            if cards:
                current_board.extend(cards.split())
            
            current_street = street_name
            street_committed = {} # Reset for new street
            continue
            
        # Seats
        m = re_seat.match(line)
        if m:
            seat_num = int(m.group(1))
            player_name = m.group(2)
            chips = float(m.group(3))
            
            if player_name == hand.hero_name:
                hand.hero_seat = seat_num
            continue
            
        # Hole Cards
        m = re_dealt.match(line)
        if m:
            if m.group(1) == hand.hero_name:
                hand.hero_hole_cards = m.group(2)
            continue
            
        # Actions - Post Blinds
        m = re_post.match(line)
        if m:
            player = m.group(1)
            action_type = m.group(2)
            amount = float(m.group(3))
            
            if player == hand.hero_name:
                hand.hero_wagered += amount
                # Blinds count as preflop commit
                street_committed[player] = street_committed.get(player, 0.0) + amount
            continue
            
        # Actions - Bet/Call/Check/Fold
        m = re_action_bet_call.match(line)
        if m:
            player = m.group(1)
            action = m.group(2)
            amount = float(m.group(3)) if m.group(3) else 0.0
            
            if action in ['bets', 'calls']:
                if player == hand.hero_name:
                    hand.hero_wagered += amount
                    street_committed[player] = street_committed.get(player, 0.0) + amount
                
                # Check for all-in in bet/call
                if "and is all-in" in line:
                    if player == hand.hero_name:
                        if not hand.is_all_in:  # Only set once
                            hand.is_all_in = True
                            hand.all_in_street = current_street
                            hand.board_at_allin = list(current_board)  # Copy current board
                    else:
                        if not hasattr(hand, '_someone_allin'):
                            hand._someone_allin = True
                            hand._allin_street = current_street
                            hand._allin_board = list(current_board)
                
                # Hero calls after someone went all-in
                if action == 'calls' and player == hand.hero_name:
                    if hasattr(hand, '_someone_allin') and hand._someone_allin and not hand.is_all_in:
                        hand.is_all_in = True
                        hand.all_in_street = hand._allin_street
                        hand.board_at_allin = list(hand._allin_board) if hasattr(hand, '_allin_board') else list(current_board)
            continue
            
        # Actions - Raise
        m = re_action_raise.match(line)
        if m:
            player = m.group(1)
            raise_amount = float(m.group(2))
            raise_to = float(m.group(4))
            
            if player == hand.hero_name:
                prev_commit = street_committed.get(player, 0.0)
                increment = raise_to - prev_commit
                if increment > 0:
                    hand.hero_wagered += increment
                    street_committed[player] = raise_to
            
            # Check for all-in in this raise
            if "and is all-in" in line:
                if player == hand.hero_name:
                    if not hand.is_all_in:  # Only set once
                        hand.is_all_in = True
                        hand.all_in_street = current_street
                        hand.board_at_allin = list(current_board)
                else:
                    if not hasattr(hand, '_someone_allin'):
                        hand._someone_allin = True
                        hand._allin_street = current_street
                        hand._allin_board = list(current_board)
            continue
            
        # Uncalled Bet Returned
        m = re_uncalled.match(line)
        if m:
            amount = float(m.group(1))
            player = m.group(3)
            if player == hand.hero_name:
                hand.hero_wagered -= amount
            continue
            
        # Collected
        m = re_collected.match(line)
        if m:
            player = m.group(1)
            amount = float(m.group(2))
            if player == hand.hero_name:
                hand.hero_collected += amount
            continue
        
        # Insurance Premium
        m = re_insurance.match(line)
        if m:
            player = m.group(1)
            premium = float(m.group(2))
            if player == hand.hero_name:
                hand.insurance_premium = premium
            continue
            
        # Showdown detection
        m = re_showdown.match(line)
        if m:
            hand.went_to_showdown = True
            current_street = 'Showdown'
            continue
            
        # Player shows cards (also indicates showdown)
        m = re_shows.match(line)
        if m:
            player = m.group(1)
            cards = m.group(2)
            hand.went_to_showdown = True
            hand.showdown_players[player] = cards
            
            # Track villain cards for EV calculation
            if player != hand.hero_name and not hand.villain_cards:
                hand.villain_cards = cards
            continue
            
        # All-in detection
        # Track when any player goes all-in
        if "and is all-in" in line:
            player_match = re.match(r"(.*?):", line)
            if player_match:
                player = player_match.group(1)
                # If Hero goes all-in
                if player == hand.hero_name:
                    hand.is_all_in = True
                    if not hand.all_in_street:
                        hand.all_in_street = current_street
                        hand.board_at_allin = current_board.copy()
                else:
                    # Someone else went all-in, mark it for tracking
                    if not hasattr(hand, '_someone_allin'):
                        hand._someone_allin = True
                        hand._allin_street = current_street
                        hand._allin_board = current_board.copy()
        
        # Hero calls (potentially calling an all-in)
        # This handles: "Hero: calls $X.XX" after someone went all-in
        if line.startswith(f"{hand.hero_name}: calls"):
            if hasattr(hand, '_someone_allin') and hand._someone_allin:
                hand.is_all_in = True
                if not hand.all_in_street:
                    hand.all_in_street = hand._allin_street
                    hand.board_at_allin = hand._allin_board.copy() if hasattr(hand, '_allin_board') else current_board.copy()

        # Summary Pot/Rake
        m = re_summary_pot.search(line)
        if m:
            hand.total_pot = float(m.group(1))
            hand.rake = float(m.group(3))
            
            m_jack = re_summary_jackpot.search(line)
            if m_jack:
                hand.jackpot = float(m_jack.group(1))
            continue

    # Calculate net profit (subtract insurance premium if any)
    hand.net_profit = hand.hero_collected - hand.hero_wagered - hand.insurance_premium
    
    # Categorize winnings: Showdown vs Non-Showdown
    if hand.went_to_showdown:
        hand.showdown_winnings = hand.net_profit
        hand.non_showdown_winnings = 0.0
    else:
        hand.showdown_winnings = 0.0
        hand.non_showdown_winnings = hand.net_profit
    
    # Calculate All-in EV
    hand.is_all_in_showdown = hand.is_all_in and hand.went_to_showdown
    
    if hand.is_all_in_showdown and hand.hero_hole_cards and hand.villain_cards:
        # We have an all-in showdown with both players' cards known
        try:
            from equity_calculator import calculate_equity, parse_cards
            
            hero_cards = parse_cards(hand.hero_hole_cards)
            villain_cards = parse_cards(hand.villain_cards)
            board = parse_cards(' '.join(hand.board_at_allin))
            
            if hero_cards and villain_cards:
                equity = calculate_equity(hero_cards, villain_cards, board, num_simulations=2000)
                
                # EV = (Total Pot × Equity) - Hero's Investment
                # Note: total_pot includes rake, we use it as approximate
                expected_win = hand.total_pot * equity
                hand.all_in_ev = expected_win - hand.hero_wagered
            else:
                hand.all_in_ev = hand.net_profit
        except Exception as e:
            # Fallback to actual profit if calculation fails
            hand.all_in_ev = hand.net_profit
    else:
        # For non all-in hands, EV = actual profit
        hand.all_in_ev = hand.net_profit
    
    return hand

if __name__ == "__main__":
    import sys
    import glob
    
    # Test with all files
    test_files = glob.glob("dev-doc/ggpoker-history-record/*.txt")
    
    all_hands = []
    for f in test_files:
        all_hands.extend(parse_file(f))
    
    print(f"Parsed {len(all_hands)} hands from {len(test_files)} files.")
    
    total_profit = 0
    total_rake = 0
    total_ev = 0
    all_in_count = 0
    
    for h in all_hands:
        total_profit += h.net_profit
        total_rake += h.rake
        total_ev += h.all_in_ev
        
        if h.is_all_in_showdown:
            all_in_count += 1
            ev_diff = h.net_profit - h.all_in_ev
            luck = "运气好" if ev_diff > 0 else "运气差" if ev_diff < 0 else "正常"
            print(f"All-in: {h.hand_id}")
            print(f"  Hero: {h.hero_hole_cards} vs Villain: {h.villain_cards}")
            print(f"  Board at all-in: {' '.join(h.board_at_allin)}")
            print(f"  Profit: ${h.net_profit:.2f}, EV: ${h.all_in_ev:.2f}, Diff: ${ev_diff:.2f} ({luck})")
            print()
        
    print(f"\n=== Summary ===")
    print(f"Total Hands: {len(all_hands)}")
    print(f"All-in Showdowns: {all_in_count}")
    print(f"Total Profit: ${total_profit:.2f}")
    print(f"Total EV: ${total_ev:.2f}")
    print(f"Luck Factor: ${total_profit - total_ev:.2f}")
    print(f"Total Rake: ${total_rake:.2f}")

