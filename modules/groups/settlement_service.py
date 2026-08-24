from decimal import Decimal, ROUND_HALF_UP

def simplify_debts(net_balances):
    """
    Minimum Transaction Debt Simplification Algorithm (Greedy Min-Cash-Flow).
    
    Parameters:
        net_balances: dict of {user_id: {'name': str, 'balance': float/Decimal}}
                      Positive balance = User should RECEIVE money (Creditor)
                      Negative balance = User OWES money (Debtor)
                      Zero balance = Settled
                      
    Returns:
        dict containing:
            - settlements: list of dicts [{'payer_id', 'payer_name', 'receiver_id', 'receiver_name', 'amount'}]
            - original_debt_count: int
            - simplified_count: int
            - transactions_saved: int
    """
    creditors = [] # (user_id, name, amount) where amount > 0
    debtors = []   # (user_id, name, amount) where amount > 0 (absolute debt)
    
    for uid, data in net_balances.items():
        # Round to 2 decimal places to avoid floating point precision artifacts
        bal = Decimal(str(round(data['balance'], 2)))
        name = data.get('name', f'User #{uid}')
        
        if bal > Decimal('0.00'):
            creditors.append({'id': uid, 'name': name, 'amount': bal})
        elif bal < Decimal('0.00'):
            debtors.append({'id': uid, 'name': name, 'amount': abs(bal)})

    simplified_settlements = []

    # Sort creditors descending by amount, debtors descending by debt amount
    creditors.sort(key=lambda x: x['amount'], reverse=True)
    debtors.sort(key=lambda x: x['amount'], reverse=True)

    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]

        # Ignore minuscule amounts less than 1 paisa (0.01)
        if debtor['amount'] < Decimal('0.01'):
            i += 1
            continue
        if creditor['amount'] < Decimal('0.01'):
            j += 1
            continue

        settle_amt = min(debtor['amount'], creditor['amount'])
        
        if settle_amt >= Decimal('0.01'):
            simplified_settlements.append({
                'payer_id': debtor['id'],
                'payer_name': debtor['name'],
                'receiver_id': creditor['id'],
                'receiver_name': creditor['name'],
                'amount': float(settle_amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            })

        debtor['amount'] -= settle_amt
        creditor['amount'] -= settle_amt

        if debtor['amount'] < Decimal('0.01'):
            i += 1
        if creditor['amount'] < Decimal('0.01'):
            j += 1

    # Original debt count estimation: up to N*(N-1)/2 pairwise debts
    total_active_members = len(creditors) + len(debtors)
    original_debt_count = max(len(debtors) * len(creditors), len(simplified_settlements))
    simplified_count = len(simplified_settlements)
    saved = max(0, original_debt_count - simplified_count)

    return {
        'settlements': simplified_settlements,
        'original_debt_count': original_debt_count,
        'simplified_count': simplified_count,
        'transactions_saved': saved
    }
