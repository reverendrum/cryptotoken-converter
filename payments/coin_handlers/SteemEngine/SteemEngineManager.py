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
import privex.steemengine.exceptions as SENG
from typing import List, Tuple
from beem.exceptions import MissingKeyError
from decimal import Decimal, getcontext, ROUND_DOWN
from payments.coin_handlers.base import exceptions, BaseManager
from privex.steemengine import SteemEngineToken
from steemengine.helpers import empty

getcontext().rounding = ROUND_DOWN

log = logging.getLogger(__name__)


class SteemEngineManager(BaseManager):
    """
    This class handles various operations for the **SteemEngine** network, and supports almost any token
    on SteemEngine.

    It handles:

    - Validating source/destination accounts
    - Checking the balance for a given account, as well as the total amount received with a certain ``memo``
    - Issuing tokens to users
    - Sending tokens to users

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

    provides = []  # type: List[str]
    """
    This attribute is automatically generated by scanning for :class:`models.Coin` s with the type ``steemengine``. 
    This saves us from hard coding specific coin symbols. See __init__.py for populating code.
    """

    def __init__(self, symbol: str):
        super().__init__(symbol.upper())
        self.eng_rpc = SteemEngineToken()

    def health(self) -> Tuple[str, tuple, tuple]:
        """
        Return health data for the passed symbol.

        Health data will include: Symbol, Status, Current Block, Node Version, Wallet Balance,
        and number of p2p connections (all as strings)

        :return tuple health_data: (manager_name:str, headings:list/tuple, health_data:list/tuple,)
        """
        headers = ('Symbol', 'Status', 'API Node', 'Token Name', 'Issuer',
                   'Precision', 'Our Account', 'Our Balance')

        class_name = type(self).__name__
        api_node = token_name = issuer = precision = our_account = balance = ''

        status = 'Okay'
        try:
            rpc = self.eng_rpc
            api_node = rpc.rpc.url
            our_account = self.coin.our_account
            if not rpc.account_exists(our_account):
                status = 'Account {} not found'.format(our_account)
            tk = rpc.get_token(self.symbol)
            issuer = tk.get('issuer', 'ERROR GETTING ISSUER')
            token_name = tk.get('name', 'ERROR GETTING NAME')
            precision = str(tk.get('precision', 'ERROR GETTING PRECISION'))
            balance = self.balance(our_account)
            balance = ('{0:,.' + str(tk['precision']) + 'f}').format(balance)
        except:
            status = 'ERROR'
            log.exception('Exception during %s.health for symbol %s', class_name, self.symbol)

        if status == 'Okay':
            status = '<b style="color: green">{}</b>'.format(status)
        else:
            status = '<b style="color: red">{}</b>'.format(status)

        data = (self.symbol, status, api_node, token_name, issuer, precision, our_account, balance)
        return class_name, headers, data

    def balance(self, address: str = None, memo: str = None, memo_case: bool = False) -> Decimal:
        """
        Get token balance for a given Steem account, if memo is given - get total symbol amt received with this memo.

        :param address:    Steem account to get balance for, if not set, uses self.coin.our_account
        :param memo:       If not None, get total `self.symbol` received with this memo.
        :param memo_case:  Case sensitive memo search
        :return: Decimal(balance)
        """
        if address is None:
            address = self.coin.our_account
        address = address.lower()
        if memo is not None:
            memo = str(memo).strip()
        if empty(memo):
            return self.eng_rpc.get_token_balance(user=address, symbol=self.symbol)
        txs = self.eng_rpc.list_transactions(user=address, symbol=self.symbol, limit=1000)
        bal = Decimal(0)
        for t in txs:
            if t['to'] == address and t['symbol'] == self.symbol:
                m = t['memo'].strip()
                if m == memo or (not memo_case and m == memo.lower()):
                    bal += Decimal(t['quantity'])
        return bal

    def get_deposit(self) -> tuple:
        """
        Returns the deposit account for this symbol

        :return tuple: A tuple containing ('account', receiving_account). The memo must be generated
                       by the calling function.
        """

        return 'account', self.coin.our_account

    def address_valid(self, address) -> bool:
        """If an account ( ``address`` param) exists on Steem, will return True. Otherwise False."""

        try:
            return self.eng_rpc.account_exists(address)
        except:
            log.exception('Something went wrong while running %s.address_valid. Returning NOT VALID.', type(self))
            return False

    def issue(self, amount: Decimal, address: str, memo: str = None) -> dict:
        """
        Issue (create/print) tokens to a given address/account, optionally specifying a memo if supported

        Example - Issue 5.10 SGTK to @privex

            >>> s = SteemEngineManager('SGTK')
            >>> s.issue(address='privex', amount=Decimal('5.10'))

        :param Decimal amount:      Amount of tokens to issue, as a Decimal()
        :param address:             Address or account to issue the tokens to
        :param memo:                (ignored) Cannot issue tokens with a memo on SteemEngine
        :raises IssuerKeyError:     Cannot issue because we don't have authority to (missing key etc.)
        :raises IssueNotSupported:  Class does not support issuing, or requested symbol cannot be issued.
        :raises AccountNotFound:    The requested account/address doesn't exist
        :return dict: Result Information

        Format::

          {
              txid:str - Transaction ID - None if not known,
              coin:str - Symbol that was sent,
              amount:Decimal - The amount that was sent (after fees),
              fee:Decimal    - TX Fee that was taken from the amount,
              from:str       - The account/address the coins were issued from,
              send_type:str       - Should be statically set to "issue"
          }

        """

        try:
            token = self.eng_rpc.get_token(symbol=self.symbol)
            # If we get passed a float for some reason, make sure we trim it to the token's precision before
            # converting it to a Decimal.
            if type(amount) == float:
                amount = ('{0:.' + str(token['precision']) + 'f}').format(amount)
            amount = Decimal(amount)
            issuer = self.eng_rpc.get_token(self.symbol)['issuer']
            log.debug('Issuing %f %s to @%s', amount, self.symbol, address)
            t = self.eng_rpc.issue_token(symbol=self.symbol, to=address, amount=amount)
            txid = None     # There's a risk we can't get the TXID, and so we fall back to None.
            if 'transaction_id' in t:
                txid = t['transaction_id']
            return {
                'txid': txid,
                'coin': self.symbol,
                'amount': amount,
                'fee': Decimal(0),
                'from': issuer,
                'send_type': 'issue'
            }
        except SENG.AccountNotFound as e:
            raise exceptions.AccountNotFound(str(e))
        except MissingKeyError:
            raise exceptions.IssuerKeyError('Missing active key for issuer account {}'.format(issuer))

    def send(self, amount, address, memo=None, from_address=None) -> dict:
        """
        Send tokens to a given address/account, optionally specifying a memo if supported

        Example - send 1.23 SGTK from @someguy123 to @privex with memo 'hello'

            >>> s = SteemEngineManager('SGTK')
            >>> s.send(from_address='someguy123', address='privex', amount=Decimal('1.23'), memo='hello')

        :param Decimal amount:      Amount of tokens to send, as a Decimal()
        :param address:             Account to send the tokens to
        :param from_address:        Account to send the tokens from
        :param memo:                Memo to send tokens with (if supported)
        :raises AttributeError:     When both `from_address` and `self.coin.our_account` are blank.
        :raises ArithmeticError:    When the amount is lower than the lowest amount allowed by the token's precision
        :raises AuthorityMissing:   Cannot send because we don't have authority to (missing key etc.)
        :raises AccountNotFound:    The requested account/address doesn't exist
        :raises TokenNotFound:      When the requested token `symbol` does not exist
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
        try:
            token = self.eng_rpc.get_token(symbol=self.symbol)
            # If we get passed a float for some reason, make sure we trim it to the token's precision before
            # converting it to a Decimal.
            if type(amount) == float:
                amount = ('{0:.' + str(token['precision']) + 'f}').format(amount)
            amount = Decimal(amount)

            log.debug('Sending %f %s to @%s', amount, self.symbol, address)

            t = self.eng_rpc.send_token(symbol=self.symbol, from_acc=from_address,
                                        to_acc=address, amount=amount, memo=memo)
            txid = None  # There's a risk we can't get the TXID, and so we fall back to None.
            if 'transaction_id' in t:
                txid = t['transaction_id']
            return {
                'txid': txid,
                'coin': self.symbol,
                'amount': amount,
                'fee': Decimal(0),
                'from': from_address,
                'send_type': 'send'
            }
        except SENG.AccountNotFound as e:
            raise exceptions.AccountNotFound(str(e))
        except SENG.TokenNotFound as e:
            raise exceptions.TokenNotFound(str(e))
        except SENG.NotEnoughBalance as e:
            raise exceptions.NotEnoughBalance(str(e))
        except MissingKeyError:
            raise exceptions.AuthorityMissing('Missing active key for sending account {}'.format(from_address))
