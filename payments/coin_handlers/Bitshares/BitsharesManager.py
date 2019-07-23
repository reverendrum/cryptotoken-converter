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
from typing import List, Tuple
from decimal import Decimal, getcontext, ROUND_DOWN
from payments.coin_handlers.base import exceptions, BaseManager
from payments.coin_handlers.Bitshares.BitsharesMixin import BitsharesMixin
from django.conf import settings
from steemengine.helpers import empty

from bitshares.account import Account
from bitshares.amount import Amount
from bitshares.memo import Memo
from bitsharesbase import operations
from graphenecommon.exceptions import KeyNotFound

getcontext().rounding = ROUND_DOWN


log = logging.getLogger(__name__)


class BitsharesManager(BaseManager, BitsharesMixin):
    """
    This class handles various operations for the **Bitshares* network, and supports any token
    on Bitshares.

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
    This attribute is automatically generated by scanning for :class:`models.Coin` s with the type ``bitshares``. 
    This saves us from hard coding specific coin symbols. See __init__.py for populating code.
    """

    def __init__(self, symbol: str):
        super().__init__(symbol.upper())

    def health(self) -> Tuple[str, tuple, tuple]:
        """
        Return health data for the passed symbol.

        Health data will include: symbol, status, API node, symbol issuer, symbol precision,
        our account for transacting with this symbol, and our account's balance of this symbol

        :return tuple health_data: (manager_name:str, headings:list/tuple, health_data:list/tuple,)
        """
        headers = ('Symbol', 'Status', 'API Node', 'Issuer',
                   'Precision', 'Our Account', 'Our Balance')

        class_name = type(self).__name__
        balance_str = '<b style="color: red">{}</b>'.format("ERROR GETTING BALANCE")
        precision_str = '<b style="color: red">{}</b>'.format("ERROR GETTING PRECISION")
        issuer = '<b style="color: red">{}</b>'.format("ERROR GETTING ISSUER")
        our_account_name = '<b style="color: red">{}</b>'.format("ERROR GETTING ACCOUNT NAME")

        status = 'Okay'
        try:
            our_asset = self.get_asset_obj(self.symbol)
            if our_asset is None:
                precision_str = '<b style="color: red">{}</b>'.format('Symbol %s not found' % (self.symbol,))
                issuer = precision_str
                status = 'ERROR'
            else:
                precision_str = str(our_asset['precision'])
                issuer_obj = self.get_account_obj(our_asset['issuer'])
                if issuer_obj is None:
                    issuer = our_asset['issuer']
                else:
                    issuer = issuer_obj.name

            our_account = self.get_account_obj(self.coin.our_account)
            if our_account is None:
                our_account_name = '<b style="color: red">{}</b>'.format('Account %s not found' % (self.coin.our_account,))
                status = 'ERROR'
            else:
                our_account_name = our_account.name
                if our_asset is None:
                    balance_str = '0.0'
                else:
                    amount_obj = our_account.balance(self.symbol)
                    balance = self.get_decimal_from_amount(amount_obj)
                    balance_str = ('{0:,.' + str(amount_obj.asset['precision']) + 'f}').format(balance)
        except:
            status = 'UNHANDLED EXCEPTION (see logs)'
            log.exception('Exception during %s.health for symbol %s', class_name, self.symbol)

        if status == 'Okay':
            status = '<b style="color: green">{}</b>'.format(status)
        else:
            status = '<b style="color: red">{}</b>'.format(status)

        data = (self.symbol, status, settings.BITSHARES_RPC_NODE, issuer, precision_str, our_account_name, balance_str)
        return class_name, headers, data

    def health_test(self) -> bool:
        """
        Check if the Bitshares API and node connection works or not, by requesting basic information such as
        the token metadata, and checking if our sending/receiving account exists.

        :return bool: True if Bitshares appears to be working, False if broken.
        """
        try:
            _, _, health_data = self.health()
            if 'Okay' in health_data[1]:
                return True
            return False
        except:
            return False

    def balance(self, address: str = None, memo: str = None, memo_case: bool = False) -> Decimal:
        """
        Get token balance for a given Bitshares account, if memo is given - get total symbol amt received with this memo.

        :param address:    Bitshares account to get balance for, if not set, uses self.coin.our_account
        :param memo:       If not None, get total `self.symbol` received with this memo.
        :param memo_case:  Case sensitive memo search

        :raises AccountNotFound:  The requested account/address doesn't exist

        :return: Decimal(balance)
        """
        balance = Decimal(0)
        if address is None:
            address = self.coin.our_account

        if not empty(memo):
            raise NotImplemented('Filtering by memos not implemented yet for BitsharesManager!')
        
        address = address.strip().lower()
        account_obj = self.get_account_obj(address)
        if account_obj is None:
            raise exceptions.AccountNotFound(f'Account {address} does not exist')

        asset_obj = self.get_asset_obj(self.symbol)
        if asset_obj is not None:
            amount_obj = account_obj.balance(self.symbol)
            balance = self.get_decimal_from_amount(amount_obj)

        return balance

    def get_deposit(self) -> tuple:
        """
        Returns the deposit account for this symbol

        :return tuple: A tuple containing ('account', receiving_account). The memo must be generated
                       by the calling function.
        """

        return 'account', self.coin.our_account

    def address_valid(self, address) -> bool:
        """If an account ( ``address`` param) exists on Bitshares, will return True. Otherwise False."""
        try:
            account_obj = self.get_account_obj(address)
            if account_obj is None:
                return False
        except:
            log.exception('Something went wrong while running %s.address_valid. Returning NOT VALID.', type(self))
            return False
        return True

    def issue(self, amount: Decimal, address: str, memo: str = None, trigger_data=None) -> dict:
        """
        Issue (create/print) tokens to a given address/account, optionally specifying a memo if desired.
        The network transaction fee for issuance will be paid by the issuing account in BTS.

        Example - Issue 5.10 SGTK to @privex

            >>> s = BitsharesManager('SGTK')
            >>> s.issue(address='privex', amount=Decimal('5.10'))

        :param Decimal amount:      Amount of tokens to issue, as a Decimal
        :param address:             Account to issue the tokens to (which is also the issuer account)
        :param memo:                Optional memo for the issuance transaction
        :raises IssuerKeyError:     Cannot issue because we don't have authority to (missing key etc.)
        :raises TokenNotFound:      When the requested token `symbol` does not exist
        :raises AccountNotFound:    The requested account doesn't exist
        :raises ArithmeticError:    When the amount is lower than the lowest amount allowed by the token's precision
        :return dict: Result Information

        Format::

          {
              txid:str - Transaction ID - None if not known,
              coin:str - Symbol that was sent,
              amount:Decimal - The amount that was issued,
              fee:Decimal    - TX Fee that was taken from the amount (will be 0 if fee is in BTS rather than the issuing token),
              from:str       - The account/address the coins were issued from,
              send_type:str       - Should be statically set to "issue"
          }

        """
        asset_obj = self.get_asset_obj(self.symbol)
        if asset_obj is None:
            raise exceptions.TokenNotFound(f'Failed to issue because {self.symbol} is an invalid token symbol.')

        # trim input amount to the token's precision just to be safe
        str_amount = ('{0:.' + str(asset_obj['precision']) + 'f}').format(amount)
        amount = Decimal(str_amount)

        if not self.is_amount_above_minimum(amount, asset_obj['precision']):
            raise ArithmeticError(f'Failed to issue because {amount} is less than the minimum amount allowed for {self.symbol} tokens.')

        to_account = self.get_account_obj(address)
        if to_account is None:
            raise exceptions.AccountNotFound(f'Failed to issue because issuing account {address} could not be found.')

        amount_obj = Amount(str_amount, self.symbol, blockchain_instance=self.bitshares)

        try:
            # make sure we have the necessary private keys loaded (memo key for encrypting memo, active key for issuing coins)
            self.set_wallet_keys(address, [ 'memo', 'active' ])

            if memo is None:
                memo = ''
            memo_obj = Memo(from_account=to_account, to_account=to_account, blockchain_instance=self.bitshares)
            encrypted_memo = memo_obj.encrypt(memo)

            # construct the transaction - note that transaction fee for issuance will be paid in BTS, but we retain the
            # flexibility to add support for paying the fee in the issuing token if deemed necessary
            op = operations.Asset_issue(
                **{
                    "fee": {"amount": 0, "asset_id": "1.3.0"},
                    "issuer": to_account["id"],
                    "asset_to_issue": {"amount": int(amount_obj), "asset_id": amount_obj.asset["id"]},
                    "memo": encrypted_memo,
                    "issue_to_account": to_account["id"],
                    "extensions": [],
                    "prefix": self.bitshares.prefix,
                }
            )

            log.debug('doing token issuance - address[%s], amount[%s %s], memo[%s]', address, str_amount, self.symbol, memo)

            # broadcast the transaction
            self.bitshares.finalizeOp(op, to_account, "active")
            result = self.bitshares.broadcast()
        except KeyNotFound as e:
            raise exceptions.IssuerKeyError(str(e))
        except exceptions.AuthorityMissing as e:
            raise exceptions.IssuerKeyError(str(e))

        return {
            'txid': None,     # transaction ID is not readily available from the Bitshares API
            'coin': self.orig_symbol,
            'amount': self.get_decimal_from_amount(amount_obj),
            'fee': Decimal(0),     # fee is in BTS, not the issuing token
            'from': address,
            'send_type': 'issue'
        }

    def is_amount_above_minimum(self, amount: Decimal, precision: int) -> bool:
        """
        Helper function to test if amount is at least equal to the minimum allowed fractional unit
        of our token. Returns True if so, otherwise False.
        """
        minimum_unit = Decimal('1.0')
        minimum_unit = minimum_unit / (10 ** precision)
        if amount < minimum_unit:
            return False
        return True

    def send(self, amount, address, memo=None, from_address=None, trigger_data=None) -> dict:
        """
        Send tokens to a given address/account, optionally specifying a memo. The Bitshares network transaction fee
        will be subtracted from the amount before sending.

        There must be a valid :py:class:`models.CryptoKeyPair` in the database for both 'active' and 'memo' keys for the
        from_address account, or an AuthorityMissing exception will be thrown.

        Example - send 1.23 BUILDTEAM from @someguy123 to @privex with memo 'hello'

            >>> s = BitsharesManager('BUILDTEAM')
            >>> s.send(from_address='someguy123', address='privex', amount=Decimal('1.23'), memo='hello')

        :param Decimal amount:      Amount of tokens to send, as a Decimal()
        :param address:             Account to send the tokens to
        :param from_address:        Account to send the tokens from
        :param memo:                Memo to send tokens with
        :raises AttributeError:     When both `from_address` and `self.coin.our_account` are blank.
        :raises ArithmeticError:    When the amount is lower than the lowest amount allowed by the token's precision
                                    (after subtracting the network transaction fee)
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

        # make sure we have the necessary private keys loaded (memo key for encrypting memo, active key for sending coins)
        self.set_wallet_keys(from_address, [ 'memo', 'active' ])

        asset_obj = self.get_asset_obj(self.symbol)
        if asset_obj is None:
            raise exceptions.TokenNotFound(f'Failed to send because {self.symbol} is an invalid token symbol.')

        # trim input amount to the token's precision just to be safe
        str_amount = ('{0:.' + str(asset_obj['precision']) + 'f}').format(amount)
        amount = Decimal(str_amount)

        if not self.is_amount_above_minimum(amount, asset_obj['precision']):
            raise ArithmeticError(f'Failed to send because {amount} is less than the minimum amount allowed for {self.symbol} tokens.')

        from_account = self.get_account_obj(from_address)
        if from_account is None:
            raise exceptions.AccountNotFound(f'Failed to send because source account {from_address} could not be found.')
        to_account = self.get_account_obj(address)
        if to_account is None:
            raise exceptions.AccountNotFound(f'Failed to send because destination account {address} could not be found.')

        # verify from_account balance is sufficient for the transaction
        from_account_balance = self.get_decimal_from_amount(from_account.balance(self.symbol))
        if from_account_balance < amount:
            raise exceptions.NotEnoughBalance(f'Failed to send because source account {from_address} balance {from_account_balance} {self.symbol} is less than amount to send ({amount} {self.symbol}).')

        amount_obj = Amount(str_amount, self.symbol, blockchain_instance=self.bitshares)

        try:
            if memo is None:
                memo = ''
            memo_obj = Memo(from_account=from_account, to_account=to_account, blockchain_instance=self.bitshares)
            encrypted_memo = memo_obj.encrypt(memo)

            # build preliminary transaction object, without network transaction fee
            op = operations.Transfer(
                **{
                    'fee': {'amount': 0, 'asset_id': amount_obj.asset['id']},
                    'from': from_account['id'],
                    'to': to_account['id'],
                    'amount': {'amount': int(amount_obj), 'asset_id': amount_obj.asset['id']},
                    'memo': encrypted_memo,
                    'prefix': self.bitshares.prefix,
                }
            )

            # calculate how much the transaction fee is - rather clunky method here but it works
            ops = [self.bitshares.txbuffer.operation_class(op)]
            ops_with_fees = self.bitshares.txbuffer.add_required_fees(ops, asset_id=amount_obj.asset['id'])
            raw_fee_amount = Decimal(str(ops_with_fees[0][1].data['fee']['amount']))
            fee_amount_str = '{0:f}'.format(raw_fee_amount / (10 ** amount_obj.asset['precision']))
            fee_amount = Amount(fee_amount_str, self.symbol, blockchain_instance=self.bitshares)
            amount_obj = amount_obj - fee_amount

            # verify the amount still makes sense after subtracting the transaction fee
            if int(amount_obj) < 1:
                raise ArithmeticError(f'Failed to send because {amount} is less than the network transaction fee of {fee_amount_str} {self.symbol} tokens.')

            # correct the transaction object to take into account the transaction fee
            adj_op = operations.Transfer(
                **{
                    'fee': {'amount': int(fee_amount), 'asset_id': amount_obj.asset['id']},
                    'from': from_account['id'],
                    'to': to_account['id'],
                    'amount': {'amount': int(amount_obj), 'asset_id': amount_obj.asset['id']},
                    'memo': encrypted_memo,
                    'prefix': self.bitshares.prefix,
                }
            )

            log.debug('doing Bitshares transaction - from_address[%s], address[%s], amount[%s %s], fee_amount[%s], amount_obj[%s], memo[%s]', from_address, address, str_amount, self.symbol, fee_amount, amount_obj, memo)

            # and finally, do the op!
            self.bitshares.finalizeOp(adj_op, from_address, "active", fee_asset=amount_obj.asset['id'])
            result = self.bitshares.broadcast()
        except KeyNotFound as e:
            raise exceptions.AuthorityMissing(str(e))

        return {
            'txid': None,     # transaction ID is not readily available from the Bitshares API
            'coin': self.orig_symbol,
            'amount': self.get_decimal_from_amount(amount_obj),
            'fee': self.get_decimal_from_amount(fee_amount),
            'from': from_address,
            'send_type': 'send'
        }

    def send_or_issue(self, amount, address, memo=None, trigger_data=None) -> dict:
        """
        Send tokens to a given account, optionally specifying a memo. If the balance of the
        sending account is too low, try to issue new tokens to ourself first. See documentation
        for the :func:`BitsharesManager.BitsharesManager.send` and
        :func:`BitsharesManager.BitsharesManager.issue` functions for more details.

        send_type in the returned dict will be either 'send' or 'issue' depending on the operation
        performed
        """
        try:
            log.debug(f'Attempting to send {amount} {self.symbol} to {address} ...')
            return self.send(amount=amount, address=address, memo=memo, trigger_data=trigger_data)
        except exceptions.NotEnoughBalance:
            acc = self.coin.our_account
            log.debug(f'Not enough balance. Issuing {amount} {self.symbol} to our account {acc} ...')

            # Issue the coins to our own account, and then send them.
            self.issue(amount=amount, address=acc,
                       memo=f"Issuing to self before transfer to {address}", trigger_data=trigger_data)

            log.debug(f'Sending newly issued coins: {amount} {self.symbol} to {address} ...')
            tx = self.send(amount=amount, address=address, memo=memo, from_address=acc, trigger_data=trigger_data)
            # So the calling function knows we had to issue these coins, we change the send_type back to 'issue'
            tx['send_type'] = 'issue'
            return tx
