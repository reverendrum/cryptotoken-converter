"""
**Copyright**::

    +===================================================+
    |                 © 2019 Privex Inc.                |
    |               https://www.privex.io               |
    +===================================================+
    |                                                   |
    |        CryptoToken Converter                      |
    |                                                   |
    |        Core Developer(s):                         |
    |                                                   |
    |          (+)  Chris (@someguy123) [Privex]        |
    |                                                   |
    +===================================================+

"""
import logging
from decimal import Decimal, getcontext, ROUND_DOWN
from typing import Tuple, List

from beem.account import Account
from beem.exceptions import AccountDoesNotExistsException, MissingKeyError

from payments.coin_handlers import BaseManager
from payments.coin_handlers.Steem.SteemLoader import SteemLoader
from payments.coin_handlers.Steem.SteemMixin import SteemMixin
from payments.coin_handlers.base import exceptions
from steemengine.helpers import empty

log = logging.getLogger(__name__)
getcontext().rounding = ROUND_DOWN


class SteemManager(BaseManager, SteemMixin):
    """
    This class handles various operations for the **Steem** network, and supports both STEEM and SBD.

    It may or may not work with other Graphene coins, such as GOLOS / Whaleshares.

    It handles:

    - Validating source/destination accounts
    - Checking the balance for a given account, as well as the total amount received with a certain ``memo``
    - Health checking
    - Sending assets to users

    **Copyright**::

        +===================================================+
        |                 © 2019 Privex Inc.                |
        |               https://www.privex.io               |
        +===================================================+
        |                                                   |
        |        CryptoToken Converter                      |
        |                                                   |
        |        Core Developer(s):                         |
        |                                                   |
        |          (+)  Chris (@someguy123) [Privex]        |
        |                                                   |
        +===================================================+

    """

    provides = ["STEEM", "SBD"]  # type: List[str]
    """
    This attribute is automatically generated by scanning for :class:`models.Coin` s with the type ``steembase``. 
    This saves us from hard coding specific coin symbols. See __init__.py for populating code.
    """

    def __init__(self, symbol: str):
        super(SteemManager, self).__init__(symbol)
        self._rpc = self._asset = self._precision = None
        self._rpcs = {}

    def health(self) -> Tuple[str, tuple, tuple]:
        """
        Return health data for the passed symbol.

        Health data will include: 'Symbol', 'Status', 'Coin Name', 'API Node', 'Head Block', 'Block Time',
        'RPC Version', 'Our Account', 'Our Balance' (all strings)

        :return tuple health_data: (manager_name:str, headings:list/tuple, health_data:list/tuple,)
        """
        headers = ('Symbol', 'Status', 'Coin Name', 'API Node', 'Head Block', 'Block Time', 'RPC Version',
                   'Our Account', 'Our Balance')

        class_name = type(self).__name__
        api_node = asset_name = head_block = block_time = rpc_ver = our_account = balance = ''

        status = 'Okay'
        try:
            rpc = self.rpc
            our_account = self.coin.our_account
            if not self.address_valid(our_account):
                status = 'Account {} not found'.format(our_account)

            asset_name = self.coin.display_name
            balance = ('{0:,.' + str(self.precision) + 'f}').format(self.balance(our_account))
            api_node = rpc.rpc.url
            props = rpc.get_dynamic_global_properties(use_stored_data=False)
            head_block = str(props.get('head_block_number', ''))
            block_time = props.get('time', '')
            rpc_ver = rpc.get_blockchain_version()
        except:
            status = 'ERROR'
            log.exception('Exception during %s.health for symbol %s', class_name, self.symbol)

        if status == 'Okay':
            status = '<b style="color: green">{}</b>'.format(status)
        else:
            status = '<b style="color: red">{}</b>'.format(status)

        data = (self.symbol, status, asset_name, api_node, head_block, block_time, rpc_ver, our_account, balance)
        return class_name, headers, data

    def health_test(self) -> bool:
        """
        Check if our Steem node works or not, by requesting basic information such as the current block + time, and
        checking if our sending/receiving account exists on Steem.

        :return bool: True if Steem appearsto be working, False if it seems to be broken.
        """
        try:
            _, _, health_data = self.health()
            if 'Okay' in health_data[1]:
                return True
            return False
        except:
            return False

    def address_valid(self, address) -> bool:
        """
        If an account exists on Steem, will return True. Otherwise False.

        :param address: Steem account to check existence of
        :return bool: True if account exists, False if it doesn't
        """
        try:
            Account(address, steem_instance=self.rpc)
            return True
        except AccountDoesNotExistsException:
            return False

    def get_deposit(self) -> tuple:
        """
        Returns the deposit account for this symbol

        :return tuple: A tuple containing ('account', receiving_account). The memo must be generated
                       by the calling function.
        """

        return 'account', self.coin.our_account

    def balance(self, address: str = None, memo: str = None, memo_case: bool = False) -> Decimal:
        """
        Get token balance for a given Steem account, if memo is given - get total symbol amt received with this memo.

        :param address:    Steem account to get balance for, if not set, uses self.coin.our_account
        :param memo:       If not None, get total `self.symbol` received with this memo.
        :param memo_case:  Case sensitive memo search
        :return: Decimal(balance)
        """
        if not address:
            address = self.coin.our_account

        acc = Account(address, steem_instance=self.rpc)

        if not empty(memo):
            hist = acc.get_account_history(-1, 10000, only_ops=['transfer'])
            total = Decimal(0)
            s = SteemLoader(symbols=[self.symbol])
            for h in hist:
                tx = s.clean_tx(h, self.symbol, address, memo)
                if tx is None:
                    continue
                total += tx['amount']
            return total

        bal = acc.get_balance('available', self.symbol)
        return Decimal(bal.amount)

    def send(self, amount: Decimal, address: str, from_address: str = None, memo=None, trigger_data=None) -> dict:
        """
        Send a supported currency to a given address/account, optionally specifying a memo if supported

        Example - send 1.23 STEEM from @someguy123 to @privex with memo 'hello'

            >>> s = SteemManager('STEEM')
            >>> s.send(from_address='someguy123', address='privex', amount=Decimal('1.23'), memo='hello')

        :param Decimal amount:      Amount of currency to send, as a Decimal()
        :param address:             Account to send the currency to
        :param from_address:        Account to send the currency from
        :param memo:                Memo to send currency with
        :raises AttributeError:     When both `from_address` and `self.coin.our_account` are blank.
        :raises ArithmeticError:    When the amount is lower than the lowest amount allowed by the asset's precision
        :raises AuthorityMissing:   Cannot send because we don't have authority to (missing key etc.)
        :raises AccountNotFound:    The requested account doesn't exist
        :raises NotEnoughBalance:   The account `from_address` does not have enough balance to send this amount.
        :return dict: Result Information

        Format::

          {
              txid:str - Transaction ID - None if not known,
              coin:str - Symbol that was sent,
              amount:Decimal - The amount that was sent (after fees),
              fee:Decimal    - TX Fee that was taken from the amount,
              from:str       - The account/address the coins were sent from,
              send_type:str       - Should be statically set to "send"
          }

        """

        # Try from_address first. If that's empty, try using self.coin.our_account. If both are empty, abort.
        if empty(from_address):
            if empty(self.coin.our_account):
                raise AttributeError("Both 'from_address' and 'coin.our_account' are empty. Cannot send.")
            from_address = self.coin.our_account

        prec = self.precision
        sym = self.symbol
        memo = "" if empty(memo) else memo

        try:
            if type(amount) != Decimal:
                if type(amount) == float:
                    amount = ('{0:.' + str(self.precision) + 'f}').format(amount)
                amount = Decimal(amount)
            ###
            # Various sanity checks, e.g. checking amount is valid, to/from account are valid, we have
            # enough balance to send this amt, etc.
            ###
            if amount < Decimal(pow(10, -prec)):
                log.warning('Amount %s was passed, but is lower than precision for %s', amount, sym)
                raise ArithmeticError('Amount {} is lower than token {}s precision of {} DP'.format(amount, sym, prec))

            acc = Account(from_address, steem_instance=self.rpc)

            if not self.address_valid(address): raise exceptions.AccountNotFound('Destination account does not exist')
            if not self.address_valid(from_address): raise exceptions.AccountNotFound('From account does not exist')

            bal = self.balance(from_address)
            if bal < amount:
                raise exceptions.NotEnoughBalance(
                    'Account {} has balance {} but needs {} to send this tx'.format(from_address, bal, amount)
                )

            ###
            # Broadcast the transfer transaction on the network, and return the necessary data
            ###
            log.debug('Sending %f %s to @%s', amount, sym, address)
            tfr = acc.transfer(address, amount, sym, memo)
            # Beem's finalizeOp doesn't include TXID, so we try to find the TX on the blockchain after broadcast
            tx = self.find_steem_tx(tfr)

            log.debug('Success? TX Data - Transfer: %s Lookup TX: %s', tfr, tx)
            # Return TX data compatible with BaseManager standard
            return {
                # There's a risk we can't get the TXID, and so we fall back to None.
                'txid': tx.get('transaction_id', None),
                'coin': self.orig_symbol,
                'amount': amount,
                'fee': Decimal(0),
                'from': from_address,
                'send_type': 'send'
            }
        except MissingKeyError:
            raise exceptions.AuthorityMissing('Missing active key for sending account {}'.format(from_address))




