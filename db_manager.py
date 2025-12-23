import sqlite3
import datetime
import json


class DBManager:
    def __init__(self, db_name="poker_tracker.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
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
            """
        )

        # 存储与 UI 解耦的、稳定的 replay JSON
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS hand_replay (
                hand_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        
        # Migrate old database: add insurance_premium column if it doesn't exist
        cursor.execute("PRAGMA table_info(hands)")
        columns = [col[1] for col in cursor.fetchall()]
        if "insurance_premium" not in columns:
            cursor.execute(
                "ALTER TABLE hands ADD COLUMN insurance_premium REAL DEFAULT 0"
            )
            self.conn.commit()
        
        # Migrate old database: add jackpot column if it doesn't exist
        if "jackpot" not in columns:
            cursor.execute(
                "ALTER TABLE hands ADD COLUMN jackpot REAL DEFAULT 0"
            )
            self.conn.commit()
        
        # 旧版曾经有 raw_data 列（已废弃），这里保持兼容，不再使用
        
        self.conn.commit()

    # --- Hand replay JSON -------------------------------------------------
    def _build_replay_payload(self, hand):
        """
        从 PokerHand 构造稳定的 replay JSON 结构。
        该结构尽量只使用基础类型，避免与代码实现强耦合。
        
        注意：这个函数应该只依赖于 hand 对象中已经解析好的数据，
        不应该依赖外部状态或代码实现细节。
        """
        # players_info: {seat_num: {name, chips_start, hole_cards}}
        players = []
        for seat, info in sorted(getattr(hand, "players_info", {}).items()):
            players.append(
                {
                    "seat": int(seat),
                    "name": info.get("name"),
                    "stack_start": float(info.get("chips_start", 0.0) or 0.0),
                    "hole_cards": info.get("hole_cards") or "",
                }
            )

        # 确保 actions 中的数值都是基础类型，不包含复杂对象
        actions = []
        for act in getattr(hand, "actions", []):
            # 只提取基础类型字段，确保序列化稳定
            clean_act = {
                "street": act.get("street", ""),
                "player": act.get("player", ""),
                "action_type": act.get("action_type", ""),
                "amount": float(act.get("amount", 0.0) or 0.0),
                "to_amount": float(act.get("to_amount", 0.0) or 0.0) if act.get("to_amount") is not None else None,
                "is_all_in": bool(act.get("is_all_in", False)),
                "pot_size": float(act.get("pot_size", 0.0) or 0.0),
            }
            # run-it-twice / split related extras (optional)
            if act.get("run") is not None:
                try:
                    clean_act["run"] = int(act.get("run"))
                except Exception:
                    clean_act["run"] = act.get("run")
            if act.get("board_run") is not None:
                try:
                    clean_act["board_run"] = int(act.get("board_run"))
                except Exception:
                    clean_act["board_run"] = act.get("board_run")
            if act.get("board_cards") is not None:
                bc = act.get("board_cards") or []
                if isinstance(bc, (list, tuple)):
                    clean_act["board_cards"] = [str(x) for x in bc]
                else:
                    clean_act["board_cards"] = []
            actions.append(clean_act)

        payload = {
            "hand_id": hand.hand_id,
            "date_time": hand.date_time.strftime("%Y-%m-%d %H:%M:%S")
            if hand.date_time
            else None,
            "game_type": hand.game_type,
            "blinds": hand.blinds,
            "hero_name": hand.hero_name,
            "hero_seat": hand.hero_seat,
            "hero_hole_cards": hand.hero_hole_cards,
            "button_seat": getattr(hand, "button_seat", 0),
            "total_pot": float(hand.total_pot or 0.0),
            "rake": float(hand.rake or 0.0),
            "jackpot": float(getattr(hand, "jackpot", 0.0) or 0.0),
            "net_profit": float(hand.net_profit or 0.0),
            "went_to_showdown": 1 if getattr(hand, "went_to_showdown", False) else 0,
            "players": players,
            "board_cards": getattr(hand, "board_cards", []),
            "actions": actions,  # 使用清理后的 actions
        }
        return payload

    def save_replay(self, hand, version: int = 4):
        """
        将 hand 的完整回放信息以 JSON 形式保存/更新到 hand_replay 表。
        
        版本说明：
        - version 1: 初始版本
        - version 2: 修正 pot 计算逻辑后的版本（确保 actions 中的 pot_size 正确）
        - version 3: 支持 run-it-twice（FIRST/SECOND board）节点与 run 标记
        - version 4: 街道切换插入 pot_complete（all-in/runout 时 pot 可见），并优化 split pot 展示
        
        每次代码更新导致 replay 数据结构变化时，应该增加版本号。
        旧版本的数据会在下次导入时自动更新。
        """
        try:
            payload = self._build_replay_payload(hand)
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO hand_replay (hand_id, version, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(hand_id) DO UPDATE SET
                    version = excluded.version,
                    payload = excluded.payload
                """,
                (hand.hand_id, version, json.dumps(payload, ensure_ascii=False)),
            )
            self.conn.commit()
        except Exception as e:
            # 回放数据不是核心统计指标，失败时打印日志但不影响主流程
            print(f"Error saving replay payload for hand {hand.hand_id}: {e}")

    def get_replay_payload(self, hand_id, min_version: int = 2):
        """
        从 hand_replay 表中读取 replay JSON。
        
        参数:
            hand_id: 手牌 ID
            min_version: 最低要求的版本号，如果数据库中的版本低于此版本，返回 None
        
        返回 dict 或 None。
        如果版本不匹配，返回 None，让系统重新解析并保存。
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT version, payload FROM hand_replay WHERE hand_id = ?", (hand_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        try:
            db_version = row[0]
            if db_version >= min_version:
                return json.loads(row[1])
            else:
                # 版本不匹配，返回 None，让系统重新解析
                print(f"Replay data for hand {hand_id} is version {db_version}, but requires {min_version}. Will re-parse.")
                return None
        except json.JSONDecodeError:
            return None

    def add_hand(self, hand):
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO hands (
                    hand_id, date_time, blinds, game_type, hero_hole_cards,
                    profit, rake, total_pot, insurance_premium, jackpot,
                                   showdown_winnings, non_showdown_winnings, 
                    went_to_showdown, is_all_in, all_in_ev
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                hand.hand_id,
                    hand.date_time.strftime("%Y-%m-%d %H:%M:%S")
                    if hand.date_time
                    else None,
                hand.blinds,
                hand.game_type,
                hand.hero_hole_cards,
                hand.net_profit,
                hand.rake,
                hand.total_pot,
                hand.insurance_premium,
                    hand.jackpot,
                hand.showdown_winnings,
                hand.non_showdown_winnings,
                1 if hand.went_to_showdown else 0,
                1 if hand.is_all_in else 0,
                    hand.all_in_ev,
                ),
            )
            self.conn.commit()

            # 保存/更新回放 JSON（不影响统计功能）
            self.save_replay(hand, version=4)
            return True # Success (New Hand)
        except sqlite3.IntegrityError:
            # Duplicate hand_id - 但可能 replay 数据需要更新（版本不匹配）
            # 检查并更新 replay 数据
            existing_payload = self.get_replay_payload(hand.hand_id, min_version=4)
            if existing_payload is None:
                # 版本不匹配或不存在，更新 replay 数据
                self.save_replay(hand, version=4)
                print(f"Updated replay data for existing hand {hand.hand_id}")
            return False # Duplicate (but replay may have been updated)
        except Exception as e:
            print(f"Error adding hand {hand.hand_id}: {e}")
            return False # Error

    def get_all_hands(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM hands ORDER BY date_time')
        return cursor.fetchall()

    def get_hands_in_range(self, start_date=None, end_date=None):
        """
        返回按日期范围过滤后的 hands 记录，用于 Dashboard summary 与图表保持一致。
        """
        cursor = self.conn.cursor()
        query = 'SELECT * FROM hands'
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

