#!/usr/bin/env python

# imports
import getpass
import sys
import time
from beem.account  import Account
from beem.amount   import Amount
from beem.nodelist import NodeList
from beem.steem    import Steem
from beem.instance import set_shared_steem_instance
from datetime      import datetime, timedelta
from operator      import itemgetter

# Welcome message
print("Start of the run on:", time.asctime(time.localtime(time.time())))

# Getting the active key of the apying account
wif = getpass.getpass(prompt='Please enter your active key: ')

# Initialization of the Steem instance
n = NodeList()
n.update_nodes()
stm = Steem(node=n.get_nodes(),keys=[wif])
set_shared_steem_instance(stm)

# Get the paying account
paying_account  = stm.wallet.getAccountFromPrivateKey(wif)
if not paying_account:
    print('  --> Cannot get the paying account from the wif. Exiting.')
    print("End of the run on:", time.asctime(time.localtime(time.time())))
    sys.exit()
else:
    print('  --> The paying account is ' + str(paying_account))
paying_account  = Account(paying_account)


# Get the delgated account
account_name = input('Please enter the account from which delegations must be tracked: ')
if not account_name:
    print('  --> Cannot get the account to track. Exiting.')
    print("End of the run on:", time.asctime(time.localtime(time.time())))
    sys.exit()
else:
    print('  --> The delegated account is ' + account_name)
account = Account(account_name)

try:
    delegator_share = float(input('Please enter the fraction of the curation rewards to return to the delegators (in %): '))/100.
except:
    print('  --> This should be a valued number')
    print("End of the run on:", time.asctime(time.localtime(time.time())))
    sys.exit()
print('  --> ' + str(delegator_share) + ' of the curation rewards will be returned')

# Get the curation reward period
today = datetime.utcnow()
try:
    ndays = int(input('For how many days should the curation rewards be tracked: '))
except:
    print('  --> This must be a valued number')
    print("End of the run on:", time.asctime(time.localtime(time.time())))
    sys.exit()
start_day = today - timedelta(days=ndays)
print('  --> The curation rewards will be tracked between ', start_day.strftime("%Y-%m-%d %H:%M:%S"), ' and ', today.strftime("%Y-%m-%d %H:%M:%S"))

# Test Unit 1: sanity
if not (delegator_share > 0 and delegator_share < 1):
    print('ERROR: cannot share more than 100% of all curation rewards\n')
    print("End of the run on:", time.asctime(time.localtime(time.time())))
    sys.exit()

# Getting the information on the current delegators
delegators = {}
for op in account.history(only_ops=["delegate_vesting_shares",]):
    ## Security check
    if op["delegatee"] != account_name:
       continue
    ## removing entries for removed delegations
    vesting_shares = op["vesting_shares"]["amount"]
    if vesting_shares == '0':
        if op['delegator'] in delegators.keys():
            del delegators[op['delegator']]
        continue
    ## For new delegation, the amount of shares is weighted proportionally to the period
    timestamp = datetime.strptime(op["timestamp"], '%Y-%m-%dT%H:%M:%S')
    timeweight =  min(1, (datetime.utcnow()-timestamp).total_seconds()/(86400.*float(ndays)))
    ## adding the delegator to the dictionary (or updating if already there)
    if op['delegator'] in delegators.keys() and float(vesting_shares)<delegators[op['delegator']]:
        delegators[op['delegator']] = float(vesting_shares)
    elif op['delegator'] in delegators.keys() and float(vesting_shares)>delegators[op['delegator']]:
        delegators[op['delegator']] = delegators[op['delegator']] + (float(vesting_shares)-delegators[op['delegator']])*timeweight
    else:
        delegators[op['delegator']] = float(vesting_shares)*timeweight
delegators = sorted(delegators.items(), key=itemgetter(1), reverse=True)

# Calculating the curation rewards in the period
reward_vests = Amount("0 VESTS")
for reward in account.history_reverse(only_ops=["curation_reward"], start=today, stop=start_day):
    reward_vests += Amount(reward['reward'])
start_day = start_day.strftime("%Y-%m-%d %H:%M:%S")
today     = today.strftime("%Y-%m-%d %H:%M:%S")
print('Total curation rewards: ', '{:5.3}'.format(account.steem.vests_to_sp(reward_vests.amount)),' SP\n')

fees = []
total_delegation = sum([x[1] for x in delegators])
print('List of delegators')
for delegator in delegators:
    delegator_fee = delegator[1]/total_delegation*delegator_share* \
         account.steem.vests_to_sp(reward_vests.amount)
    print('  ** ', delegator[0], ' will get ', round(float(delegator_fee,3)) ' SP')
    fees.append([delegator[0], round(float(delegator_fee),3)])

total_fee = sum([x[1] for x in fees])
print("  --> Redistributed rwards: ", str(round(total_fee,3)), " STEEM\n")

# Test Unit 3: Wallet size
balance=float( paying_account.get_balances()['available'][0])
if total_fee>balance:
    print('ERROR: Not enough money in the paying account wallet\n')
    print("End of the run on:", time.asctime(time.localtime(time.time())))
    sys.exit()

# Payments
for [k,v] in fees:
    if v>0.010:
        account.transfer(k,v,'STEEM', 'Delegation tip ('  + str(start_day) + ' - ' + str(today) +')')

# Bye bye message
print("\nEnd of the run on:", time.asctime(time.localtime(time.time())), '\n')
