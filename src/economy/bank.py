class Bank:
    def __init__(self):
        # Store balances keyed by user_id
        self._balances: dict[int, int] = {}

    def balance(self, user_id: int) -> int:
        #Return current balance, or 0 if new
        return self._balances.get(user_id, 0)

    def grant(self, user_id: int, amount: int) -> int:
        #Add coins to user balance.
        self._balances[user_id] = self.balance(user_id) + amount
        return self._balances[user_id]

    def wager(self, user_id: int, amount: int) -> bool:
        #Try to subtract coins for a bet.
        if self.balance(user_id) < amount:
            return False
        self._balances[user_id] -= amount
        return True

    def payout(self, user_id: int, amount: int) -> int:
        #Pay winnings into balance.
        return self.grant(user_id, amount)
