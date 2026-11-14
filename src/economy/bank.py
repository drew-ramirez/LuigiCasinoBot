class Bank:
    def __init__(self):
        self._balances: dict[int, int] = {}

    def balance(self, user_id: int) -> int:
        return self._balances.get(user_id, 0)

    def grant(self, user_id: int, amount: int) -> int:
        self._balances[user_id] = self.balance(user_id) + amount
        return self._balances[user_id]

    def wager(self, user_id: int, amount: int) -> bool:
        if self.balance(user_id) < amount:
            return False
        self._balances[user_id] -= amount
        return True

    def payout(self, user_id: int, amount: int) -> int:
        return self.grant(user_id, amount)
