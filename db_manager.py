import sqlite3
import datetime

class DBManager:
    def __init__(self, db_name="poker_tracker.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hands (
                hand_id TEXT PRIMARY KEY,
                date_time TEXT,
                blinds TEXT,
                game_type TEXT,
                hero_hole_cards TEXT,
                profit REAL,
                rake REAL,
                total_pot REAL,
                insurance_premium REAL DEFAULT 0,
                showdown_winnings REAL DEFAULT 0,
                non_showdown_winnings REAL DEFAULT 0,
                went_to_showdown INTEGER DEFAULT 0,
                is_all_in INTEGER DEFAULT 0,
                all_in_ev REAL DEFAULT 0
            )
        ''')
        
        # Migrate old database: add insurance_premium column if it doesn't exist
        cursor.execute("PRAGMA table_info(hands)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'insurance_premium' not in columns:
            cursor.execute('ALTER TABLE hands ADD COLUMN insurance_premium REAL DEFAULT 0')
            self.conn.commit()
        
        # Remove old raw_data column if it exists (from replayer)
        # SQLite doesn't support DROP COLUMN directly, so we'll just ignore it
        # It won't affect queries since we don't use it anymore
        
        self.conn.commit()

    def add_hand(self, hand):
        cursor = self.conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO hands (hand_id, date_time, blinds, game_type, hero_hole_cards, 
                                   profit, rake, total_pot, insurance_premium,
                                   showdown_winnings, non_showdown_winnings, 
                                   went_to_showdown, is_all_in, all_in_ev)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hand.hand_id,
                hand.date_time.strftime("%Y-%m-%d %H:%M:%S") if hand.date_time else None,
                hand.blinds,
                hand.game_type,
                hand.hero_hole_cards,
                hand.net_profit,
                hand.rake,
                hand.total_pot,
                hand.insurance_premium,
                hand.showdown_winnings,
                hand.non_showdown_winnings,
                1 if hand.went_to_showdown else 0,
                1 if hand.is_all_in else 0,
                hand.all_in_ev
            ))
            self.conn.commit()
            return True # Success (New Hand)
        except sqlite3.IntegrityError:
            # Duplicate hand_id
            return False # Duplicate
        except Exception as e:
            print(f"Error adding hand {hand.hand_id}: {e}")
            return False # Error

    def get_all_hands(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM hands ORDER BY date_time')
        return cursor.fetchall()

    def get_cumulative_profit(self, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        
        query = 'SELECT date_time, profit FROM hands'
        params = []
        
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append('date_time >= ?')
                params.append(start_date)
            if end_date:
                conditions.append('date_time <= ?')
                params.append(end_date)
            query += ' WHERE ' + ' AND '.join(conditions)
            
        query += ' ORDER BY date_time'
        
        cursor.execute(query, params)
        data = cursor.fetchall()
        
        dates = []
        profits = []
        cumulative = 0.0
        
        for row in data:
            if row[0]:
                dates.append(row[0])
                cumulative += row[1]
                profits.append(cumulative)
                
        return dates, profits

    def get_graph_data(self, start_date=None, end_date=None):
        """
        Returns comprehensive graph data:
        - dates: timestamp for each hand
        - net_won: cumulative net profit (green line)
        - showdown_won: cumulative showdown winnings (blue line)  
        - non_showdown_won: cumulative non-showdown winnings (red line)
        - all_in_ev: cumulative all-in EV (orange line)
        """
        cursor = self.conn.cursor()
        
        query = '''SELECT date_time, profit, showdown_winnings, non_showdown_winnings, all_in_ev 
                   FROM hands'''
        params = []
        
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append('date_time >= ?')
                params.append(start_date)
            if end_date:
                conditions.append('date_time <= ?')
                params.append(end_date)
            query += ' WHERE ' + ' AND '.join(conditions)
            
        query += ' ORDER BY date_time'
        
        cursor.execute(query, params)
        data = cursor.fetchall()
        
        dates = []
        net_won = []
        showdown_won = []
        non_showdown_won = []
        all_in_ev = []
        
        cum_net = 0.0
        cum_sd = 0.0
        cum_nsd = 0.0
        cum_ev = 0.0
        
        for row in data:
            if row[0]:
                dates.append(row[0])
                
                profit = row[1] or 0.0
                sd_win = row[2] or 0.0
                nsd_win = row[3] or 0.0
                ev = row[4] or 0.0
                
                cum_net += profit
                cum_sd += sd_win
                cum_nsd += nsd_win
                cum_ev += ev
                
                net_won.append(cum_net)
                showdown_won.append(cum_sd)
                non_showdown_won.append(cum_nsd)
                all_in_ev.append(cum_ev)
                
        return {
            'dates': dates,
            'net_won': net_won,
            'showdown_won': showdown_won,
            'non_showdown_won': non_showdown_won,
            'all_in_ev': all_in_ev
        }

    def close(self):
        self.conn.close()

